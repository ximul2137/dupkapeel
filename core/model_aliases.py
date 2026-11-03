from __future__ import annotations

MODEL_ALIASES: dict[str, str] = {
    "nano-banana-2": "gemini-imagen",
    "gemini-3.1-flash-image": "gemini-imagen",
    "veo-3.1-lite-generate": "gemini-veo",
}

VIRTUAL_MODEL_IDS: tuple[str, ...] = (
    "gemini-imagen",
    "nano-banana-2",
    "gemini-3.1-flash-image",
    "gemini-veo",
    "veo-3.1-lite-generate",
)


def normalize_model_name(model_name: str) -> str:
    return MODEL_ALIASES.get(str(model_name or "").strip(), str(model_name or "").strip())
