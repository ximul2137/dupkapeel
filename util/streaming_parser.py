import json
from typing import Iterator, Dict, Any, Iterable, AsyncIterator
from itertools import chain

def parse_json_array_stream(line_iterator: Iterable[str]) -> Iterator[Dict[str, Any]]:
    """
    Parsuje strumień sformatowanej (pretty-printed) tablicy JSON złożonej z linii tekstu.

    Ta funkcja jest generatorem, który dla każdego obiektu JSON najwyższego poziomu w strumieniu
    zwraca (yield) kompletny słownik Pythona. Została zaprojektowana z myślą o oszczędności pamięci,
    ponieważ przetwarza strumień linia po linii, zamiast wczytywać wszystko naraz.

    Args:
        line_iterator: iterator zwracający linie odpowiedzi, np. `requests.Response.iter_lines()`
                       po zdekodowaniu.

    Yields:
        słownik obiektu JSON sparsowanego ze strumienia.

    Raises:
        ValueError: jeśli strumień nie wygląda na początek tablicy JSON lub ma błędny format,
                    przez co nie da się go parsować obiekt po obiekcie.
    """
    # Zmienne stanu
    buffer = []
    brace_level = 0
    in_array = False

    # 1. Szukanie znaku początku tablicy '[' i pominięcie wszystkich wcześniejszych linii
    for line in line_iterator:
        stripped_line = line.strip()
        if not stripped_line:
            continue

        if stripped_line.startswith('['):
            in_array = True
            # Usunięcie początkowego znaku '[' i dalsze przetwarzanie reszty
            line = stripped_line[1:]
            # Łączenie pozostałych linii przez chain, bez konwersji na listę (oszczędność pamięci)
            line_iterator = chain([line], line_iterator)
            break
    
    if not in_array:
        raise ValueError("Strumień danych nie zaczyna się od tablicy JSON ( '[' ).")

    # 2. Przechodzenie przez strumień, budowanie i parsowanie obiektów znak po znaku
    in_string = False  # czy jesteśmy wewnątrz ciągu znaków
    escape_next = False  # czy następny znak jest poprzedzony znakiem ucieczki

    for line in line_iterator:
        for char in line:
            # Obsługa znaków ucieczki
            if escape_next:
                if brace_level > 0:
                    buffer.append(char)
                escape_next = False
                continue

            # Sprawdzenie, czy to znak ucieczki
            if char == '\\':
                if brace_level > 0:
                    buffer.append(char)
                escape_next = True
                continue

            # Sprawdzenie granic ciągu znaków (tylko wewnątrz obiektu)
            if char == '"' and brace_level > 0:
                in_string = not in_string
                buffer.append(char)
                continue

            # Nawiasy obsługujemy tylko poza ciągiem znaków
            if not in_string:
                # Po napotkaniu '{' zwiększamy poziom zagnieżdżenia
                if char == '{':
                    # Dla obiektu najwyższego poziomu czyścimy bufor i przygotowujemy się na nowy obiekt
                    if brace_level == 0:
                        buffer = []
                    brace_level += 1

                # Znaki dodajemy do bufora tylko wewnątrz obiektu (brace_level > 0)
                if brace_level > 0:
                    buffer.append(char)

                # Po napotkaniu '}' zmniejszamy poziom zagnieżdżenia
                if char == '}':
                    brace_level -= 1
                    # Gdy poziom wraca do 0, obiekt najwyższego poziomu jest kompletny
                    if brace_level == 0 and buffer:
                        obj_str = "".join(buffer)
                        try:
                            # Parsowanie kompletnego obiektu i zwrócenie wyniku
                            # strict=False dopuszcza znaki sterujące
                            yield json.loads(obj_str, strict=False)
                        except json.JSONDecodeError as e:
                            # Przy błędzie parsowania rzucamy wyjątek z kontekstem
                            raise ValueError(f"Nie udało się sparsować obiektu JSON: {e}\nTreść: {obj_str}") from e
                        finally:
                            # Reset bufora przed następnym obiektem
                            buffer = []
                            in_string = False  # reset stanu ciągu znaków
            else:
                # Wewnątrz ciągu znaków dodajemy znak bezpośrednio
                if brace_level > 0:
                    buffer.append(char)

    # 3. Sprawdzenie po zakończeniu strumienia, czy został niezamknięty obiekt
    if brace_level != 0:
        print(f"Ostrzeżenie: strumień JSON zakończył się nieoczekiwanie, poziom nawiasów {brace_level}, dane mogą być niekompletne.")

async def parse_json_array_stream_async(line_iterator: AsyncIterator[str]) -> AsyncIterator[Dict[str, Any]]:
    """
    Wersja asynchroniczna: parsuje strumień sformatowanej (pretty-printed) tablicy JSON złożonej z linii tekstu.

    Ta funkcja jest generatorem asynchronicznym, który dla każdego obiektu JSON najwyższego poziomu w strumieniu
    zwraca (yield) kompletny słownik Pythona. Została zaprojektowana z myślą o oszczędności pamięci,
    ponieważ przetwarza strumień linia po linii, zamiast wczytywać wszystko naraz.

    Args:
        line_iterator: asynchroniczny iterator zwracający linie odpowiedzi, np. `httpx.Response.aiter_lines()`

    Yields:
        słownik obiektu JSON sparsowanego ze strumienia.

    Raises:
        ValueError: jeśli strumień nie wygląda na początek tablicy JSON lub ma błędny format,
                    przez co nie da się go parsować obiekt po obiekcie.
    """
    # Zmienne stanu
    buffer = []
    brace_level = 0
    in_array = False

    # 1. Szukanie znaku początku tablicy '[' i pominięcie wszystkich wcześniejszych linii
    in_string = False
    escape_next = False

    async for line in line_iterator:
        stripped_line = line.strip()
        if not stripped_line:
            continue

        if stripped_line.startswith('['):
            in_array = True
            # Usunięcie początkowego znaku '[' i dalsze przetwarzanie reszty
            line = stripped_line[1:]
            # Przetwarzanie reszty (ta sama logika śledzenia stanu ciągu znaków)
            for char in line:
                if escape_next:
                    if brace_level > 0:
                        buffer.append(char)
                    escape_next = False
                    continue

                if char == '\\':
                    if brace_level > 0:
                        buffer.append(char)
                    escape_next = True
                    continue

                if char == '"' and brace_level > 0:
                    in_string = not in_string
                    buffer.append(char)
                    continue

                if not in_string:
                    if char == '{':
                        if brace_level == 0:
                            buffer = []
                        brace_level += 1

                    if brace_level > 0:
                        buffer.append(char)

                    if char == '}':
                        brace_level -= 1
                        if brace_level == 0 and buffer:
                            obj_str = "".join(buffer)
                            try:
                                yield json.loads(obj_str, strict=False)
                            except json.JSONDecodeError as e:
                                raise ValueError(f"Nie udało się sparsować obiektu JSON: {e}\nTreść: {obj_str}") from e
                            finally:
                                buffer = []
                                in_string = False
                else:
                    if brace_level > 0:
                        buffer.append(char)
            break

    if not in_array:
        raise ValueError("Strumień danych nie zaczyna się od tablicy JSON ( '[' ).")

    # 2. Przechodzenie przez strumień znak po znaku (z zachowaniem stanu po pierwszej linii)
    async for line in line_iterator:
        for char in line:
            # Obsługa znaków ucieczki
            if escape_next:
                if brace_level > 0:
                    buffer.append(char)
                escape_next = False
                continue

            # Sprawdzenie, czy to znak ucieczki
            if char == '\\':
                if brace_level > 0:
                    buffer.append(char)
                escape_next = True
                continue

            # Sprawdzenie granic ciągu znaków (tylko wewnątrz obiektu)
            if char == '"' and brace_level > 0:
                in_string = not in_string
                buffer.append(char)
                continue

            # Nawiasy obsługujemy tylko poza ciągiem znaków
            if not in_string:
                # Po napotkaniu '{' zwiększamy poziom zagnieżdżenia
                if char == '{':
                    # Dla obiektu najwyższego poziomu czyścimy bufor i przygotowujemy się na nowy obiekt
                    if brace_level == 0:
                        buffer = []
                    brace_level += 1

                # Znaki dodajemy do bufora tylko wewnątrz obiektu (brace_level > 0)
                if brace_level > 0:
                    buffer.append(char)

                # Po napotkaniu '}' zmniejszamy poziom zagnieżdżenia
                if char == '}':
                    brace_level -= 1
                    # Gdy poziom wraca do 0, obiekt najwyższego poziomu jest kompletny
                    if brace_level == 0 and buffer:
                        obj_str = "".join(buffer)
                        try:
                            # Parsowanie kompletnego obiektu i zwrócenie wyniku
                            # strict=False dopuszcza znaki sterujące
                            yield json.loads(obj_str, strict=False)
                        except json.JSONDecodeError as e:
                            # Przy błędzie parsowania rzucamy wyjątek z kontekstem
                            raise ValueError(f"Nie udało się sparsować obiektu JSON: {e}\nTreść: {obj_str}") from e
                        finally:
                            # Reset bufora przed następnym obiektem
                            buffer = []
                            in_string = False  # reset stanu ciągu znaków
            else:
                # Wewnątrz ciągu znaków dodajemy znak bezpośrednio
                if brace_level > 0:
                    buffer.append(char)

    # 3. Sprawdzenie po zakończeniu strumienia, czy został niezamknięty obiekt
    if brace_level != 0:
        print(f"Ostrzeżenie: strumień JSON zakończył się nieoczekiwanie, poziom nawiasów {brace_level}, dane mogą być niekompletne.")

