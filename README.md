# geminienterprise-grupkapeel

Gemini Enterprise (business.gemini.google) w OpenCode.

Paczka uruchamia na Twoim komputerze lokalne proxy, które udostępnia Twoje firmowe konto Gemini jako API zgodne z OpenAI pod adresem `http://localhost:7860/v1`. OpenCode łączy się z tym adresem i może używać modelu **Gemini 4 Argon** razem z narzędziami (zapis plików, edycja, komendy).

> Uwaga: to nieoficjalne obejście oparte na ciasteczkach przeglądarki. Może naruszać warunki korzystania z usług Google i zasady Twojej firmy. Używasz na własną odpowiedzialność.

---

## Czego potrzebujesz

1. **Docker Desktop**: https://www.docker.com/products/docker-desktop/ (zainstaluj i uruchom).
2. **Python 3.8+**: https://www.python.org/downloads/ (przy instalacji zaznacz „Add Python to PATH”).
3. **Firefox** z rozszerzeniem **Cookie-Editor**: https://addons.mozilla.org/firefox/addon/cookie-editor/
   Firefox jest zalecany, bo w Chrome i Edge ciasteczka Google potrafią wygasać po kilku godzinach.
4. **OpenCode**: https://opencode.ai
5. Konto z dostępem do **https://business.gemini.google**

---

## Krok 1. Uruchom proxy

Kliknij dwukrotnie `start.bat`.

Przy pierwszym uruchomieniu skrypt tworzy plik `.env` z losowym hasłem do panelu i buduje obraz Dockera z kodu w tym folderze (pierwszy raz kilka minut). Na końcu zobaczysz:

```
Proxy dziala:  http://localhost:7860/v1
Panel admina:  http://localhost:7860/
Haslo panelu:  ...
```

## Krok 2. Skopiuj adres strony Gemini

1. W Firefoksie zaloguj się na **https://business.gemini.google** swoim kontem firmowym.
2. Po załadowaniu czatu skopiuj **cały adres z paska przeglądarki**. Wygląda tak:

```
https://business.gemini.google/home/cid/xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx?csesidx=1234567890&...
```

Potrzebne są z niego dwie wartości: identyfikator po `/cid/` i liczba po `csesidx=`. Skrypt wyciągnie je sam.

## Krok 3. Wyeksportuj ciasteczka

Na tej samej karcie (business.gemini.google):

1. Kliknij ikonę **Cookie-Editor**.
2. Kliknij **Export**, potem **JSON**. Ciasteczka trafiają do schowka.
3. Utwórz w tym folderze plik `business.gemini.google_cookies.json` i wklej do niego zawartość schowka.

Potrzebne ciasteczka:

| Ciasteczko | Wymagane | Opis |
|---|---|---|
| `__Secure-C_SES` | **tak** | główna sesja (zaczyna się od `CSE.`) |
| `__Host-C_OSES` | **tak** | druga część sesji (zaczyna się od `COS.`) |
| `NID` i inne | nie | skrypt je pomija |

> Nie szukaj `__Secure-1PSID` ani `__Secure-1PSIDTS`. To ciasteczka zwykłego gemini.google.com i tu nie działają.

Wersja bez rozszerzenia: F12, zakładka **Dane** (Storage), **Ciasteczka**, `https://business.gemini.google`. Skopiuj wartości dwóch ciasteczek z tabeli i zapisz plik w takim formacie:

```json
{
  "__Secure-C_SES": "CSE.tu_wartosc...",
  "__Host-C_OSES": "COS.tu_wartosc..."
}
```

## Krok 4. Zaimportuj konto do proxy

W tym folderze otwórz terminal (w Eksploratorze wpisz `cmd` w pasku adresu i naciśnij Enter) i uruchom:

```
python import_cookies.py business.gemini.google_cookies.json "TU_WKLEJ_ADRES_Z_KROKU_2"
```

Adres musi być w cudzysłowie, bo zawiera znak `&`. Poprawny wynik:

```
OK: konto 'konto_1' zaimportowane, status: active, ważne jeszcze: ...
```

## Krok 5. Sprawdź, czy działa

```bash
curl -s -m 120 http://localhost:7860/v1/chat/completions -H "Content-Type: application/json" -d "{\"model\":\"gemini-4-argon\",\"messages\":[{\"role\":\"user\",\"content\":\"Odpowiedz jednym slowem: pong\"}]}"
```

W odpowiedzi powinno być `Pong`.

## Krok 6. Podłącz OpenCode

1. Otwórz plik `C:\Users\<TWOJA_NAZWA>\.config\opencode\opencode.jsonc`. Jeśli nie istnieje, utwórz go.
2. Wklej blok z pliku `opencode-provider.jsonc` do sekcji `"provider"`. Na dole tego pliku jest też przykład całej konfiguracji od zera.
3. Zrestartuj OpenCode i wybierz model **Gemini 4 Argon (geminienterprise-grupkapeel)**.
4. Test: poproś o utworzenie pliku w Twoim projekcie. Argon powinien go zapisać.

---

## Gdy przestaje działać (wygasłe ciasteczka)

Sesja wygasa po kilku dniach, a czasem wcześniej, np. po wylogowaniu w przeglądarce. Objawy w OpenCode to błędy 401/403, puste odpowiedzi albo komunikat o braku dostępnych kont.

Naprawa:

1. Wejdź na business.gemini.google w Firefoksie (zaloguj się, jeśli trzeba).
2. Powtórz **Krok 3** (nowy eksport ciasteczek) i **Krok 4** (ten sam import).

Konto zostaje nadpisane, nic więcej nie trzeba zmieniać. Stan konta i datę ważności zobaczysz w panelu `http://localhost:7860/`.

## Dostępne modele

| Model | Do czego |
|---|---|
| `gemini-4-argon` | najmocniejszy, zalecany do pracy w OpenCode |
| `gemini-3.1-pro-preview` | mocny model do kodu |
| `gemini-3.5-flash` | szybki, do prostych zadań |
| `gemini-2.5-pro` | starszy model pro |
| `gemini-imagen`, `gemini-veo` | generowanie obrazów i wideo (tylko przez API) |

Dostęp do modeli zależy od licencji konta. `gemini-4-carbon` na testowanym koncie nie był dostępny.

## Ograniczenia

- Gdy OpenCode używa narzędzi, odpowiedź pojawia się w całości po zakończeniu, a nie słowo po słowie.
- Narzędzia działają przez obejście tekstowe. Model czasem źle zapisze wywołanie i wtedy zobaczysz zwykły tekst zamiast wykonanej akcji. Wystarczy ponowić prośbę.
- Proxy nasłuchuje tylko na tym komputerze (`127.0.0.1`), więc inne urządzenia w sieci go nie widzą.

## Bezpieczeństwo

- **Nigdy nie wysyłaj nikomu pliku z ciasteczkami ani folderu `data`.** Ciasteczka dają pełny dostęp do Twojego konta firmowego.
- Jeśli przekazujesz tę paczkę dalej, usuń wcześniej: `.env`, folder `data` i plik `*_cookies.json`.
- Po zakończeniu korzystania wyloguj się z business.gemini.google. Stara sesja wtedy wygaśnie.

## Zarządzanie

- `start.bat`: uruchamia proxy (po restarcie komputera wystartuje samo, jeśli działa Docker Desktop).
- `stop.bat`: zatrzymuje proxy.
- Panel admina: `http://localhost:7860/` (hasło w pliku `.env`, wiersz `ADMIN_KEY=`).
- Logi: `docker logs geminienterprise-grupkapeel --tail 50`

## Zawartość paczki

| Plik | Opis |
|---|---|
| `AGENTS.md` | instrukcja dla agenta AI, który ma sam postawić całość od zera |
| `start.bat`, `stop.bat` | uruchamianie i zatrzymywanie proxy |
| `docker-compose.yml`, `Dockerfile` | budowanie i uruchamianie kontenera lokalnie |
| `main.py`, `app/`, `core/`, `util/` | serwer proxy (z modelem Gemini 4 Argon i obsługą narzędzi OpenCode) |
| `frontend/` | panel admina |
| `import_cookies.py` | import i odświeżanie ciasteczek |
| `opencode-provider.jsonc` | wpis do konfiguracji OpenCode |
| `LICENSE` | licencja |
| `.gitignore` | blokuje przypadkowy commit `.env`, ciasteczek i folderu `data` |
