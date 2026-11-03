"""
Moduł uwierzytelniania API
Weryfikacja klucza API (dla endpointów API)
Endpointy administracyjne używają uwierzytelniania sesją (zob. core/session_auth.py)
"""
from typing import Optional
from fastapi import HTTPException


def verify_api_key(api_key_value: str, authorization: Optional[str] = None) -> bool:
    """
    Weryfikuje klucz API (obsługa wielu kluczy oddzielonych przecinkami)

    Args:
        api_key_value: skonfigurowany klucz API (pusty = brak weryfikacji; wiele kluczy oddzielonych przecinkami)
        authorization: wartość nagłówka Authorization

    Returns:
        True przy poprawnej weryfikacji, w przeciwnym razie HTTPException

    Obsługiwane formaty:
    1. Bearer YOUR_API_KEY
    2. YOUR_API_KEY

    Przykład konfiguracji wielu kluczy:
    API_KEY=key1,key2,key3
    """
    # Jeśli API_KEY nie jest ustawiony, pomijamy weryfikację
    if not api_key_value:
        return True

    # Sprawdzenie nagłówka Authorization
    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="Missing Authorization header"
        )

    # Wyciągnięcie tokenu (obsługa formatu Bearer)
    token = authorization
    if authorization.startswith("Bearer "):
        token = authorization[7:]

    # Parsowanie wielu kluczy (oddzielonych przecinkami)
    valid_keys = [key.strip() for key in api_key_value.split(",") if key.strip()]

    if token not in valid_keys:
        raise HTTPException(
            status_code=401,
            detail="Invalid API Key"
        )

    return True
