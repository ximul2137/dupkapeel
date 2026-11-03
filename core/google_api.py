"""Moduł interakcji z API Google

Odpowiada za wszystkie operacje interakcji z API Google Gemini Business
"""
import asyncio
import json
import logging
import os
import re
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, List

import httpx
from fastapi import HTTPException

if TYPE_CHECKING:
    from main import AccountManager

logger = logging.getLogger(__name__)

# Bazowy adres URL API Google
GEMINI_API_BASE = "https://biz-discoveryengine.googleapis.com/v1alpha"



def get_common_headers(jwt: str, user_agent: str) -> dict:
    """Generuje wspólnie używane nagłówki żądania"""
    return {
        "accept": "*/*",
        "accept-encoding": "gzip, deflate, br, zstd",
        "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
        "authorization": f"Bearer {jwt}",
        "content-type": "application/json",
        "origin": "https://business.gemini.google",
        "referer": "https://business.gemini.google/",
        "user-agent": user_agent,
        "x-server-timeout": "1800",
        "sec-ch-ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "cross-site",
    }


async def make_request_with_jwt_retry(
    account_mgr: "AccountManager",
    method: str,
    url: str,
    http_client: httpx.AsyncClient,
    user_agent: str,
    request_id: str = "",
    **kwargs
) -> httpx.Response:
    """Ogólne żądanie HTTP z automatyczną obsługą ponawiania po wygaśnięciu JWT

    Args:
        account_mgr: instancja AccountManager
        method: metoda HTTP (GET/POST)
        url: URL żądania
        http_client: klient httpx
        user_agent: ciąg User-Agent
        request_id: ID żądania (do logów)
        **kwargs: pozostałe parametry przekazywane do httpx (np. json, headers)

    Returns:
        obiekt httpx.Response
    """
    jwt = await account_mgr.get_jwt(request_id)
    headers = get_common_headers(jwt, user_agent)

    # Scalanie nagłówków podanych przez użytkownika (jeśli są)
    extra_headers = kwargs.pop("headers", None)
    if extra_headers:
        headers.update(extra_headers)

    # Wyciągnięcie parametru timeout (jeśli jest) i przekazanie osobno do httpx
    req_timeout = kwargs.pop("timeout", None)

    # Wysłanie żądania
    req_kwargs = {**kwargs}
    if req_timeout is not None:
        req_kwargs["timeout"] = req_timeout

    if method.upper() == "GET":
        resp = await http_client.get(url, headers=headers, **req_kwargs)
    elif method.upper() == "POST":
        resp = await http_client.post(url, headers=headers, **req_kwargs)
    else:
        raise ValueError(f"Unsupported HTTP method: {method}")

    # Przy 401 – odświeżenie JWT i jedno ponowienie
    if resp.status_code == 401:
        jwt = await account_mgr.get_jwt(request_id)
        headers = get_common_headers(jwt, user_agent)
        if extra_headers:
            headers.update(extra_headers)

        if method.upper() == "GET":
            resp = await http_client.get(url, headers=headers, **req_kwargs)
        elif method.upper() == "POST":
            resp = await http_client.post(url, headers=headers, **req_kwargs)

    return resp


async def create_google_session(
    account_manager: "AccountManager",
    http_client: httpx.AsyncClient,
    user_agent: str,
    request_id: str = ""
) -> str:
    """Tworzy sesję Google"""
    jwt = await account_manager.get_jwt(request_id)
    headers = get_common_headers(jwt, user_agent)
    body = {
        "configId": account_manager.config.config_id,
        "additionalParams": {"token": "-"},
        "createSessionRequest": {
            "session": {"name": "", "displayName": ""}
        }
    }

    req_tag = f"[req_{request_id}] " if request_id else ""
    r = await http_client.post(
        f"{GEMINI_API_BASE}/locations/global/widgetCreateSession",
        headers=headers,
        json=body,
        timeout=30.0,
    )
    if r.status_code != 200:
        logger.error(f"[SESSION] [{account_manager.config.account_id}] {req_tag}Nie udało się utworzyć sesji: {r.status_code}")
        raise HTTPException(r.status_code, "createSession failed")
    sess_name = r.json()["session"]["name"]
    logger.info(f"[SESSION] [{account_manager.config.account_id}] {req_tag}Utworzono pomyślnie: {sess_name[-12:]}")
    return sess_name


async def upload_context_file(
    session_name: str,
    mime_type: str,
    base64_content: str,
    account_manager: "AccountManager",
    http_client: httpx.AsyncClient,
    user_agent: str,
    request_id: str = ""
) -> str:
    """Przesyła plik do podanej sesji, zwraca fileId"""
    jwt = await account_manager.get_jwt(request_id)
    headers = get_common_headers(jwt, user_agent)

    # Generowanie losowej nazwy pliku
    ext = mime_type.split('/')[-1] if '/' in mime_type else "bin"
    file_name = f"upload_{int(time.time())}_{uuid.uuid4().hex[:6]}.{ext}"

    body = {
        "configId": account_manager.config.config_id,
        "additionalParams": {"token": "-"},
        "addContextFileRequest": {
            "name": session_name,
            "fileName": file_name,
            "mimeType": mime_type,
            "fileContents": base64_content
        }
    }

    r = await http_client.post(
        f"{GEMINI_API_BASE}/locations/global/widgetAddContextFile",
        headers=headers,
        json=body,
        timeout=60.0,
    )

    req_tag = f"[req_{request_id}] " if request_id else ""
    if r.status_code != 200:
        logger.error(f"[FILE] [{account_manager.config.account_id}] {req_tag}Nie udało się przesłać pliku: {r.status_code}")
        error_text = r.text
        if r.status_code == 400:
            try:
                payload = json.loads(r.text or "{}")
                message = payload.get("error", {}).get("message", "")
            except Exception:
                message = ""
            if "Unsupported file type" in message:
                mime_type = message.split("Unsupported file type:", 1)[-1].strip()
                hint = f"Nieobsługiwany typ pliku: {mime_type}. Przekształć go na PDF, obraz lub tekst zwykły i prześlij ponownie."
                raise HTTPException(400, hint)
        raise HTTPException(r.status_code, f"Upload failed: {error_text}")

    data = r.json()
    file_id = data.get("addContextFileResponse", {}).get("fileId")
    logger.info(f"[FILE] [{account_manager.config.account_id}] {req_tag}Plik przesłany pomyślnie: {mime_type}")
    return file_id


async def get_session_file_metadata(
    account_mgr: "AccountManager",
    session_name: str,
    http_client: httpx.AsyncClient,
    user_agent: str,
    request_id: str = ""
) -> dict:
    """Pobiera metadane plików w sesji, wraz z poprawną ścieżką sesji"""
    body = {
        "configId": account_mgr.config.config_id,
        "additionalParams": {"token": "-"},
        "listSessionFileMetadataRequest": {
            "name": session_name,
            "filter": "file_origin_type = AI_GENERATED"
        }
    }

    resp = await make_request_with_jwt_retry(
        account_mgr,
        "POST",
        f"{GEMINI_API_BASE}/locations/global/widgetListSessionFileMetadata",
        http_client,
        user_agent,
        request_id,
        json=body,
        timeout=30.0
    )

    if resp.status_code != 200:
        logger.warning(f"[IMAGE] [{account_mgr.config.account_id}] [req_{request_id}] Nie udało się pobrać metadanych pliku: {resp.status_code}")
        return {}

    data = resp.json()
    result = {}
    file_metadata_list = data.get("listSessionFileMetadataResponse", {}).get("fileMetadata", [])

    for fm in file_metadata_list:
        fid = fm.get("fileId")
        if fid:
            result[fid] = fm

    return result


def build_image_download_url(session_name: str, file_id: str) -> str:
    """Buduje URL pobierania obrazu"""
    return f"{GEMINI_API_BASE}/{session_name}:downloadFile?fileId={file_id}&alt=media"


async def download_image_with_jwt(
    account_mgr: "AccountManager",
    session_name: str,
    file_id: str,
    http_client: httpx.AsyncClient,
    user_agent: str,
    request_id: str = "",
    max_retries: int = 3
) -> bytes:
    """
    Pobiera obraz z autoryzacją JWT (z mechanizmem limitu czasu i ponawiania)

    Args:
        account_mgr: menedżer konta
        session_name: nazwa sesji
        file_id: ID pliku
        http_client: klient httpx
        user_agent: ciąg User-Agent
        request_id: ID żądania
        max_retries: maksymalna liczba prób (domyślnie 3)

    Returns:
        dane bajtowe obrazu

    Raises:
        HTTPException: pobieranie nie powiodło się
        asyncio.TimeoutError: przekroczono limit czasu
    """
    url = build_image_download_url(session_name, file_id)
    logger.info(f"[IMAGE] [{account_mgr.config.account_id}] [req_{request_id}] Rozpoczęto pobieranie obrazu: {file_id[:8]}...")

    for attempt in range(max_retries):
        try:
            # Limit czasu 3 minuty (180 sekund) – użycie wait_for dla zgodności z Python 3.10
            resp = await asyncio.wait_for(
                make_request_with_jwt_retry(
                    account_mgr,
                    "GET",
                    url,
                    http_client,
                    user_agent,
                    request_id,
                    follow_redirects=True
                ),
                timeout=180
            )

            resp.raise_for_status()
            logger.info(f"[IMAGE] [{account_mgr.config.account_id}] [req_{request_id}] Pobrano obraz pomyślnie: {file_id[:8]}... ({len(resp.content)} bytes)")
            return resp.content

        except asyncio.TimeoutError:
            logger.warning(f"[IMAGE] [{account_mgr.config.account_id}] [req_{request_id}] Limit czasu pobierania obrazu (próba {attempt + 1}/{max_retries}): {file_id[:8]}...")
            if attempt == max_retries - 1:
                raise HTTPException(504, f"Image download timeout after {max_retries} attempts")
            await asyncio.sleep(2 ** attempt)  # wycofywanie wykładnicze: 2s, 4s, 8s

        except httpx.HTTPError as e:
            logger.warning(f"[IMAGE] [{account_mgr.config.account_id}] [req_{request_id}] Nie udało się pobrać obrazu (próba {attempt + 1}/{max_retries}): {type(e).__name__}")
            if attempt == max_retries - 1:
                raise HTTPException(500, f"Image download failed: {str(e)[:100]}")
            await asyncio.sleep(2 ** attempt)  # wycofywanie wykładnicze

        except Exception as e:
            logger.error(f"[IMAGE] [{account_mgr.config.account_id}] [req_{request_id}] Wyjątek przy pobieraniu obrazu: {type(e).__name__}: {str(e)[:100]}")
            raise

    # Nie powinniśmy tu dotrzeć
    raise HTTPException(500, "Image download failed unexpectedly")


def save_image_to_hf(image_data: bytes, chat_id: str, file_id: str, mime_type: str, base_url: str, image_dir: str, url_path: str = "images") -> str:
    """Zapisuje obraz do trwałego magazynu, zwraca pełny publiczny URL"""
    ext_map = {
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/gif": ".gif",
        "image/webp": ".webp",
        "video/mp4": ".mp4",
        "video/webm": ".webm",
        "video/quicktime": ".mov"
    }
    ext = ext_map.get(mime_type, ".png")

    filename = f"{chat_id}_{file_id}{ext}"
    save_path = os.path.join(image_dir, filename)

    # Katalog został utworzony przy starcie, nie trzeba go tworzyć ponownie
    with open(save_path, "wb") as f:
        f.write(image_data)

    return f"{base_url}/{url_path}/{filename}"
