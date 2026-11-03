"""Moduł zarządzania kontami

Odpowiada za konfigurację kont, koordynację wielu kont i pamięć podręczną sesji
"""
import asyncio
import json
import logging
import os
import random
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, TYPE_CHECKING, Iterable

from fastapi import HTTPException

# Import warstwy przechowywania (obsługa bazy danych)
from core import storage

if TYPE_CHECKING:
    from core.jwt import JWTManager

logger = logging.getLogger(__name__)

# Nazwy błędów HTTP
HTTP_ERROR_NAMES = {
    400: "Błąd parametrów",
    401: "Błąd uwierzytelnienia",
    403: "Brak uprawnień",
    429: "Przekroczono limit",
    502: "Błąd bramki",
    503: "Usługa niedostępna"
}

# Definicje typów limitów (quota)
QUOTA_TYPES = {
    "text": "Rozmowa",
    "images": "Obrazy",
    "videos": "Wideo"
}

@dataclass
class AccountConfig:
    """Konfiguracja pojedynczego konta"""
    account_id: str
    secure_c_ses: str
    host_c_oses: Optional[str]
    csesidx: str
    config_id: str
    expires_at: Optional[str] = None  # Czas wygaśnięcia konta (format: "2025-12-23 10:59:21")
    disabled: bool = False  # Status wyłączenia ręcznego
    trial_end: Optional[str] = None  # Koniec okresu próbnego (format: "2026-03-25", niezależnie od wygaśnięcia cookie)

    def get_remaining_hours(self) -> Optional[float]:
        """Oblicza pozostałe godziny konta"""
        if not self.expires_at:
            return None
        try:
            # Parsowanie czasu wygaśnięcia (zakładając czas pekiński)
            beijing_tz = timezone(timedelta(hours=8))
            expire_time = datetime.strptime(self.expires_at, "%Y-%m-%d %H:%M:%S")
            expire_time = expire_time.replace(tzinfo=beijing_tz)

            # Aktualny czas (czas pekiński)
            now = datetime.now(beijing_tz)

            # Obliczanie czasu pozostałego
            remaining = (expire_time - now).total_seconds() / 3600
            return remaining
        except Exception:
            return None

    def is_expired(self) -> bool:
        """Sprawdza, czy konto wygasło"""
        remaining = self.get_remaining_hours()
        if remaining is None:
            return False  # Brak ustawionego czasu wygaśnięcia – domyślnie nie wygasa
        return remaining <= 0

    def get_trial_days_remaining(self) -> Optional[int]:
        """Oblicza pozostałe dni okresu próbnego (na podstawie pola trial_end)"""
        if not self.trial_end:
            return None
        try:
            beijing_tz = timezone(timedelta(hours=8))
            end_date = datetime.strptime(self.trial_end, "%Y-%m-%d")
            end_date = end_date.replace(tzinfo=beijing_tz)
            now = datetime.now(beijing_tz)
            remaining = (end_date.date() - now.date()).days
            return max(0, remaining)
        except Exception:
            return None


@dataclass(frozen=True)
class CooldownConfig:
    text: int
    images: int
    videos: int


@dataclass(frozen=True)
class RetryPolicy:
    cooldowns: CooldownConfig


def format_account_expiration(remaining_hours: Optional[float]) -> tuple:
    """
    Formatuje wyświetlanie czasu wygaśnięcia konta (na podstawie 12-godzinnego cyklu)

    Args:
        remaining_hours: pozostałe godziny (None oznacza brak ustawionego czasu wygaśnięcia)

    Returns:
        krotek (status, status_color, expire_display)
    """
    if remaining_hours is None:
        # Brak ustawionego czasu wygaśnięcia – wyświetlane jako "Nie ustawiono"
        return ("Nie ustawiono", "#9e9e9e", "Nie ustawiono")
    elif remaining_hours <= 0:
        return ("Wygasło", "#f44336", "Wygasło")
    elif remaining_hours < 3:  # mniej niż 3 godziny
        return ("Wkrótce wygaśnie", "#ff9800", f"{remaining_hours:.1f} godz.")
    else:  # 3 godziny i więcej – zawsze wyświetlamy godziny
        return ("Aktywne", "#4caf50", f"{remaining_hours:.1f} godz.")


class AccountManager:
    """Menedżer pojedynczego konta"""
    def __init__(
        self,
        config: AccountConfig,
        http_client,
        user_agent: str,
        retry_policy: RetryPolicy,
    ):
        self.config = config
        self.http_client = http_client
        self.user_agent = user_agent
        # Konfiguracja czasu ostygnięcia (cooldown)
        self.rate_limit_cooldown_seconds = retry_policy.cooldowns.text  # zgodność wsteczna
        self.text_rate_limit_cooldown_seconds = retry_policy.cooldowns.text
        self.images_rate_limit_cooldown_seconds = retry_policy.cooldowns.images
        self.videos_rate_limit_cooldown_seconds = retry_policy.cooldowns.videos
        self.jwt_manager: Optional['JWTManager'] = None  # inicjalizacja leniwa
        self.is_available = True
        self.last_error_time = 0.0  # zachowane do statystyk
        self.quota_cooldowns: Dict[str, float] = {}  # znaczniki czasu cooldownu wg typu limitu
        self.daily_usage: Dict[str, int] = {"text": 0, "images": 0, "videos": 0}  # dzienne liczniki użycia
        self.daily_usage_date: str = ""  # data licznika (czas pekiński, format "2026-02-24")
        self.conversation_count = 0  # łączna liczba sukcesów (do wyświetlanania statystyk)
        self.failure_count = 0  # łączna liczba niepowodzeń (do wyświetlanania statystyk)
        self.session_usage_count = 0  # liczba użyć od startu (do wyważonego round-robin)
        self.disabled_reason: Optional[str] = None  # powód automatycznego wyłączenia (np. "403 Access Restricted")

    def handle_non_http_error(self, error_context: str = "", request_id: str = "", quota_type: Optional[str] = None) -> None:
        """
        Wspólna obsługa błędów spoza HTTP (błędy sieci, błędy parsowania itd.) – tylko logowanie, bez cooldownu

        Args:
            error_context: kontekst błędu (np. "Pobieranie JWT", "Żądanie czatu")
            request_id: ID żądania (do logów)
            quota_type: typ limitu (parametr zachowany dla zgodności interfejsu)

        Uwaga: błędy sieci i przekroczenia czasu to problemy tymczasowe – należy
        przełączyć konto i ponowić żądanie, nie oznaczając limitu cooldownem
        """
        req_tag = f"[req_{request_id}] " if request_id else ""

        # Tylko logowanie, bez cooldownu
        # Błędy sieci są tymczasowe – przełączamy konto i ponawiamy
        logger.warning(
            f"[ACCOUNT] [{self.config.account_id}] {req_tag}"
            f"{error_context} nie powiodło się, przełączanie konta i ponawianie (bez cooldownu)"
        )

    def _get_quota_cooldown_seconds(self, quota_type: Optional[str]) -> int:
        if quota_type == "images":
            return self.images_rate_limit_cooldown_seconds
        if quota_type == "videos":
            return self.videos_rate_limit_cooldown_seconds
        return self.text_rate_limit_cooldown_seconds

    def apply_retry_policy(self, retry_policy: RetryPolicy) -> None:
        """Apply updated retry policy to this account manager."""
        self.rate_limit_cooldown_seconds = retry_policy.cooldowns.text  # zgodność wsteczna
        self.text_rate_limit_cooldown_seconds = retry_policy.cooldowns.text
        self.images_rate_limit_cooldown_seconds = retry_policy.cooldowns.images
        self.videos_rate_limit_cooldown_seconds = retry_policy.cooldowns.videos

    def _get_quota_period(self) -> str:
        """Zwraca identyfikator bieżącego okresu limitu (granica 16:00 czasu pekińskiego, zgodna z resetem o północy czasu pacznego Google)"""
        beijing_tz = timezone(timedelta(hours=8))
        now = datetime.now(beijing_tz)
        # przed 16:00 – okres limitu należy do poprzedniego dnia, po 16:00 – do bieżącego dnia
        if now.hour < 16:
            period_date = now.date() - timedelta(days=1)
        else:
            period_date = now.date()
        return period_date.strftime("%Y-%m-%d")

    def _reset_daily_usage_if_needed(self) -> None:
        """Automatycznie resetuje dzienne liczniki po zmianie okresu limitu (leniwy reset, odświeżenie o 16:00 czasu pekińskiego)"""
        period = self._get_quota_period()
        if self.daily_usage_date != period:
            self.daily_usage = {"text": 0, "images": 0, "videos": 0}
            self.daily_usage_date = period

    def increment_daily_usage(self, quota_type: str) -> None:
        """Zwiększa dzienny licznik użycia po pomyślnym żądaniu"""
        if quota_type not in QUOTA_TYPES:
            return
        self._reset_daily_usage_if_needed()
        self.daily_usage[quota_type] += 1

    def handle_http_error(self, status_code: int, error_detail: str = "", request_id: str = "", quota_type: Optional[str] = None) -> None:
        """
        Wspólna obsługa błędów HTTP – klasyfikacja wg typu błędu

        Args:
            status_code: kod statusu HTTP
            error_detail: szczegóły błędu
            request_id: ID żądania (do logów)
            quota_type: typ limitu ("text", "images", "videos"), do cooldownu wg typu

        Logika obsługi:
            - 400: błąd parametrów, nie liczy się jako niepowodzenie (problem po stronie klienta)
            - 401/403: błąd uwierzytelnienia, cooldown limitu text (równoważny cooldownowi całego konta)
            - 429: cooldown wg typu limitu (wyczerpany limit)
            - 502/503/504/inne: tylko logowanie, bez cooldownu (tymczasowy błąd serwera – przełącz konto i ponów)
        """
        req_tag = f"[req_{request_id}] " if request_id else ""

        # 400 błąd parametrów: nie liczy się jako niepowodzenie (problem po stronie klienta)
        if status_code == 400:
            logger.warning(
                f"[ACCOUNT] [{self.config.account_id}] {req_tag}"
                f"HTTP 400 – błąd parametrów (nie liczone jako niepowodzenie){': ' + error_detail[:100] if error_detail else ''}"
            )
            return

        # 403 brak uprawnień: Google zwraca 403, co oznacza ograniczony dostęp do konta – automatyczne wyłączenie
        # (403 z odświeżenia JWT lub z wywołania API to trwały blokada, nie problem tymczasowy)
        if status_code == 403:
            self.config.disabled = True
            self.disabled_reason = "403 Access Restricted"
            logger.error(
                f"[ACCOUNT] [{self.config.account_id}] {req_tag}"
                f"⛔ Konto napotkało błąd uprawnień 403 – zostało automatycznie wyłączone"
                f"{': ' + error_detail[:200] if error_detail else ''}"
            )
            return

        # 401 błąd uwierzytelnienia: cooldown limitu text (równoważny cooldownowi całego konta, z automatycznym powrotem)
        if status_code == 401:
            self.quota_cooldowns["text"] = time.time()
            cooldown_seconds = self.text_rate_limit_cooldown_seconds
            logger.warning(
                f"[ACCOUNT] [{self.config.account_id}] {req_tag}"
                f"Spotkano błąd uwierzytelnienia – konto odpocznie {cooldown_seconds} s i wróci automatycznie"
                f"{': ' + error_detail[:100] if error_detail else ''}"
            )
            return

        # 429 wyczerpany limit: cooldown wg typu limitu
        if status_code == 429:
            if not quota_type or quota_type not in QUOTA_TYPES:
                quota_type = "text"

            self.quota_cooldowns[quota_type] = time.time()
            cooldown_seconds = self._get_quota_cooldown_seconds(quota_type)
            logger.warning(
                f"[ACCOUNT] [{self.config.account_id}] {req_tag}"
                f"Spotkano błąd 429 (limit) – limit {QUOTA_TYPES[quota_type]} odpocznie {cooldown_seconds} s i wróci automatycznie"
                f"{': ' + error_detail[:100] if error_detail else ''}"
            )
            return

        # 502/503/504/inne błędy: tylko logowanie, bez cooldownu
        # To tymczasowe błędy serwera – ponawiamy przez przełączenie konta, bez oznaczania limitu
        error_type = HTTP_ERROR_NAMES.get(status_code, f"HTTP {status_code}")
        logger.warning(
            f"[ACCOUNT] [{self.config.account_id}] {req_tag}"
            f"Spotkano błąd {error_type} – przełączanie konta i ponawianie (bez cooldownu)"
            f"{': ' + error_detail[:100] if error_detail else ''}"
        )

    def is_quota_available(self, quota_type: str) -> bool:
        """Sprawdza, czy podany limit jest dostępny (najpierw dzienny limit, potem cooldown)."""
        if quota_type not in QUOTA_TYPES:
            return True

        # Aktywne sprawdzanie licznika limitu
        from core.config import config
        quota_limits = config.quota_limits
        if quota_limits.enabled:
            self._reset_daily_usage_if_needed()
            limit = getattr(quota_limits, f"{quota_type}_daily_limit", 0)
            if limit > 0 and self.daily_usage.get(quota_type, 0) >= limit:
                return False

        # Pasywne sprawdzanie cooldownu (zabezpieczenie)
        cooldown_time = self.quota_cooldowns.get(quota_type)
        if not cooldown_time:
            return True

        elapsed = time.time() - cooldown_time
        cooldown_seconds = self._get_quota_cooldown_seconds(quota_type)
        if elapsed < cooldown_seconds:
            return False

        # Cooldown wygasł – czyszczenie
        del self.quota_cooldowns[quota_type]
        return True

    def are_quotas_available(self, quota_types: Optional[Iterable[str]] = None) -> bool:
        """
        Sprawdza, czy wszystkie podane typy limitów są dostępne.

        Uwaga: jeśli limit rozmowy jest ograniczony, żaden limit nie jest dostępny
        (rozmowa to funkcja podstawowa)
        """
        if not quota_types:
            return True
        if isinstance(quota_types, str):
            quota_types = [quota_types]

        # Jeśli limit rozmowy jest ograniczony, żaden limit nie jest dostępny
        if not self.is_quota_available("text"):
            return False

        # Sprawdzenie pozostałych limitów
        return all(self.is_quota_available(qt) for qt in quota_types if qt != "text")

    async def get_jwt(self, request_id: str = "") -> str:
        """Pobiera token JWT (z obsługą błędów)"""
        # Sprawdzenie, czy konto wygasło
        if self.config.is_expired():
            self.is_available = False
            logger.warning(f"[ACCOUNT] [{self.config.account_id}] Konto wygasło – zostało automatycznie wyłączone")
            raise HTTPException(403, f"Account {self.config.account_id} has expired")

        try:
            if self.jwt_manager is None:
                # Leniwa inicjalizacja JWTManager (unikanie cyklicznych zależności)
                from core.jwt import JWTManager
                self.jwt_manager = JWTManager(self.config, self.http_client, self.user_agent)
            jwt = await self.jwt_manager.get(request_id)
            self.is_available = True
            return jwt
        except Exception as e:
            # Wspólny punkt obsługi błędów
            if isinstance(e, HTTPException):
                self.handle_http_error(e.status_code, str(e.detail) if hasattr(e, 'detail') else "", request_id)
            else:
                self.handle_non_http_error("Pobieranie JWT", request_id)
            raise

    def should_retry(self) -> bool:
        """Sprawdza, czy konto można ponownie użyć – wersja uproszczona: konto jest zawsze dostępne (sterowane cooldownem limitów)"""
        # Konto samo w sobie jest zawsze dostępne; konkretne funkcje kontroluje cooldown limitów
        return True

    def get_cooldown_info(self) -> tuple[int, str | None]:
        """Zwraca informacje o cooldownie konta (tylko cooldown limitów)"""
        current_time = time.time()

        # Sprawdzenie cooldownów limitów (wybór najdłuższego pozostałego czasu)
        max_quota_remaining = 0
        limited_quota_types = []  # przechowuje typy limitów (text/images/videos)
        quota_icons = {"text": "💬", "images": "🎨", "videos": "🎬"}

        for quota_type in QUOTA_TYPES:
            if quota_type in self.quota_cooldowns:
                cooldown_time = self.quota_cooldowns[quota_type]
                elapsed = current_time - cooldown_time
                cooldown_seconds = self._get_quota_cooldown_seconds(quota_type)
                if elapsed < cooldown_seconds:
                    remaining = int(cooldown_seconds - elapsed)
                    if remaining > max_quota_remaining:
                        max_quota_remaining = remaining
                    limited_quota_types.append(quota_type)

        # Jeśli jest cooldown limitu, zwracamy najdłuższy czas i uproszczony opis
        if max_quota_remaining > 0:
            # Generowanie zestawu ikon emoji
            icons = "".join([quota_icons[qt] for qt in limited_quota_types])

            # Sprawdzenie, czy wszystko jest na cooldownie
            if len(limited_quota_types) == 3:
                return (max_quota_remaining, f"{icons} wszystkie na cooldownie")
            elif len(limited_quota_types) == 1:
                # Pojedynczy limit na cooldownie
                quota_name = QUOTA_TYPES[limited_quota_types[0]]
                return (max_quota_remaining, f"{icons} cooldown: {quota_name}")
            else:
                # Kilka limitów na cooldownie (ale nie wszystkie)
                quota_names = "/".join([QUOTA_TYPES[qt] for qt in limited_quota_types])
                return (max_quota_remaining, f"{icons} cooldown: {quota_names}")

        # Brak cooldownu – zwracamy stan prawidłowy
        return (0, None)

    def get_quota_status(self) -> Dict[str, any]:
        """
        Zwraca stan limitów (wykrywanie pasywne + aktywne liczniki)

        Returns:
            {
                "quotas": {
                    "text": {"available": bool, "remaining_seconds": int, "daily_used": int, "daily_limit": int},
                    "images": {"available": bool, "remaining_seconds": int, "daily_used": int, "daily_limit": int},
                    "videos": {"available": bool, "remaining_seconds": int, "daily_used": int, "daily_limit": int}
                },
                "limited_count": int,  # liczba ograniczonych limitów
                "total_count": int,    # łączna liczba limitów
                "is_expired": bool     # czy konto wygasło/jest wyłączone
            }
        """
        # Pobranie konfiguracji limitów
        from core.config import config as app_config
        quota_limits = app_config.quota_limits

        # Sprawdzenie, czy konto wygasło lub zostało wyłączone
        is_expired = self.config.is_expired() or self.config.disabled
        if is_expired:
            # Konto wygasło lub jest wyłączone – wszystkie limity niedostępne
            quotas = {quota_type: {"available": False} for quota_type in QUOTA_TYPES}
            return {
                "quotas": quotas,
                "limited_count": len(QUOTA_TYPES),
                "total_count": len(QUOTA_TYPES),
                "is_expired": True
            }

        current_time = time.time()
        self._reset_daily_usage_if_needed()

        quotas = {}
        limited_count = 0
        expired_quotas = []  # zbieranie limitów, których cooldown wygasł
        text_limited = False  # czy limit rozmowy jest ograniczony

        # Pierwsza pętla: sprawdzenie stanu wszystkich limitów
        for quota_type in QUOTA_TYPES:
            quota_info: Dict[str, any] = {}

            # Dodanie informacji o dziennym użyciu
            if quota_limits.enabled:
                daily_limit = getattr(quota_limits, f"{quota_type}_daily_limit", 0)
                quota_info["daily_used"] = self.daily_usage.get(quota_type, 0)
                quota_info["daily_limit"] = daily_limit

                # Sprawdzenie dziennego limitu
                if daily_limit > 0 and quota_info["daily_used"] >= daily_limit:
                    quota_info["available"] = False
                    quota_info["reason"] = "Dzienny limit wyczerpany"
                    limited_count += 1
                    if quota_type == "text":
                        text_limited = True
                    quotas[quota_type] = quota_info
                    continue

            # Sprawdzenie pasywnego cooldownu
            if quota_type in self.quota_cooldowns:
                cooldown_time = self.quota_cooldowns[quota_type]
                elapsed = current_time - cooldown_time
                cooldown_seconds = self._get_quota_cooldown_seconds(quota_type)
                if elapsed < cooldown_seconds:
                    remaining = int(cooldown_seconds - elapsed)
                    quota_info["available"] = False
                    quota_info["remaining_seconds"] = remaining
                    limited_count += 1
                    if quota_type == "text":
                        text_limited = True
                    quotas[quota_type] = quota_info
                    continue
                else:
                    expired_quotas.append(quota_type)

            quota_info["available"] = True
            quotas[quota_type] = quota_info

        # Usuwanie wygasłych cooldownów limitów
        for quota_type in expired_quotas:
            del self.quota_cooldowns[quota_type]

        # Jeśli limit rozmowy jest ograniczony, wszystkie limity oznaczane są jako niedostępne
        # (rozmowa to funkcja podstawowa)
        if text_limited:
            for quota_type in QUOTA_TYPES:
                if quota_type != "text" and quotas[quota_type].get("available", False):
                    quotas[quota_type]["available"] = False
                    quotas[quota_type]["reason"] = "Limit rozmowy ograniczony"
                    limited_count += 1

        return {
            "quotas": quotas,
            "limited_count": limited_count,
            "total_count": len(QUOTA_TYPES),
            "is_expired": False
        }


class MultiAccountManager:
    """Koordynator wielu kont"""
    def __init__(self, session_cache_ttl_seconds: int):
        self.accounts: Dict[str, AccountManager] = {}
        self.account_list: List[str] = []  # lista ID kont (do round-robin)
        self.current_index = 0
        self._cache_lock = asyncio.Lock()  # blokada wyłącznie dla operacji na cache
        self._counter_lock = threading.Lock()  # blokada licznika round-robin
        self._request_counter = 0  # licznik żądań
        self._last_account_count = 0  # liczba dostępnych kont
        # Globalna pamięć podręczna sesji: {conv_key: {"account_id": str, "session_id": str, "updated_at": float}}
        self.global_session_cache: Dict[str, dict] = {}
        self.cache_max_size = 1000  # maksymalna liczba wpisów cache
        self.cache_ttl = session_cache_ttl_seconds  # czas życia cache (sekundy)
        # Blokady na poziomie sesji: zapobieganie konfliktom równoległych żądań jednej rozmowy
        self._session_locks: Dict[str, asyncio.Lock] = {}
        self._session_locks_lock = asyncio.Lock()  # blokada chroniąca słownik blokad
        self._session_locks_max_size = 2000  # maksymalna liczba blokad

    def _clean_expired_cache(self):
        """Czyszczenie wygasłych wpisów cache"""
        current_time = time.time()
        expired_keys = [
            key for key, value in self.global_session_cache.items()
            if current_time - value["updated_at"] > self.cache_ttl
        ]
        for key in expired_keys:
            del self.global_session_cache[key]
        if expired_keys:
            logger.info(f"[CACHE] Wyczyszczono {len(expired_keys)} wygasłych wpisów cache sesji")

    def _ensure_cache_size(self):
        """Zapewnienie, że cache nie przekroczy maksymalnego rozmiaru (strategia LRU)"""
        if len(self.global_session_cache) > self.cache_max_size:
            # Sortowanie wg czasu aktualizacji i usuwanie najstarszych 20%
            sorted_items = sorted(
                self.global_session_cache.items(),
                key=lambda x: x[1]["updated_at"]
            )
            remove_count = len(sorted_items) - int(self.cache_max_size * 0.8)
            for key, _ in sorted_items[:remove_count]:
                del self.global_session_cache[key]
            logger.info(f"[CACHE] Czyszczenie LRU: usunięto {remove_count} najstarszych wpisów cache sesji")

    async def start_background_cleanup(self):
        """Uruchomienie zadania czyszczenia cache w tle (co 5 minut)"""
        try:
            while True:
                await asyncio.sleep(300)  # 5 minut
                async with self._cache_lock:
                    self._clean_expired_cache()
                    self._ensure_cache_size()
        except asyncio.CancelledError:
            logger.info("[CACHE] Zadanie czyszczenia w tle zatrzymane")
        except Exception as e:
            logger.error(f"[CACHE] Zadanie czyszczenia w tle zakończone błędem: {e}")

    async def set_session_cache(self, conv_key: str, account_id: str, session_id: str):
        """Bezpieczne (wątkowo) ustawienie cache sesji"""
        async with self._cache_lock:
            self.global_session_cache[conv_key] = {
                "account_id": account_id,
                "session_id": session_id,
                "updated_at": time.time()
            }
            # Sprawdzenie rozmiaru cache
            self._ensure_cache_size()

    async def update_session_time(self, conv_key: str):
        """Bezpieczne (wątkowo) aktualizowanie znacznika czasu sesji"""
        async with self._cache_lock:
            if conv_key in self.global_session_cache:
                self.global_session_cache[conv_key]["updated_at"] = time.time()

    async def acquire_session_lock(self, conv_key: str) -> asyncio.Lock:
        """Pobranie blokady dla danej rozmowy (zapobieganie konfliktom równoległych żądań)"""
        async with self._session_locks_lock:
            # Usuwanie nadmiaru blokad (LRU: usuwanie blokad spoza cache)
            if len(self._session_locks) > self._session_locks_max_size:
                # Zachowanie tylko blokad obecnych w cache
                valid_keys = set(self.global_session_cache.keys())
                keys_to_remove = [k for k in self._session_locks if k not in valid_keys]
                for k in keys_to_remove[:len(keys_to_remove)//2]:  # usuwanie połowy nieprawidłowych blokad
                    del self._session_locks[k]

            if conv_key not in self._session_locks:
                self._session_locks[conv_key] = asyncio.Lock()
            return self._session_locks[conv_key]

    def update_http_client(self, http_client):
        """Aktualizacja http_client używanego przez wszystkie konta (po zmianie proxy – odbudowa klienta)"""
        for account_mgr in self.accounts.values():
            account_mgr.http_client = http_client
            if account_mgr.jwt_manager is not None:
                account_mgr.jwt_manager.http_client = http_client

    def add_account(
        self,
        config: AccountConfig,
        http_client,
        user_agent: str,
        retry_policy: RetryPolicy,
        global_stats: dict,
    ):
        """Dodanie konta"""
        manager = AccountManager(config, http_client, user_agent, retry_policy)
        # Wczytanie liczby rozmów ze statystyk
        if "account_conversations" in global_stats:
            manager.conversation_count = global_stats["account_conversations"].get(config.account_id, 0)
        if "account_failures" in global_stats:
            manager.failure_count = global_stats["account_failures"].get(config.account_id, 0)
        self.accounts[config.account_id] = manager
        self.account_list.append(config.account_id)
        logger.debug(f"[MULTI] [ACCOUNT] Dodano konto: {config.account_id}")

    def get_available_accounts(
        self,
        required_quota_types: Optional[Iterable[str]] = None
    ) -> List[AccountManager]:
        """Zwraca listę dostępnych kont (z pominięciem wyłączonych, wygasłych i na cooldownie)

        Args:
            required_quota_types: wymagane typy limitów (np. ["text"], ["images"], ["text", "videos"])

        Returns:
            lista dostępnych kont

        Reguły filtrowania:
            1. disabled=True → pominięte (wyłączone ręcznie)
            2. is_expired() → pominięte (konto wygasłe)
            3. are_quotas_available() → pominięte (limity na cooldownie)
        """
        available = []

        for acc in self.accounts.values():
            # 1. Sprawdzenie wyłączenia ręcznego
            if acc.config.disabled:
                continue

            # 2. Sprawdzenie, czy konto wygasło
            if acc.config.is_expired():
                continue

            # 3. Sprawdzenie dostępności limitów (w tym cooldownów)
            if not acc.are_quotas_available(required_quota_types):
                continue

            available.append(acc)

        return available

    async def get_account(
        self,
        account_id: Optional[str] = None,
        request_id: str = "",
        required_quota_types: Optional[Iterable[str]] = None
    ) -> AccountManager:
        """Pobranie konta – round-robin

        Args:
            account_id: wskazane ID konta (opcjonalne; jeśli podane, zwracane jest to konto)
            request_id: ID żądania (do logów)
            required_quota_types: wymagane typy limitów

        Returns:
            dostępny menedżer konta

        Raises:
            HTTPException(404): wskazane konto nie istnieje
            HTTPException(503): brak dostępnych kont
        """
        req_tag = f"[req_{request_id}] " if request_id else ""

        # Przy wskazanym ID konta zwracamy je bezpośrednio
        if account_id:
            if account_id not in self.accounts:
                raise HTTPException(404, f"Account {account_id} not found")
            account = self.accounts[account_id]
            if not account.should_retry():
                raise HTTPException(503, f"Account {account_id} temporarily unavailable")
            if not account.are_quotas_available(required_quota_types):
                raise HTTPException(503, f"Account {account_id} quota temporarily unavailable")
            return account

        # Pobranie listy dostępnych kont
        available_accounts = self.get_available_accounts(required_quota_types)

        if not available_accounts:
            raise HTTPException(503, "No available accounts")

        # Wybór round-robin
        with self._counter_lock:
            if len(available_accounts) != self._last_account_count:
                self._request_counter = random.randint(0, 999999)
                self._last_account_count = len(available_accounts)
            index = self._request_counter % len(available_accounts)
            self._request_counter += 1

        selected = available_accounts[index]
        selected.session_usage_count += 1

        logger.info(f"[MULTI] [ACCOUNT] {req_tag}Wybrano konto: {selected.config.account_id} "
                    f"(indeks: {index}/{len(available_accounts)}, użycia: {selected.session_usage_count})")
        return selected


# ---------- Zarządzanie konfiguracją ----------

def save_accounts_to_file(accounts_data: list):
    """Zapis konfiguracji kont (tylko tryb bazy danych)."""
    if not storage.is_database_enabled():
        raise RuntimeError("Database is not enabled")
    saved = storage.save_accounts_sync(accounts_data)
    if not saved:
        raise RuntimeError("Database write failed")


def load_accounts_from_source() -> list:
    """Wczytanie konfiguracji kont ze zmiennych środowiskowych lub bazy danych."""
    env_accounts = os.environ.get('ACCOUNTS_CONFIG')
    if env_accounts:
        try:
            accounts_data = json.loads(env_accounts)
            if accounts_data:
                logger.info(f"[CONFIG] Wczytano konfigurację ze zmiennej środowiskowej, łącznie {len(accounts_data)} kont")
            else:
                logger.warning("[CONFIG] Zmienna środowiskowa ACCOUNTS_CONFIG jest pusta")
            return accounts_data
        except Exception as e:
            logger.error(f"[CONFIG] Nie udało się wczytać ze zmiennej środowiskowej: {str(e)}")

    if storage.is_database_enabled():
        try:
            accounts_data = storage.load_accounts_sync()

            # Tryb ścisły: przy błędzie połączenia z bazą rzucamy wyjątek i blokujemy start aplikacji
            if accounts_data is None:
                logger.error("[CONFIG] ❌ Nie udało się połączyć z bazą danych")
                logger.error("[CONFIG] Sprawdź konfigurację DATABASE_URL lub połączenie sieciowe")
                raise RuntimeError("Nie udało się połączyć z bazą danych – aplikacja nie może się uruchomić")

            if accounts_data:
                logger.info(f"[CONFIG] Wczytano konfigurację z bazy danych, łącznie {len(accounts_data)} kont")
            else:
                logger.warning("[CONFIG] Konfiguracja kont w bazie danych jest pusta")
                logger.warning("[CONFIG] Najpierw zaimportuj konta w panelu administracyjnym albo podaj ACCOUNTS_CONFIG")

            return accounts_data
        except RuntimeError:
            # Rzucamy RuntimeError ponownie (błąd połączenia z bazą)
            raise
        except Exception as e:
            logger.error(f"[CONFIG] ❌ Nie udało się wczytać z bazy danych: {e}")
            raise RuntimeError(f"Nie udało się wczytać z bazy danych: {e}")

    logger.error("[CONFIG] Baza danych nie jest włączona i nie podano ACCOUNTS_CONFIG")
    return []


def get_account_id(acc: dict, index: int) -> str:
    """Pobranie ID konta (jeśli jest jawne, w przeciwnym razie generowane domyślne)"""
    return acc.get("id", f"account_{index}")


def load_multi_account_config(
    http_client,
    user_agent: str,
    retry_policy: RetryPolicy,
    session_cache_ttl_seconds: int,
    global_stats: dict
) -> MultiAccountManager:
    """Wczytanie konfiguracji wielu kont z pliku lub zmiennej środowiskowej"""
    manager = MultiAccountManager(session_cache_ttl_seconds)

    accounts_data = load_accounts_from_source()

    for i, acc in enumerate(accounts_data, 1):
        # Walidacja pól wymaganych
        required_fields = ["secure_c_ses", "csesidx", "config_id"]
        missing_fields = [f for f in required_fields if f not in acc]
        if missing_fields:
            raise ValueError(f"Konto {i} nie ma wymaganych pól: {', '.join(missing_fields)}")

        config = AccountConfig(
            account_id=get_account_id(acc, i),
            secure_c_ses=acc["secure_c_ses"],
            host_c_oses=acc.get("host_c_oses"),
            csesidx=acc["csesidx"],
            config_id=acc["config_id"],
            expires_at=acc.get("expires_at"),
            disabled=acc.get("disabled", False),  # odczyt statusu wyłączenia ręcznego, domyślnie False
            trial_end=acc.get("trial_end"),
        )

        # Sprawdzenie, czy konto wygasło (wygasłe również wczytujemy do panelu)
        is_expired = config.is_expired()
        if is_expired:
            logger.debug(f"[CONFIG] Konto {config.account_id} wygasło – mimo to wczytane do wyświetlenia")

        manager.add_account(config, http_client, user_agent, retry_policy, global_stats)

        # Odtworzenie stanu cooldownu i statystyk z bazy danych
        account_mgr = manager.accounts[config.account_id]
        if "quota_cooldowns" in acc:
            account_mgr.quota_cooldowns = dict(acc["quota_cooldowns"])
        if "conversation_count" in acc:
            account_mgr.conversation_count = int(acc.get("conversation_count", 0))
        if "failure_count" in acc:
            account_mgr.failure_count = int(acc.get("failure_count", 0))
        if "daily_usage" in acc:
            account_mgr.daily_usage = dict(acc["daily_usage"])
        if "daily_usage_date" in acc:
            account_mgr.daily_usage_date = str(acc.get("daily_usage_date", ""))

        if is_expired:
            manager.accounts[config.account_id].is_available = False

    if not manager.accounts:
        logger.warning(f"[CONFIG] Brak prawidłowej konfiguracji kont – usługa uruchomi się, ale nie będzie obsługiwać żądań; dodaj konta w panelu administracyjnym")
    else:
        logger.info(f"[CONFIG] Pomyślnie wczytano {len(manager.accounts)} kont")
    return manager


def reload_accounts(
    multi_account_mgr: MultiAccountManager,
    http_client,
    user_agent: str,
    retry_policy: RetryPolicy,
    session_cache_ttl_seconds: int,
    global_stats: dict
) -> MultiAccountManager:
    """Reload account config and preserve runtime cooldown/error state."""
    # Preserve stats + runtime state to avoid clearing cooldowns on reload.
    old_stats = {}
    for account_id, account_mgr in multi_account_mgr.accounts.items():
        old_stats[account_id] = {
            "conversation_count": account_mgr.conversation_count,
            "failure_count": account_mgr.failure_count,
            "is_available": account_mgr.is_available,
            "last_error_time": account_mgr.last_error_time,
            "session_usage_count": account_mgr.session_usage_count,
            "quota_cooldowns": dict(account_mgr.quota_cooldowns),
            "daily_usage": dict(account_mgr.daily_usage),
            "daily_usage_date": account_mgr.daily_usage_date,
        }

    # Clear session cache and reload config.
    multi_account_mgr.global_session_cache.clear()
    new_mgr = load_multi_account_config(
        http_client,
        user_agent,
        retry_policy,
        session_cache_ttl_seconds,
        global_stats
    )

    # Restore stats + runtime state.
    for account_id, stats in old_stats.items():
        if account_id in new_mgr.accounts:
            account_mgr = new_mgr.accounts[account_id]
            account_mgr.conversation_count = stats["conversation_count"]
            account_mgr.failure_count = stats.get("failure_count", 0)
            account_mgr.last_error_time = stats.get("last_error_time", 0.0)
            account_mgr.session_usage_count = stats.get("session_usage_count", 0)
            account_mgr.daily_usage = stats.get("daily_usage", {"text": 0, "images": 0, "videos": 0})
            account_mgr.daily_usage_date = stats.get("daily_usage_date", "")

            # Smart restore: consider new config's expired/disabled state
            old_available = stats.get("is_available", True)
            old_cooldowns = stats.get("quota_cooldowns", {})
            if account_mgr.config.is_expired() or account_mgr.config.disabled:
                # Still expired/disabled → preserve old state
                account_mgr.is_available = False
                account_mgr.quota_cooldowns = old_cooldowns
            elif not old_available and not old_cooldowns:
                # Was unavailable with no cooldowns (i.e. expired/disabled),
                # now recovered → mark available and clear cooldowns
                account_mgr.is_available = True
                account_mgr.quota_cooldowns = {}
                logger.info(f"[CONFIG] Account {account_id} recovered from expired state, cooldowns cleared")
            else:
                # Normal case: preserve runtime state (e.g. quota cooldowns)
                account_mgr.is_available = old_available
                account_mgr.quota_cooldowns = old_cooldowns

            logger.debug(f"[CONFIG] Account {account_id} refreshed; runtime state preserved")

    logger.info(
        f"[CONFIG] Reloaded config; accounts={len(new_mgr.accounts)}; cooldown/error state preserved"
    )
    return new_mgr


def update_accounts_config(
    accounts_data: list,
    multi_account_mgr: MultiAccountManager,
    http_client,
    user_agent: str,
    retry_policy: RetryPolicy,
    session_cache_ttl_seconds: int,
    global_stats: dict
) -> MultiAccountManager:
    """Aktualizacja konfiguracji kont (zapis do pliku i ponowne wczytanie)"""
    save_accounts_to_file(accounts_data)
    return reload_accounts(
        multi_account_mgr,
        http_client,
        user_agent,
        retry_policy,
        session_cache_ttl_seconds,
        global_stats
    )


def delete_account(
    account_id: str,
    multi_account_mgr: MultiAccountManager,
    http_client,
    user_agent: str,
    retry_policy: RetryPolicy,
    session_cache_ttl_seconds: int,
    global_stats: dict
) -> MultiAccountManager:
    """Usunięcie pojedynczego konta"""
    if storage.is_database_enabled():
        deleted = storage.delete_accounts_sync([account_id])
        if deleted <= 0:
            raise ValueError(f"Konto {account_id} nie istnieje")
        return reload_accounts(
            multi_account_mgr,
            http_client,
            user_agent,
            retry_policy,
            session_cache_ttl_seconds,
            global_stats
        )

    accounts_data = load_accounts_from_source()

    filtered = [
        acc for i, acc in enumerate(accounts_data, 1)
        if get_account_id(acc, i) != account_id
    ]

    if len(filtered) == len(accounts_data):
        raise ValueError(f"Konto {account_id} nie istnieje")

    save_accounts_to_file(filtered)
    return reload_accounts(
        multi_account_mgr,
        http_client,
        user_agent,
        retry_policy,
        session_cache_ttl_seconds,
        global_stats
    )


def update_account_disabled_status(
    account_id: str,
    disabled: bool,
    multi_account_mgr: MultiAccountManager,
) -> MultiAccountManager:
    """Aktualizacja statusu wyłączenia konta (wersja zoptymalizowana: priorytet dla bezpośredniego zapisu do bazy)."""
    if storage.is_database_enabled():
        updated = storage.update_account_disabled_sync(account_id, disabled)
        if not updated:
            raise ValueError(f"Konto {account_id} nie istnieje")
        if account_id in multi_account_mgr.accounts:
            multi_account_mgr.accounts[account_id].config.disabled = disabled
        return multi_account_mgr

    if account_id not in multi_account_mgr.accounts:
        raise ValueError(f"Konto {account_id} nie istnieje")
    account_mgr = multi_account_mgr.accounts[account_id]
    account_mgr.config.disabled = disabled

    accounts_data = load_accounts_from_source()
    for i, acc in enumerate(accounts_data, 1):
        if get_account_id(acc, i) == account_id:
            acc["disabled"] = disabled
            break

    save_accounts_to_file(accounts_data)

    status_text = "wyłączone" if disabled else "włączone"
    logger.info(f"[CONFIG] Konto {account_id} {status_text}")
    return multi_account_mgr


def bulk_update_account_disabled_status(
    account_ids: list[str],
    disabled: bool,
    multi_account_mgr: MultiAccountManager,
) -> tuple[int, list[str]]:
    """Masowa aktualizacja statusu wyłączenia kont, maksymalnie 20 naraz."""
    if storage.is_database_enabled():
        updated, missing = storage.bulk_update_accounts_disabled_sync(account_ids, disabled)
        for account_id in account_ids:
            if account_id in multi_account_mgr.accounts:
                multi_account_mgr.accounts[account_id].config.disabled = disabled
        errors = [f"{account_id}: konto nie istnieje" for account_id in missing]
        status_text = "wyłączone" if disabled else "włączone"
        logger.info(f"[CONFIG] Masowo {status_text} {updated}/{len(account_ids)} kont")
        return updated, errors

    success_count = 0
    errors = []

    for account_id in account_ids:
        if account_id not in multi_account_mgr.accounts:
            errors.append(f"{account_id}: konto nie istnieje")
            continue
        account_mgr = multi_account_mgr.accounts[account_id]
        account_mgr.config.disabled = disabled
        success_count += 1

    accounts_data = load_accounts_from_source()
    account_id_set = set(account_ids)

    for i, acc in enumerate(accounts_data, 1):
        acc_id = get_account_id(acc, i)
        if acc_id in account_id_set:
            acc["disabled"] = disabled

    save_accounts_to_file(accounts_data)

    status_text = "wyłączone" if disabled else "włączone"
    logger.info(f"[CONFIG] Masowo {status_text} {success_count}/{len(account_ids)} kont")
    return success_count, errors


def bulk_delete_accounts(
    account_ids: list[str],
    multi_account_mgr: MultiAccountManager,
    http_client,
    user_agent: str,
    retry_policy: RetryPolicy,
    session_cache_ttl_seconds: int,
    global_stats: dict
) -> tuple[MultiAccountManager, int, list[str]]:
    """Masowe usuwanie kont, maksymalnie 20 naraz."""
    if storage.is_database_enabled():
        existing_ids = set(multi_account_mgr.accounts.keys())
        missing = [account_id for account_id in account_ids if account_id not in existing_ids]
        deleted = storage.delete_accounts_sync(account_ids)
        errors = [f"{account_id}: konto nie istnieje" for account_id in missing]
        if deleted > 0:
            multi_account_mgr = reload_accounts(
                multi_account_mgr,
                http_client,
                user_agent,
                retry_policy,
                session_cache_ttl_seconds,
                global_stats
            )
        logger.info(f"[CONFIG] Usunięto masowo {deleted}/{len(account_ids)} kont")
        return multi_account_mgr, deleted, errors

    errors = []
    account_id_set = set(account_ids)

    accounts_data = load_accounts_from_source()
    kept: list[dict] = []
    deleted_ids: list[str] = []

    for i, acc in enumerate(accounts_data, 1):
        acc_id = get_account_id(acc, i)
        if acc_id in account_id_set:
            deleted_ids.append(acc_id)
            continue
        kept.append(acc)

    missing = account_id_set.difference(deleted_ids)
    for account_id in missing:
        errors.append(f"{account_id}: konto nie istnieje")

    if deleted_ids:
        save_accounts_to_file(kept)
        multi_account_mgr = reload_accounts(
            multi_account_mgr,
            http_client,
            user_agent,
            retry_policy,
            session_cache_ttl_seconds,
            global_stats
        )

    success_count = len(deleted_ids)
    logger.info(f"[CONFIG] Usunięto masowo {success_count}/{len(account_ids)} kont")
    return multi_account_mgr, success_count, errors


async def save_account_cooldown_state(account_id: str, account_mgr: AccountManager) -> bool:
    """Zapis stanu cooldownu pojedynczego konta do bazy (wersja zoptymalizowana: jedno aktualizowanie)"""
    if not storage.is_database_enabled():
        return False

    try:
        success = await asyncio.to_thread(
            storage.update_account_cooldown_sync,
            account_id,
            {
                "quota_cooldowns": dict(account_mgr.quota_cooldowns),
                "conversation_count": account_mgr.conversation_count,
                "failure_count": account_mgr.failure_count,
                "daily_usage": dict(account_mgr.daily_usage),
                "daily_usage_date": account_mgr.daily_usage_date,
            },
        )
        if success:
            logger.debug(f"[COOLDOWN] Zapisano stan cooldownu konta {account_id}")
        else:
            logger.warning(f"[COOLDOWN] Konto {account_id} nie istnieje")
        return success
    except Exception as e:
        logger.error(f"[COOLDOWN] Nie udało się zapisać stanu cooldownu konta {account_id}: {e}")
        return False


def save_account_cooldown_state_sync(account_id: str, account_mgr: AccountManager) -> bool:
    """Zapis stanu cooldownu pojedynczego konta do bazy (wersja synchroniczna)"""
    if not storage.is_database_enabled():
        return False

    try:
        success = storage.update_account_cooldown_sync(
            account_id,
            {
                "quota_cooldowns": dict(account_mgr.quota_cooldowns),
                "conversation_count": account_mgr.conversation_count,
                "failure_count": account_mgr.failure_count,
                "daily_usage": dict(account_mgr.daily_usage),
                "daily_usage_date": account_mgr.daily_usage_date,
            },
        )
        if success:
            logger.debug(f"[COOLDOWN] Zapisano stan cooldownu konta {account_id} (synchronicznie)")
        else:
            logger.warning(f"[COOLDOWN] Konto {account_id} nie istnieje (synchronicznie)")
        return success
    except Exception as e:
        logger.error(f"[COOLDOWN] Nie udało się synchronicznie zapisać stanu cooldownu konta {account_id}: {e}")
        return False


async def save_all_cooldown_states(multi_account_mgr: MultiAccountManager) -> int:
    """Zapis kont ze stanem cooldownu do bazy (wersja zoptymalizowana: aktualizacja zbiorcza)"""
    if not storage.is_database_enabled():
        return 0

    # Zbieranie kont wymagających zapisu
    updates = []
    for account_id, account_mgr in multi_account_mgr.accounts.items():
        has_cooldown = (
            account_mgr.quota_cooldowns or
            account_mgr.conversation_count > 0 or
            account_mgr.failure_count > 0 or
            any(v > 0 for v in account_mgr.daily_usage.values())
        )

        if has_cooldown:
            cooldown_data = {
                "quota_cooldowns": dict(account_mgr.quota_cooldowns),
                "conversation_count": account_mgr.conversation_count,
                "failure_count": account_mgr.failure_count,
                "daily_usage": dict(account_mgr.daily_usage),
                "daily_usage_date": account_mgr.daily_usage_date,
            }
            updates.append((account_id, cooldown_data))

    if not updates:
        logger.info(f"[COOLDOWN] Brak czego zapisywać: żadne konto nie ma stanu cooldownu")
        return 0

    success_count, missing = await asyncio.to_thread(
        storage.bulk_update_accounts_cooldown_sync,
        updates,
    )

    if missing:
        logger.warning(f"[COOLDOWN] {len(missing)} kont nie istnieje: {missing[:5]}")

    logger.info(f"[COOLDOWN] Zapisano stany cooldownu zbiorczo: {success_count}/{len(updates)} kont (pominięto {len(multi_account_mgr.accounts) - len(updates)} kont bez stanu)")
    return success_count

