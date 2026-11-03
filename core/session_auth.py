"""
Moduł uwierzytelniania sesją
Logowanie oparte na sesji
"""
import secrets
from functools import wraps
from typing import Optional
from fastapi import HTTPException, Request, Response
from fastapi.responses import RedirectResponse


def generate_session_secret() -> str:
    """Generuje losowy klucz sesji"""
    return secrets.token_hex(32)


def is_logged_in(request: Request) -> bool:
    """Sprawdza, czy użytkownik jest zalogowany"""
    return request.session.get("authenticated", False)


def login_user(request: Request):
    """Oznacza użytkownika jako zalogowanego"""
    request.session["authenticated"] = True


def logout_user(request: Request):
    """Czyści stan zalogowania użytkownika"""
    request.session.clear()


def require_login(redirect_to_login: bool = True):
    """
    Dekorator wymagający zalogowania

    Args:
        redirect_to_login: czy przekierować na stronę logowania, gdy brak logowania (domyślnie True)
                          przy False zwracany jest błąd 404
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, request: Request, **kwargs):
            if not is_logged_in(request):
                if redirect_to_login:
                    accept_header = (request.headers.get("accept") or "").lower()
                    wants_html = "text/html" in accept_header or request.url.path.endswith("/html")

                    if wants_html:
                        # Usunięcie ewentualnie powtórzonego PATH_PREFIX z URL
                        # Unikanie wielokrotnego prefiksu w ścieżce przekierowania
                        path = request.url.path

                        # Obsługa przypadku pustego PATH_PREFIX w main
                        import main
                        prefix = main.PATH_PREFIX

                        if prefix:
                            login_url = f"/{prefix}/login"
                        else:
                            login_url = "/login"

                        return RedirectResponse(url=login_url, status_code=302)

                raise HTTPException(401, "Unauthorized")

            return await func(*args, request=request, **kwargs)
        return wrapper
    return decorator
