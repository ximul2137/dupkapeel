"""Text-protocol tool support for OpenAI-compatible clients.

The business.gemini.google upstream (widgetStreamAssist) does not support
arbitrary client-side function calling. This module emulates OpenAI
`tools` / `tool_calls` on top of a plain text session:

1. Outgoing: OpenAI `tools` definitions are rendered into an instruction
   block prepended to the text sent upstream. Assistant `tool_calls` and
   role=="tool" result messages from the client are rendered into the
   same marker format so the model sees a consistent conversation.
2. Incoming: the model's raw text response is scanned for
   `[TOOL_CALL] {...} [/TOOL_CALL]` markers and converted into proper
   OpenAI `tool_calls` chunks (works for both stream and non-stream
   responses via the SSE chunk transform).
"""
from __future__ import annotations

import json
import re
import uuid
from typing import Any, AsyncIterable

TOOL_MARKER_OPEN = "[TOOL_CALL]"
TOOL_MARKER_CLOSE = "[/TOOL_CALL]"

_TOOL_CALL_RE = re.compile(r"\[TOOL_CALL\](.*?)(?:\[/TOOL_CALL\]|$)", re.DOTALL)


def has_active_tools(tools: Any) -> bool:
    return bool(tools)


def _extract_content_text(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") == "text"
        )
    return str(content)


def _parse_message_dict(msg: Any) -> dict[str, Any]:
    if hasattr(msg, "model_dump"):
        return msg.model_dump()
    return msg


def _dump_tool_calls(tool_calls: Any) -> list[dict[str, Any]]:
    if not tool_calls:
        return []
    if isinstance(tool_calls, dict):
        tool_calls = list(tool_calls.values())
    result = []
    for tc in tool_calls:
        if not isinstance(tc, dict):
            continue
        fn = tc.get("function") or {}
        name = fn.get("name") or tc.get("name") or ""
        args = fn.get("arguments", tc.get("arguments", {}))
        result.append({"name": str(name), "arguments": args})
    return result


def _format_tool_call_block(name: str, arguments: Any) -> str:
    try:
        args_json = json.dumps(arguments, ensure_ascii=False)
    except Exception:
        args_json = "{}"
    return f"{TOOL_MARKER_OPEN} {{\"name\": {json.dumps(name)}, \"arguments\": {args_json}}} {TOOL_MARKER_CLOSE}"


def build_tool_instructions(tools: list[Any]) -> str:
    lines = [
        "# TOOL PROTOCOL (CRITICAL)",
        "You are an autonomous agent connected to an external tool executor (an IDE).",
        "You CANNOT perform side effects yourself (no files, no shell, no browser).",
        "To execute an action, output EXACTLY one or more tool-call blocks and nothing else in that section:",
        f'{TOOL_MARKER_OPEN} {{"name": "<tool_name>", "arguments": <single JSON object matching the tool\'s schema>}} {TOOL_MARKER_CLOSE}',
        "Rules:",
        "- One block per call; you may output several blocks for several independent calls.",
        '- "arguments" MUST be a single valid JSON object (match the JSON Schema below).',
        "- NEVER put explanatory prose inside a block; no markdown code fences around blocks.",
        "- NEVER simulate a tool result or describe output you have not received.",
        "- After emitting block(s), stop. The system will respond with TOOL RESULT messages.",
        "- When results arrive (messages titled TOOL RESULT), use them to continue the task.",
        "- If no tool is needed (pure conversation/answer), reply in normal text WITHOUT any block.",
        "",
        "Available tools:",
    ]
    for tool in tools or []:
        if not isinstance(tool, dict):
            continue
        if tool.get("type") and not tool.get("function"):
            continue
        fn = tool.get("function") or tool
        name = fn.get("name", "")
        desc = fn.get("description", "")
        params = fn.get("parameters")
        params_str = ""
        if isinstance(params, dict) and (params.get("properties") or params.get("required")):
            try:
                params_str = " " + json.dumps(params, ensure_ascii=False)
            except Exception:
                params_str = ""
        lines.append(f"- {name}: {desc}{params_str}")
    return "\n".join(lines)


def _render_single_message(msg: dict[str, Any], *, is_last: bool) -> str:
    role = msg.get("role", "")
    if role == "system":
        return f"SYSTEM INSTRUCTIONS:\n{_extract_content_text(msg.get('content'))}"
    if role == "tool":
        name = msg.get("name") or ""
        return f"TOOL RESULT {name + ' ' if name else ''}(id={msg.get('tool_call_id') or 'n/a'}):\n{_extract_content_text(msg.get('content'))}"
    if role == "user":
        label = "USER (CURRENT REQUEST):" if is_last else "PREVIOUS USER MESSAGE:"
        return f"{label}\n{_extract_content_text(msg.get('content'))}"
    if role == "assistant":
        calls = _dump_tool_calls(msg.get("tool_calls"))
        if calls:
            blocks = "\n".join(_format_tool_call_block(c["name"], c["arguments"]) for c in calls)
            return f"YOUR PREVIOUS TOOL CALLS:\n{blocks}"
        return f"YOUR PREVIOUS REPLY:\n{_extract_content_text(msg.get('content'))}"
    return f"{role.upper()}:\n{_extract_content_text(msg.get('content'))}"


def build_tool_request_text(
    *,
    messages: list[Any],
    tools: Any,
    is_new_conversation: bool,
    fallback_text: str = "",
) -> str:
    """Text to send upstream for a tool-enabled request."""
    dicts = [_parse_message_dict(m) for m in (messages or [])]
    if not has_active_tools(tools):
        return fallback_text

    last_user_idx = -1
    for i, m in enumerate(dicts):
        if m.get("role") == "user":
            last_user_idx = i

    parts: list[str] = []

    if is_new_conversation:
        # Fresh Google session: include instructions + FULL conversation.
        parts.append(build_tool_instructions((tools if isinstance(tools, list) else [tools])))
        for i, m in enumerate(dicts):
            parts.append(_render_single_message(m, is_last=(i == last_user_idx)))
        return "\n\n".join(p for p in parts if p and p != "SYSTEM INSTRUCTIONS:\n")

    # Continuing session (Google already holds earlier turns + instructions).
    # Only the tool round since the last user message is missing server-side.
    for i, m in enumerate(dicts[last_user_idx + 1:], start=last_user_idx + 1):
        parts.append(_render_single_message(m, is_last=(i == last_user_idx)))
    # If nothing followed the last user message, the last message itself is the
    # user turn -> its text is appended below via fallback-like handling.
    if not parts and last_user_idx >= 0 and last_user_idx == len(dicts) - 1:
        parts.append(_render_single_message(dicts[-1], is_last=True))
    return "\n\n".join(p for p in parts if p)


def parse_tool_calls(text: str) -> tuple[list[dict[str, Any]], str]:
    """Extract tool-call blocks. Returns (calls, remaining_text)."""
    calls: list[dict[str, Any]] = []
    spans: list[tuple[int, int]] = []

    for match in _TOOL_CALL_RE.finditer(text or ""):
        raw = (match.group(1) or "").strip()
        spans.append(match.span())
        try:
            data = json.loads(raw)
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        name = str(data.get("name", "")).strip()
        if not name:
            continue
        args = data.get("arguments", data.get("args", {}))
        if isinstance(args, str):
            args_str = args.strip() or "{}"
            try:
                json.loads(args_str)
            except Exception:
                args_str = json.dumps({"input": args})
        else:
            try:
                args_str = json.dumps(args if args is not None else {}, ensure_ascii=False)
            except Exception:
                args_str = "{}"
        calls.append(
            {
                "id": f"call_{uuid.uuid4().hex[:12]}",
                "type": "function",
                "function": {"name": name, "arguments": args_str},
            }
        )

    cleaned = text or ""
    for start, end in sorted(spans, reverse=True):
        cleaned = cleaned[:start] + cleaned[end:]
    cleaned = cleaned.strip()
    return calls, cleaned


def _sse_chunk(chat_id: str, created: int, model: str, delta: dict[str, Any], finish: str | None) -> str:
    payload = {
        "id": chat_id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": model,
        "choices": [{"index": 0, "delta": delta, "logprobs": None, "finish_reason": finish}],
        "system_fingerprint": None,
    }
    return f"data: {json.dumps(payload)}\n\n"


async def transform_chat_chunks_with_tools(
    chunk_stream: AsyncIterable[str],
    *,
    chat_id: str,
    created_time: int,
    model_name: str,
) -> AsyncIterable[str]:
    """Buffer an SSE chunk stream, convert tool markers into OpenAI tool_calls."""
    contents: list[str] = []
    reasonings: list[str] = []

    async for chunk_str in chunk_stream:
        if chunk_str.startswith("data: [DONE]"):
            break
        if not chunk_str.startswith("data: "):
            continue
        try:
            data = json.loads(chunk_str[6:])
        except json.JSONDecodeError:
            continue
        try:
            delta = data["choices"][0]["delta"]
        except (KeyError, IndexError):
            continue
        if isinstance(delta.get("reasoning_content"), str) and delta["reasoning_content"]:
            reasonings.append(delta["reasoning_content"])
        if isinstance(delta.get("content"), str):
            contents.append(delta["content"])

    full_text = "".join(contents)
    calls, cleaned = parse_tool_calls(full_text)

    yield _sse_chunk(chat_id, created_time, model_name, {"role": "assistant", "content": ""}, None)
    if reasonings:
        yield _sse_chunk(chat_id, created_time, model_name, {"reasoning_content": "".join(reasonings)}, None)
    if cleaned:
        yield _sse_chunk(chat_id, created_time, model_name, {"content": cleaned}, None)
    if calls:
        for idx, call in enumerate(calls):
            yield _sse_chunk(
                chat_id,
                created_time,
                model_name,
                {"tool_calls": [{**call, "index": idx}]},
                None,
            )
    yield _sse_chunk(chat_id, created_time, model_name, {}, "tool_calls" if calls else "stop")
    yield "data: [DONE]\n\n"
