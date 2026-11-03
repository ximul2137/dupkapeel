# AGENTS.md: instrukcja instalacji dla agenta AI

Ten plik jest dla agenta AI (OpenCode, Claude Code, Codex, Cursor itp.), który ma postawić **geminienterprise-grupkapeel** od zera na komputerze użytkownika. Wykonuj kroki po kolei. Po każdym kroku sprawdź wynik, zanim przejdziesz dalej.

## Cel

Na końcu użytkownik ma:

1. działający kontener Dockera `geminienterprise-grupkapeel` z API zgodnym z OpenAI pod `http://localhost:7860/v1` (albo pod innym portem, jeśli 7860 jest zajęty),
2. zaimportowane do proxy konto Gemini Enterprise (business.gemini.google),
3. providera `geminienterprise-grupkapeel` w globalnej konfiguracji OpenCode, z modelem `gemini-4-argon` ustawionym jako domyślny (jeśli użytkownik się zgodzi).

## Zasady bezpieczeństwa (obowiązkowe)

- **Ciasteczka i hasło panelu to sekrety.** Nigdy nie wypisuj ich wartości w odpowiedziach, logach ani komendach widocznych dla użytkownika. Nie wklejaj ich do plików poza `.env` i plikiem ciasteczek, który dostarczył użytkownik. Nie commituj ich.
- Nie proś użytkownika o wklejenie ciasteczek do czatu. Poproś o zapisanie ich w pliku (krok 4).
- **Przed edycją `opencode.jsonc` zrób kopię zapasową.** Nie usuwaj ani nie zmieniaj istniejących providerów, modeli i ustawień użytkownika. Tylko dopisuj.
- Zmianę domyślnego modelu (`"model"`) w OpenCode wykonaj tylko za zgodą użytkownika.
- Nie zatrzymuj ani nie usuwaj kontenerów, których nie utworzyłeś. Jeśli port jest zajęty przez coś innego, użyj innego portu (krok 2).
- Nie usuwaj folderu `data/`. Zawiera bazę kont użytkownika.
- Nie używaj `docker system prune`, `docker volume rm` ani innych komend kasujących dane.

## Uwagi o środowisku (Windows)

- Projekt jest przygotowany pod Windows z Docker Desktop. Działa też na Linuksie i macOS. Wtedy zamiast `start.bat` użyj komend z kroków poniżej.
- W Git Bash na Windows komendy `docker exec` ze ścieżkami typu `/app/...` są przerabiane na ścieżki Windows. Poprzedź je `MSYS_NO_PATHCONV=1`.
- Komendy uruchamiaj w folderze tego projektu (tam, gdzie leży ten plik).
- W zapytaniach JSON przez `curl` używaj w ścieżkach Windows `/` zamiast `\`, bo pojedynczy `\` psuje JSON.

---

## Krok 1. Sprawdź wymagania

Uruchom:

```
docker --version
docker info
docker compose version
python --version
```

- `docker info` musi zadziałać bez błędu. Jeśli Docker jest zainstalowany, ale nie działa, poproś użytkownika o uruchomienie **Docker Desktop** i poczekaj na potwierdzenie.
- Jeśli brakuje Dockera, poproś użytkownika o instalację Docker Desktop: https://www.docker.com/products/docker-desktop/. Nie instaluj go sam bez zgody, bo wymaga uprawnień administratora i restartu.
- Python musi być w wersji 3.8 lub nowszej (komenda może się nazywać `python`, `python3` albo `py`). Jeśli go brakuje, poproś o instalację z https://www.python.org/downloads/ z opcją „Add Python to PATH”.

## Krok 2. Wybierz port

Sprawdź, czy port 7860 jest wolny:

```
curl -s -m 3 http://localhost:7860/health
docker ps --format "{{.Names}} {{.Ports}}"
```

- Brak odpowiedzi i brak kontenera na `7860`: port jest wolny. Używaj 7860.
- Port zajęty przez kontener `geminienterprise-grupkapeel`: projekt jest już uruchomiony. Przejdź do kroku 4.
- Port zajęty przez coś innego (np. starszy kontener `gemini-business2api`): **nie zatrzymuj go bez pytania.** Zapytaj użytkownika, czy zatrzymać tamto narzędzie, czy użyć innego portu. Przy innym porcie wybierz wolny (np. 7870) i zapamiętaj go jako `PORT`. Wpiszesz go do `.env` w kroku 3 i użyjesz w krokach 5–7.

## Krok 3. Utwórz `.env` i uruchom kontener

Jeśli plik `.env` **nie istnieje**, utwórz go z losowym hasłem panelu:

```
python -c "import secrets;open('.env','w').write('ADMIN_KEY='+secrets.token_urlsafe(24)+'\nPORT=7860\n')"
```

Przy innym porcie zamień `7860` na wybrany numer. Jeśli `.env` już istnieje, nie nadpisuj go. Tylko sprawdź, czy jest w nim `ADMIN_KEY=` (i ewentualnie zmień `PORT=`).

Zbuduj i uruchom kontener:

```
docker compose up -d --build
```

Pierwsze budowanie trwa kilka minut (instalacja zależności i budowanie panelu). Ustaw długi timeout (np. 15 minut).

Poczekaj na start i sprawdź zdrowie serwera (powtarzaj co kilka sekund, maksymalnie przez około minutę):

```
curl -s http://localhost:7860/health
```

Oczekiwany wynik: `{"status":"ok"}`. Jeśli serwer nie wstaje, sprawdź logi:

```
docker logs geminienterprise-grupkapeel --tail 50
```

## Krok 4. Zdobądź ciasteczka i adres strony (wymaga użytkownika)

Agent nie może sam zalogować się na konto Google użytkownika. Ten krok wykonuje człowiek. Przekaż mu te instrukcje:

1. Zainstaluj w **Firefoksie** rozszerzenie **Cookie-Editor**: https://addons.mozilla.org/firefox/addon/cookie-editor/ (Firefox jest zalecany, bo w Chrome i Edge ciasteczka Google wygasają po kilku godzinach).
2. Zaloguj się na **https://business.gemini.google** swoim kontem firmowym i otwórz czat.
3. Skopiuj **cały adres z paska przeglądarki**. Musi zawierać `/cid/` oraz `csesidx=`, np.
   `https://business.gemini.google/home/cid/xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx?csesidx=1234567890&...`
4. Na tej samej karcie kliknij Cookie-Editor, potem **Export**, potem **JSON**.
5. Zapisz zawartość schowka jako plik `business.gemini.google_cookies.json` w folderze tego projektu.
6. Wklej agentowi **tylko adres strony** z punktu 3 (adres nie jest sekretem na tyle, co ciasteczka, ale też nie publikuj go).

Gdy użytkownik potwierdzi, sprawdź plik **bez wypisywania wartości**:

```
python -c "import json;d=json.load(open('business.gemini.google_cookies.json',encoding='utf-8-sig'));n=[c['name'] for c in d] if isinstance(d,list) else list(d);print(sorted(n))"
```

W liście muszą być `__Secure-C_SES` i `__Host-C_OSES`.

- Brak `__Secure-C_SES`: użytkownik eksportował ciasteczka z innej strony. Poproś o eksport na karcie `business.gemini.google`.
- Są `__Secure-1PSID` / `__Secure-1PSIDTS`, a brak `__Secure-C_SES`: to ciasteczka zwykłego gemini.google.com. Nie zadziałają.

## Krok 5. Zaimportuj konto do proxy

```
python import_cookies.py business.gemini.google_cookies.json "ADRES_OD_UŻYTKOWNIKA"
```

Adres musi być w cudzysłowie (zawiera `&`). Przy innym porcie dodaj `--proxy http://localhost:PORT`. Skrypt sam czyta hasło panelu z `.env`.

Oczekiwany wynik: `OK: konto 'konto_1' zaimportowane, status: active, ...`

Status inny niż `active` albo błąd HTTP oznacza zwykle wygasłe lub złe ciasteczka. Poproś użytkownika o ponowny eksport (krok 4).

## Krok 6. Sprawdź, czy model odpowiada

```
curl -s -m 120 http://localhost:7860/v1/chat/completions -H "Content-Type: application/json" -d "{\"model\":\"gemini-4-argon\",\"messages\":[{\"role\":\"user\",\"content\":\"Odpowiedz jednym slowem: pong\"}]}"
```

W `choices[0].message.content` powinno być `Pong` (lub `pong`). Pusta treść albo błąd `model id ... is invalid` oznacza, że konto użytkownika nie ma dostępu do Argon. Wtedy sprawdź `gemini-3.1-pro-preview` i w kroku 7 ustaw jako domyślny ten model, który odpowiada.

Sprawdź też obsługę narzędzi (bez niej agent w OpenCode nie zapisze plików):

```
curl -s -m 120 http://localhost:7860/v1/chat/completions -H "Content-Type: application/json" -d "{\"model\":\"gemini-4-argon\",\"tools\":[{\"type\":\"function\",\"function\":{\"name\":\"write\",\"description\":\"Write a file\",\"parameters\":{\"type\":\"object\",\"properties\":{\"filePath\":{\"type\":\"string\"},\"content\":{\"type\":\"string\"}},\"required\":[\"filePath\",\"content\"]}}}],\"messages\":[{\"role\":\"user\",\"content\":\"Create file C:/tmp/test.txt with content: ok\"}]}"
```

Oczekiwany wynik: `finish_reason` równe `tool_calls` i wywołanie `write` w `message.tool_calls`. Ten test niczego nie zapisuje na dysku.

## Krok 7. Dopisz providera do OpenCode

### Gdzie jest konfiguracja

Globalny plik konfiguracji OpenCode:

- Windows: `C:\Users\<UŻYTKOWNIK>\.config\opencode\opencode.jsonc` (albo `opencode.json`)
- Linux / macOS: `~/.config/opencode/opencode.jsonc` (albo `opencode.json`)

Jeśli istnieją oba, edytuj ten, którego używa użytkownik (zapytaj, jeśli nie wiesz). Jeśli nie ma żadnego, utwórz `opencode.jsonc`.

### Kopia zapasowa

Przed edycją skopiuj plik obok, np. `opencode.jsonc.bak-grupkapeel-<data>`.

### Co dopisać

Plik to JSONC (dozwolone komentarze i przecinki na końcu). **Edytuj go tekstowo, zachowując komentarze i formatowanie.** Nie wczytuj go parserem JSON i nie zapisuj od nowa, bo usuniesz komentarze użytkownika.

Do obiektu `"provider"` dopisz klucz `"geminienterprise-grupkapeel"` z zawartością z pliku `opencode-provider.jsonc` z tego projektu (blok na górze pliku). Przy innym porcie zmień `baseURL` na `http://localhost:PORT/v1`.

- Brak obiektu `"provider"`: dodaj go na najwyższym poziomie.
- Klucz `"geminienterprise-grupkapeel"` już istnieje: zaktualizuj tylko `options.baseURL` i dopisz brakujące modele. Niczego innego nie zmieniaj.
- Usuń z modeli te, które w kroku 6 nie odpowiadały (np. gdy konto nie ma Argon).

Jeśli tworzysz plik od zera, użyj tej struktury:

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "provider": {
    "geminienterprise-grupkapeel": {
      // blok z opencode-provider.jsonc
    }
  },
  "model": "geminienterprise-grupkapeel/gemini-4-argon"
}
```

### Domyślny model

Zapytaj użytkownika, czy ustawić `"model": "geminienterprise-grupkapeel/gemini-4-argon"` jako domyślny. Jeśli w pliku już jest inny `"model"`, nie zmieniaj go bez zgody.

### Sprawdzenie pliku

Sprawdź, czy plik jest poprawnym JSONC (usuwa komentarze i przecinki na końcu, potem parsuje):

```
python -c "import re,json,sys;t=open(sys.argv[1],encoding='utf-8').read();t=re.sub(r'(?m)^\s*//.*$','',t);t=re.sub(r',(\s*[}\]])',r'\1',t);c=json.loads(t);print('OK, providerzy:',list(c.get('provider',{})))" "ŚCIEŻKA_DO_opencode.jsonc"
```

Ten test jest uproszczony (nie obsługuje `//` wewnątrz napisów, np. w adresach URL w tej samej linii po kodzie). Jeśli zgłasza błąd przy pliku, który wygląda poprawnie, porównaj zmiany z kopią zapasową i upewnij się ręcznie, że nawiasy i przecinki się zgadzają.

## Krok 8. Raport dla użytkownika

Na końcu przekaż użytkownikowi krótko:

1. Adres API (`http://localhost:PORT/v1`) i adres panelu (`http://localhost:PORT/`). Hasło panelu jest w pliku `.env` (wiersz `ADMIN_KEY=`). Podaj ścieżkę do pliku, nie wartość hasła.
2. Które modele odpowiadały w kroku 6.
3. Że musi **zrestartować OpenCode** i wybrać model **Gemini 4 Argon (geminienterprise-grupkapeel)**.
4. Gdzie jest kopia zapasowa `opencode.jsonc`.
5. Datę wygaśnięcia sesji z wyniku kroku 5 i sposób odświeżenia (sekcja niżej).
6. Że plik `business.gemini.google_cookies.json` zawiera dostęp do jego konta. Nie wolno go nikomu wysyłać ani commitować (jest w `.gitignore`).

---

## Odświeżanie ciasteczek (gdy przestaje działać)

Objawy: błędy 401/403, puste odpowiedzi, komunikat o braku dostępnych kont, status konta inny niż `active` w panelu.

1. Poproś użytkownika o powtórzenie kroku 4 (nowy eksport ciasteczek, ten sam plik).
2. Uruchom ponownie krok 5 z tym samym adresem. Konto `konto_1` zostanie nadpisane.
3. Sprawdź krokiem 6.

Kontenera nie trzeba restartować.

## Rozwiązywanie problemów

| Objaw | Przyczyna | Co zrobić |
|---|---|---|
| `docker info` zwraca błąd | Docker Desktop nie działa | poproś użytkownika o uruchomienie Docker Desktop |
| `port is already allocated` | port zajęty | krok 2: inny port w `.env`, potem `docker compose up -d` |
| `container name ... already in use` | został stary kontener tego projektu | `docker compose up -d` w tym folderze; jeśli kontener pochodzi z innego folderu, zapytaj użytkownika przed usunięciem |
| budowanie przerywa się na `npm install` lub `pip install` | brak internetu lub chwilowy błąd sieci | powtórz `docker compose up -d --build` |
| import: `nie mogę połączyć się z proxy` | kontener nie działa lub zły port | krok 3, sprawdź `/health`, dodaj `--proxy` |
| import: `HTTP 401` przy `/login` | `ADMIN_KEY` w `.env` nie pasuje do działającego kontenera | po zmianie `.env` wykonaj `docker compose up -d --force-recreate` |
| `model id: ... is invalid` | konto nie ma dostępu do modelu | użyj innego modelu z kroku 6 |
| OpenCode nie widzi modelu | brak restartu lub błąd w `opencode.jsonc` | sprawdź plik (krok 7), zrestartuj OpenCode |
| model pisze „nie mam narzędzi write/bash” | zapytanie trafia do innego providera lub starej wersji proxy | sprawdź `baseURL` w OpenCode i test narzędzi z kroku 6 |

## Struktura projektu

| Ścieżka | Opis |
|---|---|
| `docker-compose.yml`, `Dockerfile` | budowanie i uruchamianie kontenera |
| `start.bat`, `stop.bat` | uruchamianie i zatrzymywanie dla użytkownika (Windows) |
| `import_cookies.py` | import i odświeżanie konta w proxy |
| `opencode-provider.jsonc` | blok providera do OpenCode |
| `main.py` | konfiguracja modeli (`MODEL_MAPPING`) |
| `app/services/tools_protocol.py` | emulacja narzędzi OpenAI (`tools` / `tool_calls`) |
| `app/services/chat_service.py` | obsługa zapytań czatu |
| `data/` | baza kont i ustawień (tworzona przy starcie, nie commitować) |
| `.env` | hasło panelu i port (nie commitować) |

### Dodanie nowego modelu

Jeśli Google udostępni na koncie nowy model (np. `gemini-4-carbon`):

1. Dopisz go do `MODEL_MAPPING` w `main.py`: `"gemini-4-carbon": "gemini-4-carbon",`
2. Przebuduj: `docker compose up -d --build`
3. Sprawdź krokiem 6 z nową nazwą modelu.
4. Dopisz model do providera w `opencode.jsonc` i zrestartuj OpenCode.
