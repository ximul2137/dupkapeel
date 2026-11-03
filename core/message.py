"""Moduł przetwarzania wiadomości

Odpowiada za parsowanie wiadomości, wyciąganie tekstu i generowanie odcisku rozmowy
"""
import asyncio
import base64
import hashlib
import logging
import re
from typing import List, TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from main import Message

logger = logging.getLogger(__name__)


def get_conversation_key(messages: List[dict], client_identifier: str = "") -> str:
    """
    Generuje odcisk rozmowy (pierwsze 3 wiadomości + identyfikator klienta, dla unikalności)

    Strategia:
    1. Odcisk z pierwszych 3 wiadomości (a nie tylko pierwszej)
    2. Dodanie identyfikatora klienta (IP lub request_id), aby uniknąć kolizji między użytkownikami
    3. Zachowanie ponownego użycia sesji (kolejne wiadomości tego samego użytkownika trafiają do tej samej sesji)

    Args:
        messages: lista wiadomości
        client_identifier: identyfikator klienta (np. adres IP lub request_id), do rozróżniania użytkowników
    """
    if not messages:
        return f"{client_identifier}:empty" if client_identifier else "empty"

    # Wyciągnięcie kluczowych informacji z pierwszych 3 wiadomości (rola + treść)
    message_fingerprints = []
    for msg in messages[:3]:  # tylko pierwsze 3
        role = msg.get("role", "")
        content = msg.get("content", "")

        # Ujednolicenie formatu treści (ciąg znaków lub tablica)
        if isinstance(content, list):
            # Wiadomość multimodalna: tylko część tekstowa
            text = extract_text_from_content(content)
        else:
            text = str(content)

        # Normalizacja: usunięcie białych znaków na brzegach, małe litery
        text = text.strip().lower()

        # Połączenie roli i treści
        message_fingerprints.append(f"{role}:{text}")

    # Generowanie odcisku z pierwszych 3 wiadomości + identyfikatora klienta
    conversation_prefix = "|".join(message_fingerprints)
    if client_identifier:
        conversation_prefix = f"{client_identifier}|{conversation_prefix}"

    return hashlib.md5(conversation_prefix.encode()).hexdigest()


def extract_text_from_content(content) -> str:
    """
    Wyciąga tekst z pola content wiadomości
    Obsługuje zarówno ciągi znaków, jak i tablice multimodalne
    """
    if isinstance(content, str):
        return content
    elif isinstance(content, list):
        # Wiadomość multimodalna: tylko część tekstowa
        return "".join([x.get("text", "") for x in content if x.get("type") == "text"])
    else:
        return str(content)


async def parse_last_message(messages: List['Message'], http_client: httpx.AsyncClient, request_id: str = ""):
    """Parsuje ostatnią wiadomość, oddzielając tekst od plików (obrazy, PDF, dokumenty itd., base64 i URL)"""
    if not messages:
        return "", []

    last_msg = messages[-1]
    content = last_msg.content

    text_content = ""
    images = [] # List of {"mime": str, "data": str_base64} - nazwa dla zgodności, obsługuje wszystkie pliki
    image_urls = []  # URL-e do pobrania - nazwa dla zgodności, obsługuje wszystkie pliki

    if isinstance(content, str):
        text_content = content
    elif isinstance(content, list):
        for part in content:
            if part.get("type") == "text":
                text_content += part.get("text", "")
            elif part.get("type") == "image_url":
                url = part.get("image_url", {}).get("url", "")
                # Parsowanie Data URI: data:mime/type;base64,xxxxxx (wszystkie typy MIME)
                match = re.match(r"data:([^;]+);base64,(.+)", url)
                if match:
                    images.append({"mime": match.group(1), "data": match.group(2)})
                elif url.startswith(("http://", "https://")):
                    image_urls.append(url)
                else:
                    logger.warning(f"[FILE] [req_{request_id}] Nieobsługiwany format pliku: {url[:30]}...")

    # Równoległe pobieranie wszystkich plików z URL (obrazy, PDF, dokumenty itd.)
    if image_urls:
        async def download_url(url: str):
            try:
                resp = await http_client.get(url, timeout=30, follow_redirects=True)
                if resp.status_code == 404:
                    logger.warning(f"[FILE] [req_{request_id}] Plik pod URL wygasł (404), pominięto: {url[:50]}...")
                    return None
                resp.raise_for_status()
                content_type = resp.headers.get("content-type", "application/octet-stream").split(";")[0]
                # Bez ograniczenia do obrazów, obsługa wszystkich typów plików
                b64 = base64.b64encode(resp.content).decode()
                logger.info(f"[FILE] [req_{request_id}] Pobrano plik z URL: {url[:50]}... ({len(resp.content)} bytes, {content_type})")
                return {"mime": content_type, "data": b64}
            except httpx.HTTPStatusError as e:
                status_code = e.response.status_code if e.response else "unknown"
                logger.warning(f"[FILE] [req_{request_id}] Nie udało się pobrać pliku z URL ({status_code}): {url[:50]}... - {e}")
                return None
            except Exception as e:
                logger.warning(f"[FILE] [req_{request_id}] Nie udało się pobrać pliku z URL: {url[:50]}... - {e}")
                return None

        results = await asyncio.gather(*[download_url(u) for u in image_urls], return_exceptions=True)
        safe_results = []
        for result in results:
            if isinstance(result, Exception):
                logger.warning(f"[FILE] [req_{request_id}] Wyjątek przy pobieraniu pliku z URL: {type(result).__name__}: {str(result)[:120]}")
                continue
            safe_results.append(result)
        images.extend([r for r in safe_results if r])

    return text_content, images


def build_full_context_text(messages: List['Message']) -> str:
    """Łączy tylko tekst historii; obrazy przetwarzane są wyłącznie z bieżącego żądania"""
    prompt = ""
    for msg in messages:
        role = "User" if msg.role in ["user", "system", "tool"] else "Assistant"
        if msg.content is None:
            content_str = ""
        else:
            content_str = extract_text_from_content(msg.content)

        # Dodanie znacznika obrazu dla wiadomości multimodalnych
        if isinstance(msg.content, list):
            image_count = sum(1 for part in msg.content if part.get("type") == "image_url")
            if image_count > 0:
                content_str += "[obraz]" * image_count

        prompt += f"{role}: {content_str}\n\n"
    return prompt
