from pathlib import Path
from typing import Callable
import argparse
from openai import OpenAI
from bs4 import BeautifulSoup



BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR.parent / "data"

CUT_PHRASE = "Licytant przystępujący do przetargu"

SYSTEM = """Jesteś precyzyjnym ekstraktorem danych z polskich obwieszczeń komorniczych o licytacji nieruchomości.

Twoim zadaniem jest wyciągnąć wyłącznie dane znajdujące się w tekście.
Nie zgaduj. Nie dopisuj danych spoza dokumentu.
Jeśli pole nie występuje lub nie da się go jednoznacznie ustalić — wpisz null.

Zwróć WYŁĄCZNIE poprawny JSON.
Nie używaj markdown.
Nie dodawaj komentarzy.
Nie dodawaj wyjaśnień.
Nie poprzedzaj odpowiedzi żadnym tekstem.
Odpowiedź ma zawierać tylko jeden obiekt JSON.
"""

USER_TEMPLATE_STATIC = """Wyciągnij dane w dokładnie tym schemacie:

{
  "dluznik": string|null,
  "adres_nieruchomosci": {
    "wojewodztwo": string|null,
    "powiat": string|null,
    "gmina": string|null,
    "miejscowosc": string|null,
    "ulica_wieś": string|null,
    "nr_budynku": string|null
  },
  "nieruchomosci": [
    {
      "nr_dzialki": string,
      "powierzchnia": string|null,
      "nr_ksiegi_wieczystej": string|null
    }
  ]
}

Zasady ekstrakcji:

1. dluznik:
   - osoba wskazana jako właściciel nieruchomości
   - najczęściej w frazie: "należącej do ..."

2. nieruchomosci:
   - każdą działkę ewidencyjną traktuj jako osobny obiekt w tablicy
   - nr_dzialki: numer działki (np. "207/1")
   - powierzchnia: powierzchnia przypisana do tej działki (np. "8 251 m2")
   - jeśli powierzchnia podana jest zbiorczo dla wielu działek, przypisz null
   - nr_ksiegi_wieczystej:
       - jeśli jedna księga dotyczy wszystkich działek → powiel ją w każdym obiekcie
       - jeśli brak informacji → null

3. nr_ksiegi_wieczystej:
   - numer księgi wieczystej, np. "LU1R/00082146/9"

4. Interpretacja skrótów administracyjnych:
   - "msc." = miejscowosc
   - "gm." = gmina
   - "pow." = powiat
   - "woj." = wojewodztwo
   - "ul." = ulica

5. Adres:
   - wyciągaj tylko informacje wprost obecne w tekście
   - nie ustalaj województwa ani powiatu na podstawie wiedzy geograficznej
   - jeśli element adresu nie występuje → null
   - najczęściej miejscowość poprzedza kod pocztowy w formie "00-000 Miejscowość"
   

Oto tekst do analizy:

"""


import re
import json
from pathlib import Path


def save_result_structured(input_file: Path, json_data: dict) -> None:
    # wyciągnij numer aukcji z nazwy pliku
    match = re.search(r"\d+", input_file.stem)
    if not match:
        raise ValueError(f"Nie znaleziono numeru aukcji w nazwie pliku: {input_file.name}")

    nraukcji = int(match.group())

    # wylicz folder grupujący
    group_folder = (nraukcji // 1000) * 1000

    # budowa ścieżki
    output_dir = DATA_DIR / "processed" / "28" / str(group_folder)
    output_dir.mkdir(parents=True, exist_ok=True)

    output_file = output_dir / f"{nraukcji}.json"

    # opcjonalna walidacja JSON
    data = json_data

    with output_file.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"Zapisano: {output_file.resolve()}")



def cut_after_phrase(text: str, phrase: str = CUT_PHRASE) -> str:
    i = text.find(phrase)
    return text if i == -1 else text[:i].strip()


def html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")

    # usuń niepotrzebne elementy
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    # tekst z sensownymi separatorami (żeby nie sklejało słów)
    text = soup.get_text(separator="\n", strip=True)

    # normalizacja spacji
    text = text.replace("\xa0", " ")
    return text


def process_html(file_path: Path) -> None:
    """
    Twoja funkcja do wykonania na każdym pliku HTML.
    Podmień zawartość na swoją logikę.
    """
    html = file_path.read_text(encoding="utf-8", errors="replace")
    text = html_to_text(html)
    text = cut_after_phrase(text)
    
    client = OpenAI(api_key=ChatGPTKey)
    try:

        r = client.responses.create(
                model="gpt-4.1-mini",
                input=[
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": USER_TEMPLATE_STATIC},
                {"role": "user", "content": text},
            ]
            )
        
        print(r.usage   )

        data = json.loads(r.output_text.strip())

        json_path = file_path.with_suffix(".json")

        if json_path.exists():
            with json_path.open("r", encoding="utf-8") as f:
                existing_data = json.load(f)
        else:
            existing_data = {}


        # scal dane z istniejącym plikiem JSON, jeśli istnieje
        existing_data.update(data)

        match = re.search(r"\((.*?)\)", lok)
        woj = match.group(1) if match else None

        lok = existing_data["metadata"]["Lokalizacja"]
        existing_data["adres_nieruchomosci"]["wojewodztwo"] = woj

        save_result_structured(file_path, existing_data)
    except Exception as e:
        raise SystemExit(str(e))
    
    


def iterate_html_files(root_dir: Path, func: Callable[[Path], None]) -> int:
    """
    Iteruje po wszystkich *.html w katalogu i subkatalogach i wywołuje func(path).
    Zwraca liczbę przetworzonych plików.
    """
    if not root_dir.exists():
        raise FileNotFoundError(f"Nie ma takiego katalogu: {root_dir}")

    count = 0
    for file_path in root_dir.rglob("*.html"):
        if file_path.is_file():
            try:
                func(file_path)
                count += 1
            except Exception as e:
                # Nie przerywaj całości jeśli jeden plik się wysypie
                print(f"[ERROR] {file_path}: {e}")

    return count


if __name__ == "__main__":
    # Zmień na swój katalog:
    parser = argparse.ArgumentParser(
    description="Iteruje wszystkie pliki HTML w katalogu i subkatalogach."
    )
    parser.add_argument(
        "-id", 
        "--inputDir",
        type=str,
        help="Ścieżka do katalogu głównego"
    )

    parser.add_argument(
        "-od", 
        "--outputDir",
        type=str,
        help="Ścieżka do katalogu wyjściowego"
    )



    args = parser.parse_args()
    root = Path(args.inputDir)
    
  

    processed = iterate_html_files(root, process_html)
    print(f"\nDone. Przetworzono {processed} plików HTML.")
