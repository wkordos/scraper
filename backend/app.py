import os
from pathlib import Path
from flask import Flask, send_from_directory, request, jsonify
import psycopg2
import psycopg2.extras

BASE_DIR = Path(__file__).resolve().parent

# Zmień <app-name> na nazwę folderu z dist (sprawdź w scraper/frontend/dist)
ANGULAR_DIST_DIR = (BASE_DIR / ".." / "frontend" / "dist").resolve()

FRONTEND_ROOT = (ANGULAR_DIST_DIR / "frontEnd" / "browser").resolve()  

DB_DSN = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/gis"
)

app = Flask(
    __name__,
    static_folder=str(FRONTEND_ROOT),   # statyki Angulara
    static_url_path=""                  # serwuj je z root-a (/, /assets, /main.js itd.)
)

@app.route("/health")
def health():
    return {"status": "ok"}

# Serwowanie plików statycznych (js/css/assets) + fallback do index.html dla routingu Angulara
@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_angular(path: str):
    file_path = FRONTEND_ROOT / path

    # jeśli istnieje plik (np. main.js, styles.css, assets/*) -> zwróć go
    if path and file_path.exists() and file_path.is_file():
        return send_from_directory(FRONTEND_ROOT, path)

    # inaczej -> Angular routing (SPA) -> index.html
    return send_from_directory(FRONTEND_ROOT, "index.html")

def parse_bbox(bbox_str: str):
    """
    bbox format: minLon,minLat,maxLon,maxLat
    """
    parts = [p.strip() for p in bbox_str.split(",")]
    if len(parts) != 4:
        raise ValueError("bbox must have 4 comma-separated values: minLon,minLat,maxLon,maxLat")

    min_lon, min_lat, max_lon, max_lat = map(float, parts)

    # prosta walidacja
    if min_lon >= max_lon or min_lat >= max_lat:
        raise ValueError("bbox is invalid: minLon < maxLon and minLat < maxLat required")

    return min_lon, min_lat, max_lon, max_lat

def limit_for_zoom(zoom: int) -> int:
    """
    Prosty limit zależny od zoomu, żeby nie zabić frontu tysiącami poligonów.
    Dopasuj do swoich danych.
    """
    if zoom <= 10:
        return 500
    if zoom <= 13:
        return 2000
    return 5000

@app.get("/api/properties")
def get_properties():
    bbox_str = request.args.get("bbox")
    zoom_str = request.args.get("zoom", "12")

    if not bbox_str:
        return jsonify({"error": "Missing required query param: bbox"}), 400

    try:
        zoom = int(zoom_str)
    except ValueError:
        return jsonify({"error": "zoom must be an integer"}), 400

    try:
        min_lon, min_lat, max_lon, max_lat = parse_bbox(bbox_str)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    limit = limit_for_zoom(zoom)

    # Jeśli masz SRID inny niż 4326, to:
    # - envelope robisz w 4326 (bo bbox z Leaflet jest 4326),
    # - a geometrię w bazie transformujesz do 4326 albo envelope do SRID geometrii.
    # Na start zakładamy SRID=4326 w geom.
    sql = """
        SELECT
            id_nieruchomosci AS id,
            -- geometry -> GeoJSON
            ST_AsGeoJSON(geom)::json AS geometry,
            -- properties jako json (dodaj tu kolumny jakie chcesz)
            jsonb_build_object(
                'id_nieruchomosci', id_nieruchomosci
            ) AS properties
        FROM nieruchomosci
        WHERE geom IS NOT NULL
          AND ST_Intersects(
                geom,
                ST_MakeEnvelope(%s, %s, %s, %s, 4258)
          )
        LIMIT %s
    """

    try:
        with psycopg2.connect(DB_DSN) as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, (min_lon, min_lat, max_lon, max_lat, limit))
                rows = cur.fetchall()
    except Exception as e:
        # na start zwracamy info, w produkcji lepiej logować i zwracać generyczny błąd
        return jsonify({"error": "Database query failed", "details": str(e)}), 500

    # składamy FeatureCollection
    features = []
    for r in rows:
        features.append({
            "type": "Feature",
            "geometry": r["geometry"],
            "properties": r["properties"] or {}
        })

    return jsonify({
        "type": "FeatureCollection",
        "features": features
    })



if __name__ == "__main__":
    # dev server
    print("hello")
    app.run(host="0.0.0.0", port=8000, debug=True)