import json, time, os, asyncio, re, yaml
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Union, Dict, Any
from pathlib import Path
import logging
from dotenv import load_dotenv

import httpx
import aiofiles
from fastapi import HTTPException, Request
from util.streaming_parser import parse_json_array_stream_async
from collections import deque
from threading import Lock
from core.database import stats_db
from app.bootstrap import RouteBootstrapDeps, register_http_routes
from app.factory import AppFactorySettings, create_http_app, mount_media_assets
from app.lifecycle import LifecycleDeps, register_lifecycle_hooks
from app.api.schemas import ChatRequest
from app.services.chat_service import (
    ChatRequestHandlerDeps,
    ChatStreamFlowStaticDeps,
    build_openai_model_ids,
    create_chat_completion_chunk,
    handle_chat_request,
    stream_chat_with_flow,
)
from app.services.chat_media_service import (
    parse_generated_media_files,
)
from app.services.gallery_service import cleanup_expired_gallery_payload

# ---------- Konfiguracja katalogu danych ----------
DATA_DIR = "./data"
logger_prefix = "[LOCAL]"

# Upewnienie się, że katalog danych istnieje
os.makedirs(DATA_DIR, exist_ok=True)

# Wspólne ścieżki plików danych
TASK_HISTORY_MTIME: float = 0.0
IMAGE_DIR = os.path.join(DATA_DIR, "images")
VIDEO_DIR = os.path.join(DATA_DIR, "videos")

# Upewnienie się, że katalogi obrazów i wideo istnieją
os.makedirs(IMAGE_DIR, exist_ok=True)
os.makedirs(VIDEO_DIR, exist_ok=True)

# Import modułu uwierzytelniania
from core.auth import verify_api_key
from core.session_auth import is_logged_in, login_user, logout_user, require_login, generate_session_secret

# Import modułów podstawowych
from core.message import (
    get_conversation_key,
    parse_last_message,
    build_full_context_text
)
from core.google_api import (
    get_common_headers,
    create_google_session,
    upload_context_file,
    get_session_file_metadata,
    download_image_with_jwt,
    save_image_to_hf,
)
from core.account import (
    MultiAccountManager,
    RetryPolicy,
    CooldownConfig,
    format_account_expiration,
    load_multi_account_config,
    load_accounts_from_source,
    reload_accounts as _reload_accounts,
    update_accounts_config as _update_accounts_config,
    delete_account as _delete_account,
    update_account_disabled_status as _update_account_disabled_status,
    bulk_update_account_disabled_status as _bulk_update_account_disabled_status,
    bulk_delete_accounts as _bulk_delete_accounts
)
from core.proxy_utils import parse_proxy_setting
from core.model_aliases import normalize_model_name, VIRTUAL_MODEL_IDS
from core.version import get_update_status, get_version_info

# Import trackera uptime
from core import uptime as uptime_tracker

# Import zarządzania konfiguracją i systemu szablonów
from core.config import config_manager, config

# Obsługa przechowywania w bazie danych
from core import storage, account

# Mapowanie modeli na typy limitów
MODEL_TO_QUOTA_TYPE = {
    "gemini-imagen": "images",
    "gemini-veo": "videos"
}

# ---------- Konfiguracja logowania ----------

# Bufor logów w pamięci (ostatnie 3000 wpisów, czyszczony po restarcie)
log_buffer = deque(maxlen=3000)
log_lock = Lock()

# Trwały zapis statystyk
stats_lock = asyncio.Lock()  # blokada asynchroniczna

async def load_stats():
    """Wczytuje statystyki (asynchronicznie). Gdy baza jest niedostępna, używa domyślnych wartości w pamięci."""
    data = None
    if storage.is_database_enabled():
        try:
            has_stats = await asyncio.to_thread(storage.has_stats_sync)
            if has_stats:
                data = await asyncio.to_thread(storage.load_stats_sync)
                if not isinstance(data, dict):
                    data = None
        except Exception as e:
            logger.error(f"[STATS] Błąd ładowania bazy danych: {str(e)[:50]}")

    if data is None:
        data = {
            "total_visitors": 0,
            "total_requests": 0,
            "success_count": 0,
            "failed_count": 0,
            "request_timestamps": [],
            "model_request_timestamps": {},
            "failure_timestamps": [],
            "rate_limit_timestamps": [],
            "visitor_ips": {},
            "account_conversations": {},
            "account_failures": {},
            "recent_conversations": []
        }

    if isinstance(data.get("request_timestamps"), list):
        data["request_timestamps"] = deque(data["request_timestamps"], maxlen=20000)
    if isinstance(data.get("failure_timestamps"), list):
        data["failure_timestamps"] = deque(data["failure_timestamps"], maxlen=10000)
    if isinstance(data.get("rate_limit_timestamps"), list):
        data["rate_limit_timestamps"] = deque(data["rate_limit_timestamps"], maxlen=10000)

    return data

async def save_stats(stats):
    """Zapisuje statystyki (asynchronicznie). Gdy baza jest niedostępna, nic nie jest zapisywane."""
    def convert_deques(obj):
        """Rekurencyjnie zamienia wszystkie obiekty deque na list"""
        if isinstance(obj, deque):
            return list(obj)
        elif isinstance(obj, dict):
            return {k: convert_deques(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [convert_deques(item) for item in obj]
        return obj

    stats_to_save = convert_deques(stats)

    if storage.is_database_enabled():
        try:
            saved = await asyncio.to_thread(storage.save_stats_sync, stats_to_save)
            if saved:
                return
        except Exception as e:
            logger.error(f"[STATS] Błąd zapisu do bazy danych: {str(e)[:50]}")
    return

# Inicjalizacja statystyk (wczytywane asynchronicznie przy starcie)
global_stats = {
    "total_visitors": 0,
    "total_requests": 0,
    "success_count": 0,
    "failed_count": 0,
    "request_timestamps": deque(maxlen=20000),
    "model_request_timestamps": {},
    "failure_timestamps": deque(maxlen=10000),
    "rate_limit_timestamps": deque(maxlen=10000),
    "visitor_ips": {},
    "account_conversations": {},
    "account_failures": {},
    "recent_conversations": []
}

def get_beijing_time_str(ts: Optional[float] = None) -> str:
    tz = timezone(timedelta(hours=8))
    current = datetime.fromtimestamp(ts or time.time(), tz=tz)
    return current.strftime("%Y-%m-%d %H:%M:%S")


def build_recent_conversation_entry(
    request_id: str,
    model: Optional[str],
    message_count: Optional[int],
    start_ts: float,
    status: str,
    duration_s: Optional[float] = None,
    error_detail: Optional[str] = None,
) -> dict:
    start_time = get_beijing_time_str(start_ts)
    if model:
        start_content = f"{model}"
        if message_count:
            start_content = f"{model} | {message_count} wiad."
    else:
        start_content = "Przetwarzanie żądania"

    events = [{
        "time": start_time,
        "type": "start",
        "content": start_content,
    }]

    end_time = get_beijing_time_str(start_ts + duration_s) if duration_s is not None else get_beijing_time_str()

    if status == "success":
        if duration_s is not None:
            events.append({
                "time": end_time,
                "type": "complete",
                "status": "success",
            "content": f"Odpowiedź ukończona | czas {duration_s:.2f}s",
            })
        else:
            events.append({
                "time": end_time,
                "type": "complete",
                "status": "success",
            "content": "Odpowiedź ukończona",
            })
    elif status == "timeout":
        events.append({
            "time": end_time,
            "type": "complete",
            "status": "timeout",
            "content": "Przekroczono czas żądania",
        })
    else:
        detail = error_detail or "Błąd żądania"
        events.append({
            "time": end_time,
            "type": "complete",
            "status": "error",
            "content": detail[:120],
        })

    return {
        "request_id": request_id,
        "start_time": start_time,
        "start_ts": start_ts,
        "status": status,
        "events": events,
    }

class MemoryLogHandler(logging.Handler):
    """Własny handler logów zapisujący wpisy do bufora w pamięci"""
    def emit(self, record):
        log_entry = self.format(record)
        # Konwersja na czas pekiński (UTC+8)
        beijing_tz = timezone(timedelta(hours=8))
        beijing_time = datetime.fromtimestamp(record.created, tz=beijing_tz)
        with log_lock:
            log_buffer.append({
                "time": beijing_time.strftime("%Y-%m-%d %H:%M:%S"),
                "level": record.levelname,
                "message": record.getMessage()
            })

# Konfiguracja logowania
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("gemini")

# ---------- Linux zombie process reaper ----------
# Some optional browser-related child processes may exit without being waited on,
# which can accumulate as zombies (<defunct>) in long-running services.
try:
    from core.child_reaper import install_child_reaper

    install_child_reaper(log=lambda m: logger.warning(m))
except Exception:
    # Never fail startup due to optional process reaper.
    pass

# Dodanie handlera logów w pamięci
memory_handler = MemoryLogHandler()
memory_handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s", datefmt="%H:%M:%S"))
logger.addHandler(memory_handler)

# ---------- Zarządzanie konfiguracją (wspólny system konfiguracji) ----------
# Cała konfiguracja przez config_manager, priorytet: zmienne środowiskowe > YAML > wartości domyślne
TIMEOUT_SECONDS = 300
API_KEY = config.basic.api_key
DEFAULT_ADMIN_KEY = "123456"
ADMIN_KEY = config.security.admin_key or DEFAULT_ADMIN_KEY
_proxy_chat, _no_proxy_chat = parse_proxy_setting(config.basic.proxy_for_chat)
PROXY_FOR_CHAT = _proxy_chat
_NO_PROXY = ",".join(filter(None, {_no_proxy_chat}))
if _NO_PROXY:
    os.environ["NO_PROXY"] = _NO_PROXY
else:
    os.environ.pop("NO_PROXY", None)
BASE_URL = config.basic.base_url
SESSION_SECRET_KEY = config.security.session_secret_key
SESSION_EXPIRE_HOURS = config.session.expire_hours

# ---------- Konfiguracja widoku publicznego ----------
LOGO_URL = config.public_display.logo_url
CHAT_URL = config.public_display.chat_url

# ---------- Konfiguracja generowania obrazów ----------
IMAGE_GENERATION_ENABLED = config.image_generation.enabled
IMAGE_GENERATION_MODELS = config.image_generation.supported_models

def get_request_quota_type(model_name: str) -> str:
    """Return the quota bucket for the requested model."""
    canonical_model = normalize_model_name(model_name)
    if canonical_model in MODEL_TO_QUOTA_TYPE:
        return MODEL_TO_QUOTA_TYPE[canonical_model]
    if IMAGE_GENERATION_ENABLED and canonical_model in IMAGE_GENERATION_MODELS:
        return "images"
    return "text"

def get_required_quota_types(model_name: str) -> List[str]:
    """Każde żądanie wymaga limitu tekstowego; żądania obrazów/wideo wymagają też odpowiedniego limitu."""
    required = ["text"]
    request_quota = get_request_quota_type(model_name)
    if request_quota != "text":
        required.append(request_quota)
    return required

# ---------- Mapowanie modeli wirtualnych ----------
VIRTUAL_MODELS = {
    "gemini-imagen": {"imageGenerationSpec": {}},
    "gemini-veo": {"videoGenerationSpec": {}},
}

def get_tools_spec(model_name: str) -> dict:
    """Return toolsSpec for the requested model."""
    canonical_model = normalize_model_name(model_name)
    # Virtual media models
    if canonical_model in VIRTUAL_MODELS:
        return VIRTUAL_MODELS[canonical_model]
    
    # Standard chat models
    tools_spec = {
        "webGroundingSpec": {},
        "toolRegistry": "default_tool_registry",
    }
    
    if IMAGE_GENERATION_ENABLED and canonical_model in IMAGE_GENERATION_MODELS:
        tools_spec["imageGenerationSpec"] = {}
    
    return tools_spec


# ---------- Konfiguracja ponowień ----------
MAX_ACCOUNT_SWITCH_TRIES = config.retry.max_account_switch_tries
SESSION_CACHE_TTL_SECONDS = config.retry.session_cache_ttl_seconds

def build_retry_policy() -> RetryPolicy:
    return RetryPolicy(
        cooldowns=CooldownConfig(
            text=config.retry.text_rate_limit_cooldown_seconds,
            images=config.retry.images_rate_limit_cooldown_seconds,
            videos=config.retry.videos_rate_limit_cooldown_seconds,
        ),
    )

RETRY_POLICY = build_retry_policy()

# ---------- Konfiguracja mapowania modeli ----------
MODEL_MAPPING = {
    "gemini-auto": None,
    "gemini-2.5-pro": "gemini-2.5-pro",
    "gemini-3.5-flash": "gemini-3.5-flash",
    "gemini-3.1-pro-preview": "gemini-3.1-pro-preview",
    "gemini-4-argon": "gemini-4-argon",
    "argon": "gemini-4-argon"
}

# ---------- Klient HTTP ----------
# Klient operacji czatu (pobieranie JWT, tworzenie sesji, wysyłanie wiadomości)
http_client = httpx.AsyncClient(
    proxy=(PROXY_FOR_CHAT or None),
    verify=False,
    http2=False,
    timeout=httpx.Timeout(TIMEOUT_SECONDS, connect=60.0),
    limits=httpx.Limits(
        max_keepalive_connections=100,
        max_connections=200
    )
)

# Klient strumieniowy czatu (odpowiedzi strumieniowe)
http_client_chat = httpx.AsyncClient(
    proxy=(PROXY_FOR_CHAT or None),
    verify=False,
    http2=False,
    timeout=httpx.Timeout(TIMEOUT_SECONDS, connect=60.0),
    limits=httpx.Limits(
        max_keepalive_connections=100,
        max_connections=200
    )
)

# Logowanie konfiguracji proxy
logger.info(f"[PROXY] Chat operations (JWT/session/messages): {PROXY_FOR_CHAT if PROXY_FOR_CHAT else 'disabled'}")

# ---------- Funkcje pomocnicze ----------
def _parse_bool(value, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in ("1", "true", "yes", "y", "on"):
            return True
        if lowered in ("0", "false", "no", "n", "off"):
            return False
    return default


def get_base_url(request: Request) -> str:
    """Zwraca pełny base URL (najpierw ze zmiennej środowiskowej, w przeciwnym razie z żądania)"""
    # Najpierw zmienna środowiskowa
    if BASE_URL:
        return BASE_URL.rstrip("/")

    # Automatycznie z żądania (zgodne z reverse proxy)
    forwarded_proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    forwarded_host = request.headers.get("x-forwarded-host", request.headers.get("host"))

    return f"{forwarded_proto}://{forwarded_host}"



# ---------- Stałe ----------
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"

# ---------- Obsługa wielu kont ----------
# (AccountConfig, AccountManager, MultiAccountManager przeniesione do core/account.py)

# ---------- Zarządzanie plikami konfiguracji ----------
# (funkcje zarządzania konfiguracją przeniesione do core/account.py)

# Inicjalizacja menedżera wielu kont
multi_account_mgr = load_multi_account_config(
    http_client,
    USER_AGENT,
    RETRY_POLICY,
    SESSION_CACHE_TTL_SECONDS,
    global_stats
)

# Legacy register/login services were removed.

# Fallback admin password when ADMIN_KEY is not configured
if not config.security.admin_key:
    logger.warning("[SYSTEM] ADMIN_KEY not set, fallback to default password 123456")

# Logi startowe
logger.info("[SYSTEM] Endpoint API: /v1/chat/completions")
logger.info("[SYSTEM] Admin API endpoints: /admin/*")
logger.info("[SYSTEM] Public endpoints: /public/log, /public/stats, /public/uptime")
logger.info(f"[SYSTEM] Czas wygaśnięcia sesji: {SESSION_EXPIRE_HOURS} godz.")
logger.info("[SYSTEM] Inicjalizacja systemu zakończona")

# ---------- Zarządzanie JWT ----------
# (JWTManager przeniesiony do core/jwt.py)

# ---------- Zarządzanie sesjami i plikami ----------
# (funkcje Google API przeniesione do core/google_api.py)

# ---------- Logika przetwarzania wiadomości ----------
# (funkcje przetwarzania wiadomości przeniesione do core/message.py)

frontend_origin = os.getenv("FRONTEND_ORIGIN", "").strip()
allow_all_origins = os.getenv("ALLOW_ALL_ORIGINS", "0") == "1"
app = create_http_app(
    AppFactorySettings(
        frontend_origin=frontend_origin,
        allow_all_origins=allow_all_origins,
        session_secret_key=SESSION_SECRET_KEY,
        session_expire_hours=SESSION_EXPIRE_HOURS,
    )
)

# ---------- Inicjalizacja statycznego serwowania obrazów i wideo ----------
mount_media_assets(app, IMAGE_DIR, VIDEO_DIR)
logger.info(f"[SYSTEM] Serwis statyczny obrazów włączony: /images/ -> {IMAGE_DIR}")
logger.info(f"[SYSTEM] Serwis statyczny wideo włączony: /videos/ -> {VIDEO_DIR}")

# ---------- API galerii obrazów ----------

def _scan_media_files() -> list:
    """Skanuje wszystkie pliki mediów w katalogach data/images i data/videos"""
    beijing_tz = timezone(timedelta(hours=8))
    now = time.time()
    expire_hours = config.basic.image_expire_hours
    files = []

    for directory, url_prefix, media_type in [
        (IMAGE_DIR, "images", "image"),
        (VIDEO_DIR, "videos", "video"),
    ]:
        if not os.path.isdir(directory):
            continue
        for filename in os.listdir(directory):
            filepath = os.path.join(directory, filename)
            if not os.path.isfile(filepath):
                continue
            try:
                stat = os.stat(filepath)
                mtime = stat.st_mtime
                size = stat.st_size
                created_at = datetime.fromtimestamp(mtime, tz=beijing_tz).strftime("%Y-%m-%d %H:%M:%S")
                # Obliczenie pozostałego czasu ważności
                if expire_hours > 0:
                    expires_in_seconds = (mtime + expire_hours * 3600) - now
                    expired = expires_in_seconds <= 0
                else:
                    expires_in_seconds = -1  # nigdy nie wygasa
                    expired = False

                ext = os.path.splitext(filename)[1].lower()
                file_type = "video" if ext in (".mp4", ".webm", ".mov") else media_type

                files.append({
                    "filename": filename,
                    "url": f"/{url_prefix}/{filename}",
                    "size": size,
                    "created_at": created_at,
                    "mtime": mtime,
                    "type": file_type,
                    "expired": expired,
                    "expires_in_seconds": int(expires_in_seconds) if expire_hours > 0 else None,
                })
            except Exception:
                continue

    # Sortowanie od najnowszych
    files.sort(key=lambda x: x["mtime"], reverse=True)
    return files


# ---------- Funkcje anonimizacji logów ----------
def get_sanitized_logs(limit: int = 100) -> list:
    """Zwraca zanonimizowane logi pogrupowane wg ID żądania, z wyciągniętymi kluczowymi zdarzeniami"""
    with log_lock:
        logs = list(log_buffer)

    # Grupowanie wg ID żądania (dwa formaty: z [req_xxx] i bez)
    request_logs = {}
    orphan_logs = []  # logi bez request_id (np. wybór konta)

    for log in logs:
        message = log["message"]
        req_match = re.search(r'\[req_([a-z0-9]+)\]', message)

        if req_match:
            request_id = req_match.group(1)
            if request_id not in request_logs:
                request_logs[request_id] = []
            request_logs[request_id].append(log)
        else:
            # Logi bez request_id (np. wybór konta) – odkładane na później
            orphan_logs.append(log)

    # Przypisanie orphan_logs (np. wybór konta) do odpowiednich żądań
    # Strategia: log orphan trafia do najbliższego czasowo kolejnego żądania
    for orphan in orphan_logs:
        orphan_time = orphan["time"]
        # Szukanie najbliższego czasowo żądania po logu orphan
        closest_request_id = None
        min_time_diff = None

        for request_id, req_logs in request_logs.items():
            if req_logs:
                first_log_time = req_logs[0]["time"]
                # orphan powinien być przed żądaniem lub w tym samym czasie
                if first_log_time >= orphan_time:
                    if min_time_diff is None or first_log_time < min_time_diff:
                        min_time_diff = first_log_time
                        closest_request_id = request_id

        # Po znalezieniu żądania log orphan wstawiany jest na początek jego listy logów
        if closest_request_id:
            request_logs[closest_request_id].insert(0, orphan)

    # Wyciąganie kluczowych zdarzeń dla każdego żądania
    sanitized = []
    for request_id, req_logs in request_logs.items():
        # Zbieranie kluczowych informacji
        model = None
        message_count = None
        retry_events = []
        final_status = "in_progress"
        duration = None
        start_time = req_logs[0]["time"]

        # Przejście przez wszystkie logi żądania
        for log in req_logs:
            message = log["message"]

            # Wyciągnięcie nazwy modelu i liczby wiadomości (początek rozmowy)
            if ('Otrzymano żądanie:' in message or '收到请求:' in message) and not model:
                model_match = re.search(r'(?:Otrzymano żądanie|收到请求): ([^ |]+)', message)
                if model_match:
                    model = model_match.group(1)
                count_match = re.search(r'(\d+)(?: wiad\.|条消息)', message)
                if count_match:
                    message_count = int(count_match.group(1))

            # Wyciągnięcie zdarzeń ponowień (nieudane próby, przełączenie konta, wybór konta)
            # Uwaga: logi "ponawianie" są pomijane, bo towarzyszą logom "nie powiodło się (próba"
            if any(keyword in message for keyword in ['Przełączanie konta', 'Wybór konta', 'nie powiodło się (próba', '切换账户', '选择账户', '失败 (尝试']):
                retry_events.append({
                    "time": log["time"],
                    "message": message
                })

            # Wyciągnięcie ukończenia odpowiedzi (najwyższy priorytet – końcowy sukces ignoruje błędy pośrednie)
            if 'Odpowiedź ukończona:' in message or '响应完成:' in message:
                time_match = re.search(r'(?:Odpowiedź ukończona|响应完成): ([\d.]+)(?:s|秒)', message)
                if time_match:
                    duration = time_match.group(1) + 's'
                    final_status = "success"

            # Wykrycie ukończenia odpowiedzi niestrumieniowej
            if 'Odpowiedź niestrumieniowa ukończona' in message or '非流式响应完成' in message:
                final_status = "success"

            # Wykrycie błędu (tylko gdy status nie jest success)
            if final_status != "success" and (log['level'] == 'ERROR' or 'nie powiodło się' in message.lower() or 'błąd' in message.lower() or '失败' in message):
                final_status = "error"

            # Wykrycie przekroczenia czasu (tylko gdy status nie jest success)
            if final_status != "success" and ('przekroczono czas' in message.lower() or 'timeout' in message.lower() or '超时' in message):
                final_status = "timeout"

        # Brak informacji o modelu, ale jest błąd – nadal wyświetlamy
        if not model and final_status == "in_progress":
            continue

        # Budowanie listy kluczowych zdarzeń
        events = []

        # 1. Początek rozmowy
        if model:
            events.append({
                "time": start_time,
                "type": "start",
                "content": f"{model} | {message_count} wiad." if message_count else model
            })
        else:
            # Przypadek: brak informacji o modelu, ale jest błąd
            events.append({
                "time": start_time,
                "type": "start",
                "content": "Przetwarzanie żądania"
            })

        # 2. Zdarzenia ponowień
        failure_count = 0  # licznik nieudanych prób
        account_select_count = 0  # licznik wyborów konta

        for i, retry in enumerate(retry_events):
            msg = retry["message"]

            # Rozpoznawanie typów zdarzeń ponowień (dopasowanie wg priorytetu)
            if 'nie powiodło się (próba' in msg or '失败 (尝试' in msg:
                # Nieudane tworzenie sesji
                failure_count += 1
                events.append({
                    "time": retry["time"],
                    "type": "retry",
                    "content": f"Błąd usługi, ponawianie ({failure_count})"
                })
            elif 'Wybór konta' in msg or '选择账户' in msg:
                # Wybór/przełączenie konta
                account_select_count += 1

                # Jeśli następny log to "przełączanie konta", pomijamy bieżący "wybór konta" (unikanie duplikatów)
                next_is_switch = (i + 1 < len(retry_events) and ('Przełączanie konta' in retry_events[i + 1]["message"] or '切换账户' in retry_events[i + 1]["message"]))

                if not next_is_switch:
                    if account_select_count == 1:
                        # Pierwszy wybór: wyświetlany jako "Wybór węzła usługi"
                        events.append({
                            "time": retry["time"],
                            "type": "select",
                            "content": "Wybór węzła usługi"
                        })
                    else:
                        # Drugi i kolejne: wyświetlane jako "Przełączenie węzła usługi"
                        events.append({
                            "time": retry["time"],
                            "type": "switch",
                            "content": "Przełączenie węzła usługi"
                        })
            elif 'Przełączanie konta' in msg or '切换账户' in msg:
                # Przełączenie konta w trakcie (wyświetlane jako "Przełączenie węzła usługi")
                events.append({
                    "time": retry["time"],
                    "type": "switch",
                    "content": "Przełączenie węzła usługi"
                })

        # 3. Zdarzenie ukończenia
        if final_status == "success":
            if duration:
                events.append({
                    "time": req_logs[-1]["time"],
                    "type": "complete",
                    "status": "success",
                    "content": f"Odpowiedź ukończona | czas {duration}"
                })
            else:
                events.append({
                    "time": req_logs[-1]["time"],
                    "type": "complete",
                    "status": "success",
                    "content": "Odpowiedź ukończona"
                })
        elif final_status == "error":
            events.append({
                "time": req_logs[-1]["time"],
                "type": "complete",
                "status": "error",
                "content": "Błąd żądania"
            })
        elif final_status == "timeout":
            events.append({
                "time": req_logs[-1]["time"],
                "type": "complete",
                "status": "timeout",
                "content": "Przekroczono czas żądania"
            })

        sanitized.append({
            "request_id": request_id,
            "start_time": start_time,
            "status": final_status,
            "events": events
        })

    # Sortowanie wg czasu i ograniczenie liczby
    sanitized.sort(key=lambda x: x["start_time"], reverse=True)
    return sanitized[:limit]


def _set_multi_account_mgr(manager) -> None:
    global multi_account_mgr
    multi_account_mgr = manager


def _set_global_stats(stats: dict[str, Any]) -> None:
    global global_stats
    global_stats = stats


def _get_openai_model_ids() -> list[str]:
    return build_openai_model_ids(MODEL_MAPPING, VIRTUAL_MODEL_IDS)


def _get_runtime_settings_state() -> dict[str, Any]:
    return {
        "api_key": API_KEY,
        "proxy_for_chat": PROXY_FOR_CHAT,
        "base_url": BASE_URL,
        "logo_url": LOGO_URL,
        "chat_url": CHAT_URL,
        "image_generation_enabled": IMAGE_GENERATION_ENABLED,
        "image_generation_models": IMAGE_GENERATION_MODELS,
        "max_account_switch_tries": MAX_ACCOUNT_SWITCH_TRIES,
        "retry_policy": RETRY_POLICY,
        "session_cache_ttl_seconds": SESSION_CACHE_TTL_SECONDS,
        "session_expire_hours": SESSION_EXPIRE_HOURS,
        "http_client": http_client,
        "http_client_chat": http_client_chat,
    }


def _apply_runtime_settings_state(state: dict[str, Any]) -> None:
    global API_KEY, PROXY_FOR_CHAT, BASE_URL, LOGO_URL, CHAT_URL
    global IMAGE_GENERATION_ENABLED, IMAGE_GENERATION_MODELS
    global MAX_ACCOUNT_SWITCH_TRIES, RETRY_POLICY
    global SESSION_CACHE_TTL_SECONDS
    global SESSION_EXPIRE_HOURS, http_client, http_client_chat

    API_KEY = state["api_key"]
    PROXY_FOR_CHAT = state["proxy_for_chat"]
    BASE_URL = state["base_url"]
    LOGO_URL = state["logo_url"]
    CHAT_URL = state["chat_url"]
    IMAGE_GENERATION_ENABLED = state["image_generation_enabled"]
    IMAGE_GENERATION_MODELS = state["image_generation_models"]
    MAX_ACCOUNT_SWITCH_TRIES = state["max_account_switch_tries"]
    RETRY_POLICY = state["retry_policy"]
    SESSION_CACHE_TTL_SECONDS = state["session_cache_ttl_seconds"]
    SESSION_EXPIRE_HOURS = state["session_expire_hours"]
    http_client = state["http_client"]
    http_client_chat = state["http_client_chat"]


def _create_http_client_for_proxy(proxy: Optional[str]):
    return httpx.AsyncClient(
        proxy=(proxy or None),
        verify=False,
        http2=False,
        timeout=httpx.Timeout(TIMEOUT_SECONDS, connect=60.0),
        limits=httpx.Limits(
            max_keepalive_connections=100,
            max_connections=200,
        ),
    )

# ---------- Rejestracja cyklu życia aplikacji ----------
register_lifecycle_hooks(
    app,
    LifecycleDeps(
        account_store=account,
        cleanup_expired_gallery=cleanup_expired_gallery_payload,
        data_dir=DATA_DIR,
        get_config=lambda: config,
        get_multi_account_mgr=lambda: multi_account_mgr,
        image_dir=IMAGE_DIR,
        load_stats=load_stats,
        logger=logger,
        set_global_stats=_set_global_stats,
        stats_db=stats_db,
        storage=storage,
        uptime_tracker=uptime_tracker,
        video_dir=VIDEO_DIR,
    ),
)

register_http_routes(
    app,
    RouteBootstrapDeps(
        api_key=lambda: API_KEY,
        admin_key=lambda: ADMIN_KEY,
        apply_runtime_state=_apply_runtime_settings_state,
        build_retry_policy=build_retry_policy,
        bulk_delete_accounts=_bulk_delete_accounts,
        bulk_update_account_disabled_status=_bulk_update_account_disabled_status,
        chat_handler=lambda chat_req, request, authorization=None: chat_impl(chat_req, request, authorization),
        config_manager=config_manager,
        create_http_client=_create_http_client_for_proxy,
        delete_account=_delete_account,
        format_account_expiration=format_account_expiration,
        get_config=lambda: config,
        get_base_url=get_base_url,
        get_global_stats=lambda: global_stats,
        get_http_client=lambda: http_client,
        get_log_buffer=lambda: log_buffer,
        get_model_ids=_get_openai_model_ids,
        get_multi_account_mgr=lambda: multi_account_mgr,
        get_retry_policy=lambda: RETRY_POLICY,
        get_runtime_state=_get_runtime_settings_state,
        get_sanitized_logs=get_sanitized_logs,
        get_session_cache_ttl_seconds=lambda: SESSION_CACHE_TTL_SECONDS,
        get_update_status=get_update_status,
        get_user_agent=lambda: USER_AGENT,
        get_version_info=get_version_info,
        image_dir=IMAGE_DIR,
        load_accounts_from_source=load_accounts_from_source,
        logger=logger,
        log_lock=log_lock,
        login_user=login_user,
        logout_user=logout_user,
        parse_proxy_setting=parse_proxy_setting,
        require_login=require_login,
        save_account_cooldown_state=account.save_account_cooldown_state,
        save_image_file=save_image_to_hf,
        save_stats=save_stats,
        scan_media_files=_scan_media_files,
        set_multi_account_mgr=_set_multi_account_mgr,
        stats_db=stats_db,
        stats_lock=stats_lock,
        update_account_disabled_status=_update_account_disabled_status,
        update_accounts_config=_update_accounts_config,
        uptime_tracker=uptime_tracker,
        verify_api_key=verify_api_key,
        video_dir=VIDEO_DIR,
    ),
)

def create_chunk(id: str, created: int, model: str, delta: dict, finish_reason: Union[str, None]) -> str:
    return create_chat_completion_chunk(
        chunk_id=id,
        created=created,
        model=model,
        delta=delta,
        finish_reason=finish_reason,
    )

# chat handler
async def chat_impl(
    req: ChatRequest,
    request: Request,
    authorization: Optional[str]
):
    del authorization

    stream_chat_deps = ChatStreamFlowStaticDeps(
        create_chunk=create_chunk,
        download_media_file=download_image_with_jwt,
        get_base_url=get_base_url,
        get_common_headers=get_common_headers,
        get_file_metadata=get_session_file_metadata,
        get_request_quota_type=get_request_quota_type,
        get_tools_spec=get_tools_spec,
        http_client=http_client,
        http_client_chat=http_client_chat,
        image_dir=IMAGE_DIR,
        image_output_format=config_manager.image_output_format,
        logger=logger,
        model_mapping=MODEL_MAPPING,
        parse_generated_media_files=parse_generated_media_files,
        parse_json_array_stream=parse_json_array_stream_async,
        save_media_file=save_image_to_hf,
        stream_timeout=httpx.Timeout(300.0, connect=20.0, read=300.0, write=60.0, pool=60.0),
        stream_url="https://biz-discoveryengine.googleapis.com/v1alpha/locations/global/widgetStreamAssist",
        uptime_tracker=uptime_tracker,
        user_agent=USER_AGENT,
        video_dir=VIDEO_DIR,
        video_output_format=config_manager.video_output_format,
    )

    return await handle_chat_request(
        deps=ChatRequestHandlerDeps(
            build_full_context_text=build_full_context_text,
            build_recent_conversation_entry=build_recent_conversation_entry,
            create_google_session=create_google_session,
            get_conversation_key=get_conversation_key,
            get_required_quota_types=get_required_quota_types,
            get_request_quota_type=get_request_quota_type,
            global_stats=global_stats,
            http_client=http_client,
            logger=logger,
            max_account_switch_tries=MAX_ACCOUNT_SWITCH_TRIES,
            model_mapping=MODEL_MAPPING,
            multi_account_mgr=multi_account_mgr,
            parse_last_message=parse_last_message,
            save_stats=save_stats,
            stats_db=stats_db,
            stats_lock=stats_lock,
            stream_chat=lambda session, text_content, file_ids, model_name, chat_id, created_time, stream_account_manager, is_stream=True, stream_request_id="", stream_request=None: stream_chat_with_flow(
                deps=stream_chat_deps,
                request=stream_request or request,
                account_manager=stream_account_manager,
                session=session,
                text_content=text_content,
                file_ids=file_ids,
                model_name=model_name,
                chat_id=chat_id,
                created_time=created_time,
                is_stream=is_stream,
                request_id=stream_request_id,
            ),
            upload_context_file=upload_context_file,
            uptime_tracker=uptime_tracker,
            user_agent=USER_AGENT,
            virtual_models=VIRTUAL_MODELS,
        ),
        req=req,
        request=request,
    )

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "7860"))
    uvicorn.run(app, host="0.0.0.0", port=port)
