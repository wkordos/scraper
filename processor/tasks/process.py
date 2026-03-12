from __future__ import annotations
from __future__ import annotations
from typing import Any, Dict, Optional, Tuple
import psycopg
from pathlib import Path
from typing import Callable
import argparse
from openai import OpenAI
from bs4 import BeautifulSoup
import re
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple
import requests

from typing import Any, Dict, List, Optional
import psycopg
from psycopg.rows import dict_row
from scraper.dictionaries import WOJ_KODY




DSN = "postgresql://postgres:postgres@localhost:5432/gis"

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
   - najczęściej miejscowość poprzedza kod pocztowy w formie np. 02-345 Miejscowość
   - gmina i miejscowosc mogą być takie same 
   
6. Przykładowe frazy do rozpoznania:
    19,Sokóle, 05-304 Stanisławów - oznacza ulica_wieś=Sokóle, miejscowosc=Stanisławów, kod_pocztowy=05-304 
   

Oto tekst do analizy:

"""




def _parse_extent(extent: Optional[str]) -> Optional[Tuple[float, float, float, float]]:
    if not extent or not isinstance(extent, str):
        return None
    parts = [p.strip() for p in extent.split(",")]
    if len(parts) != 4:
        return None
    try:
        return tuple(map(float, parts))  # (minx, miny, maxx, maxy)
    except ValueError:
        return None


def save_existing_data_to_postgis(
    conn: psycopg.Connection,
    existing_data: Dict[str, Any],
    srid: int = 4258,
) -> Dict[str, Any]:
    """
    Zapisuje existing_data do tabel (bez constraintów):
      1) aukcje
      2) aukcje_meta
      3) nieruchomosci
      4) adres
      5) aukcja_nieruchomosc

    UWAGA: Bez PK/UNIQUE/FK nie ma upsertu – będą możliwe duplikaty.
    """
    print("Zapisuję do PostGIS...")
    print("ID aukcji:", existing_data.get("auction_id"))
    id_aukcji = str(existing_data.get("auction_id"))
        
    
    if not isinstance(id_aukcji, str) or not id_aukcji.strip():
        raise ValueError("Brak id_aukcji w existing_data (np. existing_data['id_aukcji']).")

    dluznik = (
        existing_data.get("dluznik")
        or (existing_data.get("aukcja") or {}).get("dluznik")
    )

    meta = existing_data.get("metadata") 
    if not isinstance(meta, dict):
        meta = {}

    adres_src = existing_data.get("adres_nieruchomosci") or {}
    nieruchomosci = existing_data.get("nieruchomosci") or []
    if not isinstance(nieruchomosci, list):
        raise ValueError("existing_data['nieruchomosci'] musi być listą.")

    inserted_nieruchomosci_ids = []

    with conn.transaction():
        # 1) aukcje - zawsze INSERT (append-only)
        conn.execute(
            "INSERT INTO aukcje (id_aukcji, dluznik) VALUES (%s, %s)",
            (id_aukcji, dluznik),
        )

        # 2) aukcje_meta - zawsze INSERT (append-only)
        for k, v in meta.items():
            conn.execute(
                "INSERT INTO aukcje_meta (id_aukcji, name, value) VALUES (%s, %s, %s)",
                (id_aukcji, str(k), None if v is None else str(v)),
            )

        # 3) nieruchomosci + 4) adres + 5) relacja
        for obj in nieruchomosci:
            if not isinstance(obj, dict):
                continue
                
            obreb =   adres_src.get("obreb")
            nr_dzialki = obj.get("nr_dzialki")
            

            teryt = f"{obreb.strip()}.{nr_dzialki.strip()}"
            powierzchnia = obj.get("powierzchnia")
            nr_kw = obj.get("nr_ksiegi_wieczystej")
                
            

            extent = _parse_extent(obj.get("geom_extent"))
            geom_wkb_hex = obj.get("geom_wkb") or obj.get("geom")  # jeśli czasem pod kluczem "geom"

            row = conn.execute(
                """
                INSERT INTO nieruchomosci (
                  teryt, powierzchnia, nr_ksiegi_wieczystej, geom_extent, geom
                )
                VALUES (
                  %s,
                  %s,
                  %s,
                  CASE
                    WHEN %s IS NULL THEN NULL
                    ELSE ST_MakeEnvelope(%s, %s, %s, %s, %s)
                  END,
                  CASE
                    WHEN %s IS NULL THEN NULL
                    ELSE ST_SetSRID(ST_GeomFromWKB(decode(%s, 'hex')), %s)
                  END
                )
                RETURNING id_nieruchomosci
                """,
                (
                    teryt,
                    powierzchnia,
                    nr_kw,
                    None if extent is None else 1,
                    None if extent is None else extent[0],
                    None if extent is None else extent[1],
                    None if extent is None else extent[2],
                    None if extent is None else extent[3],
                    int(srid),
                    None if geom_wkb_hex is None else 1,
                    None if geom_wkb_hex is None else geom_wkb_hex,
                    int(srid),
                ),
            ).fetchone()

            id_nieruchomosci = row[0]
            inserted_nieruchomosci_ids.append(id_nieruchomosci)

            # 4) adres - zawsze INSERT (append-only)
            conn.execute(
                """
                INSERT INTO adres (
                  id_dzialki, wojewodztwo, powiat, gmina, miejscowosc, ulica_wies, nr_budynku, obreb
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    id_nieruchomosci,
                    adres_src.get("wojewodztwo"),
                    adres_src.get("powiat"),
                    adres_src.get("gmina"),
                    adres_src.get("miejscowosc"),
                    adres_src.get("ulica_wieś") or adres_src.get("ulica_wies"),
                    adres_src.get("nr_budynku"),
                    adres_src.get("obreb"),
                ),
            )

            # 5) aukcja_nieruchomosc - zawsze INSERT (append-only)
            conn.execute(
                "INSERT INTO aukcja_nieruchomosc (id_aukcji, id_nieruchomosci) VALUES (%s, %s)",
                (id_aukcji, id_nieruchomosci),
            )

    # opcjonalnie: zwróć id w existing_data do debugowania / dalszego użycia
    existing_data.setdefault("_db", {})["inserted_nieruchomosci_ids"] = inserted_nieruchomosci_ids
    return existing_data



def _uldk_get_parcel_by_id(parcel_id: str, srid: int = 4258, timeout: int = 20) -> Tuple[str, str, str, str]:
    """
    Zwraca: (returned_id, geom_extent, geom_wkb, final_url)
    Rzuca wyjątek jeśli status != 0 lub zły format odpowiedzi.
    """
    base_url = "https://uldk.gugik.gov.pl/"
    params = {
        "request": "GetParcelById",
        "id": parcel_id,
        "result": "teryt,geom_extent,geom_wkb",
        "srid": str(int(srid)),
    }

    resp = requests.get(base_url, params=params, timeout=timeout)
    resp.raise_for_status()

    lines = [ln.strip() for ln in (resp.text or "").splitlines() if ln.strip()]
    if len(lines) < 2:
        raise ValueError(f"Nieoczekiwana odpowiedź ULDK (za mało linii): {resp.text!r}")

    status = lines[0]
    if status != "0":
        raise ValueError(f"ULDK zwrócił status={status}. Odpowiedź: {resp.text!r}")

    payload = lines[1]
    parts = payload.split("|")
    if len(parts) < 3:
        raise ValueError(f"Nieoczekiwany format payload: {payload!r}")

    returned_id = parts[0].strip()
    geom_extent = parts[1].strip()
    geom_wkb = parts[2].strip()

    return returned_id, geom_extent, geom_wkb, resp.url


def query_uldk(
    existing_data: Dict[str, Any],
    srid: int = 4258,
    timeout: int = 20,
) -> Dict[str, Any]:
    """
    Dla każdego obiektu w existing_data["nieruchomosci"] pobiera geometrię z ULDK
    i dopisuje ją do tego obiektu.

    Wymaga:
      existing_data["adres_nieruchomosci"]["obreb"] = np. "142904_2.0022"
      existing_data["nieruchomosci"][i]["nr_dzialki"] = np. "167"
    """
    adres = existing_data.get("adres_nieruchomosci") or {}
    obreb = adres.get("obreb")

    if not isinstance(obreb, str) or not obreb.strip():
        raise ValueError("Brak existing_data['adres_nieruchomosci']['obreb'] (np. '142904_2.0022').")

    nieruchomosci = existing_data.get("nieruchomosci") or []
    if not isinstance(nieruchomosci, list):
        raise ValueError("existing_data['nieruchomosci'] musi być listą.")

    for obj in nieruchomosci:
        if not isinstance(obj, dict):
            continue

        nr_dzialki = obj.get("nr_dzialki")
        if not isinstance(nr_dzialki, str) or not nr_dzialki.strip():
            obj["uldk_error"] = "Brak nr_dzialki"
            continue

        parcel_id = f"{obreb.strip()}.{nr_dzialki.strip()}"

        try:
            returned_id, geom_extent, geom_wkb, final_url = _uldk_get_parcel_by_id(
                parcel_id=parcel_id,
                srid=srid,
                timeout=timeout,
            )

            # dopisz do konkretnej nieruchomości (obiektu na liście)
            #obj["uldk_id"] = returned_id
            obj["geom_extent"] = geom_extent
            obj["geom_wkb"] = geom_wkb
            obj["srid"] = int(srid)
            #obj["uldk_url"] = final_url

            # jeśli był błąd wcześniej, usuń
            obj.pop("uldk_error", None)

        except Exception as e:
            obj["uldk_error"] = str(e)

    return existing_data





def fetch_obreb(
    conn: psycopg.Connection,
    existing_data: Optional[Dict[str, Any]] = None,
    limit: int = 50,
    wojewodztwo: Optional[str] = None,
    powiat: Optional[str] = None,
    gmina: Optional[str] = None,
    miejscowosc: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Pobiera rekordy z a06_granice_obrebow_ewidencyjnych dla danej nazwy (case-insensitive),
    i opcjonalnie filtruje po województwie (prefix jpt_kod_je = kod województwa),
    jeśli województwo jest obecne w JSON (existing_data["adres_nieruchomosci"]["wojewodztwo"]).

    Zwraca listę słowników (dict_row).
    """
    existing_data = existing_data or {}

    woj_kod = None
    print("step1.85")
    if isinstance(wojewodztwo, str) and wojewodztwo.strip():
        woj_kod = WOJ_KODY.get(wojewodztwo.strip().lower())

    sql = """
        SELECT jpt_kod_je, jpt_nazwa_
        FROM a06_granice_obrebow_ewidencyjnych
        WHERE LOWER(jpt_nazwa_) = LOWER(%s)
    """

    print("step1.9")
    print("miejscowosc do filtrowania:", miejscowosc)
    params: List[Any] = [miejscowosc.strip()]  # miejscowosc jest obowiązkowa do filtrowania

    if woj_kod:
        sql += " AND jpt_kod_je LIKE %s"
        params.append(f"{woj_kod}%")

    sql += " LIMIT %s"
    params.append(int(limit))

    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def update_obreb(existing_data: Dict[str, Any], woj: str, miej: str) -> None:
    with psycopg.connect(DSN) as conn:
            rows = fetch_obreb(
                conn,
                existing_data=existing_data,
                wojewodztwo=woj,
                miejscowosc=miej,
                limit=20,
            )

            liczba = len(rows)
            print(f"Liczba znalezionych rekordów: {liczba}")
            print("step1.75")
            if liczba == 1:
                obreb = rows[0]["jpt_kod_je"]  # 

                existing_data.setdefault("adres_nieruchomosci", {})["obreb"] = obreb

                print(f"Uzupełniono obręb: {obreb}")
            elif liczba == 0:
                print("Nie znaleziono obrębu. dla aukcji ID=%s" % existing_data.get("auction_id"))

            else:
                print("Znaleziono więcej niż jeden obręb — wymagane doprecyzowanie. Dla aukcji ID=%s" % existing_data.get("auction_id"))



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
                model="gpt-5-mini",
                input=[
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": USER_TEMPLATE_STATIC},
                {"role": "user", "content": text},
            ]
            )
        
        print(r.usage   )
        print(r.output)


        json_text = getattr(r, "output_text", None)

        # 2️jeśli None → ręczne wyciąganie
        if not json_text:
            chunks = []
            print("step0")
            for item in r.output:
                if getattr(item, "type", None) == "message":
                    for content in getattr(item, "content", []) or []:
                        if getattr(content, "type", None) == "output_text":
                            chunks.append(getattr(content, "text", ""))

            json_text = "".join(chunks)

        # 3️teraz masz tekst (o ile model coś zwrócił)
        if not json_text:
            raise ValueError("Brak tekstu w odpowiedzi modelu.")

        print(type(json_text))
        data = json.loads(json_text.strip())

        print("Wyciągnięte dane:", )

        json_path = file_path.with_suffix(".json")

        if json_path.exists():
            with json_path.open("r", encoding="utf-8") as f:
                existing_data = json.load(f)
        else:
            existing_data = {}


        # scal dane z istniejącym plikiem JSON, jeśli istnieje
        existing_data.update(data)

        lok = existing_data.get("metadata", {}).get("Lokalizacja", "")

        match = re.search(r"\((.*?)\)", lok)
        woj = match.group(1) if match else None

        print("step1")
        existing_data.setdefault("adres_nieruchomosci", {}).setdefault("wojewodztwo", woj) 

        adres = existing_data.setdefault("adres_nieruchomosci", {})

        print("step1.5")

        # 1️pierwsza próba — po ulica_wieś
        ulica_wies = adres.get("ulica_wieś")
        if isinstance(ulica_wies, str) and ulica_wies.strip():
            update_obreb(
                existing_data,
                woj,
                adres.get("ulica_wieś")
            )
        print("step2")
        # 2️sprawdzenie czy obręb został ustawiony
        if not adres.get("obreb"):
            print("Nie znaleziono obrębu po ulicy/wsi — próbuję po miejscowości...")

            update_obreb(
                existing_data,
                woj,
                adres.get("miejscowosc")
            )

        # 3️finalna walidacja
        if adres.get("obreb"):
            print(f"Znaleziono obręb: {adres['obreb']}")

            existing_data = query_uldk(existing_data)
            existing_data = save_existing_data_to_postgis(psycopg.connect(DSN), existing_data)
        else:
            print("Nie udało się znaleźć obrębu.")

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
