"""
Funkcje pomocnicze do ustawień proxy

Obsługiwane formaty:
- http://127.0.0.1:7890
- http://user:pass@127.0.0.1:7890
- socks5h://127.0.0.1:7890
- socks5h://user:pass@127.0.0.1:7890 | no_proxy=localhost,127.0.0.1,.local

Format NO_PROXY:
- nazwy hostów lub sufiksy domen oddzielone przecinkami
- obsługa prefiksu wieloznacznego, np. .local pasuje do *.local
"""

import re
from typing import Tuple, Callable, Any, Optional
from urllib.parse import urlparse
import functools


def parse_proxy_setting(proxy_str: str) -> Tuple[str, str]:
    """
    Parsuje ciąg ustawień proxy, wyciągając URL proxy i listę NO_PROXY

    Args:
        proxy_str: ciąg ustawień proxy, np. "http://127.0.0.1:7890 | no_proxy=localhost,127.0.0.1"

    Returns:
        Tuple[str, str]: (proxy_url, no_proxy_list)
        - proxy_url: adres proxy, np. "http://127.0.0.1:7890"
        - no_proxy_list: lista NO_PROXY jako ciąg, np. "localhost,127.0.0.1"
    """
    if not proxy_str:
        return "", ""

    proxy_str = proxy_str.strip()
    if not proxy_str:
        return "", ""

    # Sprawdzenie, czy jest ustawienie no_proxy
    # Obsługiwany format: proxy_url | no_proxy=host1,host2
    no_proxy = ""
    proxy_url = proxy_str

    # Proxy i no_proxy rozdzielone znakiem |
    if "|" in proxy_str:
        parts = proxy_str.split("|", 1)
        proxy_url = parts[0].strip()
        no_proxy_part = parts[1].strip()

        # Parsowanie formatu no_proxy=xxx
        no_proxy_match = re.match(r"no_proxy\s*=\s*(.+)", no_proxy_part, re.IGNORECASE)
        if no_proxy_match:
            no_proxy = no_proxy_match.group(1).strip()

    return normalize_proxy_url(proxy_url), no_proxy


def extract_host(url: str) -> str:
    """
    Wyciąga nazwę hosta z URL

    Args:
        url: pełny URL, np. "https://example.com/api/emails"

    Returns:
        str: nazwa hosta, np. "example.com"
    """
    if not url:
        return ""

    url = url.strip()
    if not url:
        return ""

    # Brak prefiksu protokołu – dodajemy go, aby umożliwić parsowanie
    if not url.startswith(("http://", "https://", "socks5://", "socks5h://")):
        url = "http://" + url

    try:
        parsed = urlparse(url)
        return parsed.hostname or ""
    except Exception:
        return ""


def no_proxy_matches(host: str, no_proxy: str) -> bool:
    """
    Sprawdza, czy host jest na liście wyjątków NO_PROXY

    Args:
        host: sprawdzana nazwa hosta, np. "example.com"
        no_proxy: lista NO_PROXY jako ciąg, np. "localhost,127.0.0.1,.local"

    Returns:
        bool: True, jeśli host jest na liście wyjątków, w przeciwnym razie False

    Reguły dopasowania:
        - dokładne: "localhost" pasuje do "localhost"
        - sufiks domeny: ".local" pasuje do "foo.local", "bar.foo.local"
        - adres IP: "127.0.0.1" dopasowanie dokładne
    """
    if not host or not no_proxy:
        return False

    host = host.lower().strip()
    if not host:
        return False

    # Parsowanie listy no_proxy
    no_proxy_list = [item.strip().lower() for item in no_proxy.split(",") if item.strip()]

    for pattern in no_proxy_list:
        if not pattern:
            continue

        # Dopasowanie dokładne
        if host == pattern:
            return True

        # Dopasowanie sufiksu domeny (np. .local pasuje do foo.local)
        if pattern.startswith("."):
            if host.endswith(pattern) or host == pattern[1:]:
                return True
        else:
            # Także sufiks bez kropki (np. local pasuje do foo.local)
            if host.endswith("." + pattern):
                return True

    return False


def normalize_proxy_url(proxy_str: str) -> str:
    """
    Normalizuje format URL proxy

    Obsługiwane formaty wejściowe:
    - http://127.0.0.1:7890
    - http://user:pass@127.0.0.1:7890
    - socks5://127.0.0.1:7890
    - socks5h://127.0.0.1:7890
    - 127.0.0.1:7890 (automatycznie dodawane http://)
    - host:port:user:pass (stary format, konwertowany automatycznie)

    Returns:
        str: znormalizowany URL proxy
    """
    if not proxy_str:
        return ""

    proxy_str = proxy_str.strip()
    if not proxy_str:
        return ""

    # Jeśli to już standardowy URL, zwracamy bez zmian
    if proxy_str.startswith(("http://", "https://", "socks5://", "socks5h://")):
        return proxy_str

    # Próba parsowania starego formatu host:port:user:pass
    parts = proxy_str.split(":")
    if len(parts) == 4:
        host, port, user, password = parts
        return f"http://{user}:{password}@{host}:{port}"
    elif len(parts) == 2:
        # format host:port
        return f"http://{proxy_str}"

    # Nierozpoznany format – próba dodania prefiksu http://
    return f"http://{proxy_str}"


def request_with_proxy_fallback(request_func: Callable, *args, **kwargs) -> Any:
    """
    Opakowanie żądania z powrotem do połączenia bezpośredniego po błędzie proxy

    Jeśli połączenie przez proxy się nie uda, ponawia raz bez proxy

    Args:
        request_func: oryginalna funkcja żądania
        *args, **kwargs: argumenty przekazywane do funkcji żądania

    Returns:
        obiekt odpowiedzi

    Raises:
        oryginalny wyjątek (jeśli połączenie bezpośrednie też się nie uda)
    """
    # Typy błędów związanych z proxy
    PROXY_ERRORS = (
        "ProxyError",
        "ConnectTimeout",
        "ConnectionError",
        "407",  # Proxy Authentication Required
        "502",  # Bad Gateway (problem z proxy)
        "503",  # Service Unavailable (problem z proxy)
    )

    try:
        # Pierwsza próba (przez proxy)
        return request_func(*args, **kwargs)
    except Exception as e:
        error_str = str(e)
        error_type = type(e).__name__

        # Sprawdzenie, czy to błąd związany z proxy
        is_proxy_error = any(err in error_str or err in error_type for err in PROXY_ERRORS)

        if is_proxy_error and "proxies" in kwargs:
            # Ponowienie bez proxy
            original_proxies = kwargs.get("proxies")
            kwargs["proxies"] = None

            try:
                # Ponowienie połączeniem bezpośrednim
                return request_func(*args, **kwargs)
            except Exception:
                # Połączenie bezpośrednie też się nie udało – przywrócenie ustawień proxy i rzucenie oryginalnego wyjątku
                kwargs["proxies"] = original_proxies
                raise e
        else:
            # To nie błąd proxy – rzucamy dalej
            raise
