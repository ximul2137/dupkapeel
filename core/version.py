from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import Dict, Optional, Tuple

import httpx


ROOT_DIR = Path(__file__).resolve().parent.parent
VERSION_FILE = ROOT_DIR / "VERSION"
DEFAULT_REPOSITORY = ""


def get_app_version() -> str:
    try:
        value = VERSION_FILE.read_text(encoding="utf-8").strip()
        if value:
            return value
    except Exception:
        pass
    env_version = str(os.getenv("GEMINI_BUSINESS2API_VERSION") or "").strip()
    return env_version or "0.0.0"


def get_git_commit_short() -> str:
    env_value = str(
        os.getenv("GEMINI_BUSINESS2API_GIT_SHA")
        or os.getenv("GEMINI_WEB2API_GIT_SHA")
        or ""
    ).strip()
    if env_value:
        return env_value[:12]
    try:
        return (
            subprocess.check_output(
                ["git", "rev-parse", "--short", "HEAD"],
                cwd=str(ROOT_DIR),
                stderr=subprocess.DEVNULL,
                text=True,
            )
            .strip()
        )
    except Exception:
        return ""


def get_version_info() -> Dict[str, object]:
    version = get_app_version()
    commit = get_git_commit_short()
    default_admin_key_active = not str(os.getenv("ADMIN_KEY") or "").strip()
    return {
        "version": version,
        "tag": f"v{version}",
        "commit": commit,
        "default_admin_key_active": default_admin_key_active,
    }


def get_update_status(repository: Optional[str] = None) -> Dict[str, object]:
    current = get_version_info()
    return {
        **current,
        "repository": "",
        "latest_tag": current["tag"],
        "latest_version": current["version"],
        "release_url": "",
        "is_latest": True,
        "update_available": False,
        "check_error": "",
    }
