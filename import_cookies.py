"""Import ciasteczek Gemini Business (business.gemini.google) do lokalnego proxy.

Użycie:
  python import_cookies.py <plik_cookies.json> "<adres strony Gemini z paska przeglądarki>"

Przykład:
  python import_cookies.py business.gemini.google_cookies.json "https://business.gemini.google/home/cid/xxxx-xxxx?csesidx=123456"

Skrypt można uruchamiać wielokrotnie. Przy odświeżaniu ciasteczek nadpisuje to samo konto.
Wymaga tylko Pythona 3.8+ (bez dodatkowych bibliotek). Proxy musi być uruchomione (start.bat).
"""
from __future__ import annotations

import argparse
import datetime as dt
import http.cookiejar
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
BEIJING = dt.timezone(dt.timedelta(hours=8))  # proxy liczy ważność konta w tej strefie


def fail(msg: str) -> None:
    print(f"BŁĄD: {msg}", file=sys.stderr)
    sys.exit(1)


def read_env_value(key: str) -> str | None:
    env = HERE / ".env"
    if not env.exists():
        return None
    for line in env.read_text(encoding="utf-8").splitlines():
        if line.strip().startswith(f"{key}="):
            return line.split("=", 1)[1].strip()
    return None


def load_cookies(path: Path) -> tuple[dict[str, str], float | None]:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        fail(f"nie mogę odczytać {path}: {exc}")
    values: dict[str, str] = {}
    expiry = None
    if isinstance(data, dict):  # format {"nazwa": "wartość"}
        values = {str(k): str(v) for k, v in data.items()}
    elif isinstance(data, list):  # eksport z rozszerzenia Cookie-Editor
        for c in data:
            if isinstance(c, dict) and "name" in c:
                values[c["name"]] = str(c.get("value", ""))
                if c["name"] == "__Secure-C_SES":
                    expiry = c.get("expirationDate") or c.get("expires")
    else:
        fail("nieznany format pliku z ciasteczkami")
    return values, expiry


def parse_page_url(url: str) -> tuple[str, str]:
    cid = re.search(r"/cid/([0-9a-fA-F-]{8,})", url)
    cses = re.search(r"[?&]csesidx=(\d+)", url)
    if not cid or not cses:
        fail(
            "w adresie brakuje /cid/... albo csesidx=...\n"
            "Skopiuj cały adres z paska przeglądarki po zalogowaniu na business.gemini.google"
        )
    return cid.group(1), cses.group(1)


def main() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    p = argparse.ArgumentParser(description="Import ciasteczek Gemini Business do proxy")
    p.add_argument("cookies_file", help="plik JSON z ciasteczkami (eksport Cookie-Editor)")
    p.add_argument("page_url", help="pełny adres strony business.gemini.google z /cid/ i csesidx=")
    p.add_argument("--id", default="konto_1", help="nazwa konta w proxy (domyślnie konto_1)")
    p.add_argument("--proxy", default="http://localhost:7860", help="adres proxy")
    p.add_argument("--admin-key", default=None, help="hasło panelu (domyślnie z pliku .env)")
    args = p.parse_args()

    cookies, expiry = load_cookies(Path(args.cookies_file))
    ses = cookies.get("__Secure-C_SES", "").strip()
    oses = cookies.get("__Host-C_OSES", "").strip()
    if not ses:
        fail(
            "w pliku nie ma ciasteczka __Secure-C_SES.\n"
            "Eksportuj ciasteczka będąc na stronie business.gemini.google (nie gemini.google.com)."
        )
    if not oses:
        print("UWAGA: brak __Host-C_OSES. Próbuję bez niego, ale zwykle jest potrzebne.")

    config_id, csesidx = parse_page_url(args.page_url)

    if expiry:
        expires_dt = dt.datetime.fromtimestamp(float(expiry), tz=BEIJING)
    else:
        expires_dt = dt.datetime.now(tz=BEIJING) + dt.timedelta(hours=12)
        print("UWAGA: brak daty ważności w pliku, zakładam 12 godzin.")
    expires_at = expires_dt.strftime("%Y-%m-%d %H:%M:%S")

    admin_key = args.admin_key or read_env_value("ADMIN_KEY")
    if not admin_key:
        fail("brak hasła panelu. Uruchom najpierw start.bat (tworzy plik .env).")

    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    base = args.proxy.rstrip("/")

    def call(method: str, path: str, body: bytes | None = None, ctype: str | None = None):
        req = urllib.request.Request(base + path, data=body, method=method)
        if ctype:
            req.add_header("Content-Type", ctype)
        try:
            with opener.open(req, timeout=30) as r:
                return json.loads(r.read().decode("utf-8") or "{}")
        except urllib.error.HTTPError as e:
            fail(f"{method} {path} -> HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:300]}")
        except urllib.error.URLError as e:
            fail(f"nie mogę połączyć się z proxy ({base}). Czy działa start.bat? ({e.reason})")

    call("POST", "/login", urllib.parse.urlencode({"admin_key": admin_key}).encode(),
         "application/x-www-form-urlencoded")

    existing = call("GET", "/admin/accounts-config").get("accounts") or []
    account = {
        "id": args.id,
        "secure_c_ses": ses,
        "host_c_oses": oses,
        "csesidx": csesidx,
        "config_id": config_id,
        "expires_at": expires_at,
    }
    merged = [a for a in existing if a.get("id") != args.id] + [account]
    call("PUT", "/admin/accounts-config", json.dumps(merged).encode(), "application/json")

    listing = call("GET", "/admin/accounts?page=1&page_size=50")
    for a in listing.get("accounts", []):
        if a.get("id") == args.id:
            hours = a.get("remaining_hours")
            left = f"{hours:.1f} h" if isinstance(hours, (int, float)) else "nieznane"
            print(f"OK: konto '{args.id}' zaimportowane, status: {a['state']['code']}, "
                  f"ważne jeszcze: {left} (do {expires_at} czasu UTC+8)")
            break
    else:
        print("Konto zapisane, ale nie widać go na liście. Sprawdź panel http://localhost:7860/")


if __name__ == "__main__":
    main()
