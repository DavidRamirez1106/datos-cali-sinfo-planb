#!/usr/bin/env python3
"""Ingesta del lago de datos de Cali.

Descarga cada fuente de sources.json, la limpia y escribe:
  lago/raw/<ID>.json            respuesta cruda (para poder auditar)
  lago/clean/<archivo>          tabla limpia (lo que describe el diccionario)
  lago/manifest.json            qué respondió, cuándo, con qué licencia

Solo usa la biblioteca estándar. No usa llaves ni cuentas.

Uso:
  python scripts/ingest.py                      # descarga real
  python scripts/ingest.py --fixtures tests/fixtures --out /tmp/lago_prueba
                                                # datos SINTÉTICOS de prueba (nunca para entregar)
"""
import argparse
import csv
import hashlib
import io
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Algunos portales rechazan (403) a clientes que no parecen navegador; se puede cambiar con la variable UA.
UA = os.environ.get("UA") or ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                              "Chrome/120.0 Safari/537.36 cali-lago-taller/1.0 (proyecto academico)")
BOGOTA = timezone(timedelta(hours=-5))


# ---------------------------------------------------------------- descarga
class FetchError(Exception):
    pass


class LiveFetcher:
    mode = "live"

    def get(self, url, retries=3):
        last = None
        for i in range(retries):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
                with urllib.request.urlopen(req, timeout=60) as r:
                    return r.status, r.read()
            except urllib.error.HTTPError as e:
                last = f"HTTP {e.code}"
                if e.code in (400, 401, 403, 404):
                    break
            except Exception as e:  # red, DNS, timeout
                last = f"{type(e).__name__}: {e}"
            time.sleep(2 * (i + 1))
        raise FetchError(last or "error desconocido")


class FixtureFetcher:
    """Lee respuestas sintéticas guardadas en disco. Solo para pruebas."""
    mode = "fixtures"

    def __init__(self, folder):
        self.folder = folder

    def get(self, url, retries=1):
        key = None
        if "package_show" in url:
            key = re.search(r"id=([^&]+)", url).group(1) + ".package.json"
        elif "datastore_search" in url:
            rid = re.search(r"resource_id=([^&]+)", url).group(1)
            off = int(re.search(r"offset=(\d+)", url).group(1)) if "offset=" in url else 0
            key = f"{rid}.datastore.{off}.json"
        elif "geojson" in url.lower() or "geospatial" in url:
            key = "comunas.geojson"
        path = os.path.join(self.folder, key) if key else None
        if not path or not os.path.exists(path):
            raise FetchError(f"sin fixture para {url}")
        with open(path, "rb") as f:
            return 200, f.read()


def today_bogota():
    return datetime.now(BOGOTA).strftime("%Y-%m-%d")


def sha256(b):
    return hashlib.sha256(b).hexdigest()


# ---------------------------------------------------------------- utilidades
def to_float(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace(",", ".")
    if s == "" or s.upper() in ("ND", "N/D", "NA", "N.A.", "-", "NULL"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def to_int(v):
    f = to_float(v)
    return None if f is None else int(round(f))


def clean_text(v):
    if v is None:
        return ""
    return re.sub(r"\s+", " ", str(v)).strip()


def pop_value(v):
    """Las poblaciones del portal vienen con punto de miles ('637.929').
    En el datastore pueden llegar como número 637.929 (= 637929)."""
    if v is None:
        return None
    if isinstance(v, str):
        s = v.strip()
        if s == "" or s.upper() == "ND":
            return None
        if re.fullmatch(r"\d{1,3}(\.\d{3})+", s):
            return int(s.replace(".", ""))
        f = to_float(s)
        if f is None:
            return None
        v = f
    v = float(v)
    return int(round(v * 1000)) if v < 1000 else int(round(v))


def pct_value(v):
    if v is None:
        return None
    s = str(v).replace("%", "").strip()
    return to_float(s)


# ---------------------------------------------------------------- CKAN
def ckan_package(fetcher, portal, package):
    url = f"{portal}/api/3/action/package_show?id={urllib.parse.quote(package)}"
    status, body = fetcher.get(url)
    res = json.loads(body)["result"]
    return {
        "license_title": res.get("license_title") or "no declara",
        "metadata_modified": (res.get("metadata_modified") or "")[:10],
        "organization": (res.get("organization") or {}).get("title", ""),
        "package_url": f"{portal}/dataset/{package}",
    }


def ckan_datastore(fetcher, portal, resource_id):
    records, offset, total = [], 0, None
    first_url = None
    while True:
        url = (f"{portal}/api/3/action/datastore_search?resource_id={resource_id}"
               f"&limit=1000&offset={offset}")
        first_url = first_url or url
        status, body = fetcher.get(url)
        data = json.loads(body)
        if not data.get("success"):
            raise FetchError("datastore_search respondió success=false")
        res = data["result"]
        total = res.get("total", len(res["records"]))
        records.extend(res["records"])
        offset += len(res["records"])
        if not res["records"] or offset >= total:
            break
    return records, first_url, status


def csv_fallback(fetcher, url):
    status, body = fetcher.get(url)
    text = body.decode("utf-8-sig", errors="replace")
    return list(csv.DictReader(io.StringIO(text))), url, status


# ---------------------------------------------------------------- limpiezas
F01_ULTIMO_ANIO = 2018  # 2019-2021 no son creíbles (múltiplos exactos del número de comuna); ver sources.json > calidad


def clean_f01(records):
    """Homicidios por comuna y año (largo). Toma solo las columnas 'Total AAAA'."""
    rows = []
    for r in records:
        name = clean_text(r.get("Comuna"))
        if not name or name.lower().startswith("total"):
            continue  # evita contar dos veces la fila de totales
        m = re.search(r"(\d+)", name)
        cid = int(m.group(1)) if m and name.lower().startswith("comuna") else ""
        for k, v in r.items():
            ym = re.fullmatch(r"Total (\d{4})", str(k).strip())
            if ym and int(ym.group(1)) <= F01_ULTIMO_ANIO:
                val = to_int(v)
                if val is not None:
                    rows.append({"comuna_id": cid, "comuna": name, "anio": int(ym.group(1)),
                                 "homicidios": val})
    return rows


def clean_f03(records):
    """ICA mensual por estación (largo). 'ND' y los ceros se descartan (faltantes, no se imputan).

    Un ICA de 0 no es aire perfecto: es un valor que la estación no midió
    (criterio del profesor en la retroalimentación de la visualización)."""
    rows = []
    skip = {"_id", "id", "Fecha", "_full_text"}
    for r in records:
        fecha = clean_text(r.get("Fecha"))[:10]
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", fecha):
            continue
        for k, v in r.items():
            if k in skip:
                continue
            val = to_float(v)
            if val is not None and val > 0:
                rows.append({"fecha": fecha, "estacion": clean_text(k), "ica": val})
    return rows


def clean_f04(records):
    rows, seen = [], set()
    for r in records:
        jor = []
        for k in ("jornada_1", "jornada_2", "jornada_3"):
            j = clean_text(r.get(k)).lower()
            if j and j not in jor:
                jor.append(j)
        row = {
            "codigo_institucion": clean_text(r.get("codigo_institucion")),
            "institucion": clean_text(r.get("nombre_institucion")).lower(),
            "codigo_programa": clean_text(r.get("codigo_programa")),
            "programa": clean_text(r.get("nombre_programa")).lower(),
            "tipo_certificado": clean_text(r.get("tipo_certificado")),
            "jornadas": ";".join(jor),
        }
        key = tuple(row.values())
        if row["institucion"] and key not in seen:
            seen.add(key)
            rows.append(row)
    return rows


def clean_f09(records):
    rows = []
    for r in records:
        anio = to_int(r.get("Año"))
        if anio is None:
            continue
        rows.append({
            "anio_censo": anio,
            "poblacion_total": pop_value(r.get("Población total")),
            "poblacion_cabecera": pop_value(r.get("Población cabecera")),
            "poblacion_resto": pop_value(r.get("Población resto")),
            "pct_cabecera": pct_value(r.get("% Cabecera")),
        })
    rows.sort(key=lambda x: x["anio_censo"])
    return rows


CLEANERS = {"F01": clean_f01, "F03": clean_f03, "F04": clean_f04, "F09": clean_f09}


def write_csv(path, rows):
    if not rows:
        raise FetchError("la limpieza no produjo filas")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


# ---------------------------------------------------------------- comunas (geometría)
COMUNA_KEYS = ["comuna", "id_comuna", "cod_comuna", "codigo", "nombre", "nom_comuna", "name", "id"]


def round_coords(c, n=5):
    if isinstance(c, (int, float)):
        return round(c, n)
    return [round_coords(x, n) for x in c]


def first_coord(c):
    while isinstance(c, list) and c and isinstance(c[0], list):
        c = c[0]
    return c


def clean_comunas(gj):
    if gj.get("type") != "FeatureCollection" or not gj.get("features"):
        raise FetchError("la respuesta no es un FeatureCollection con polígonos")
    feats = gj["features"]
    chosen = None
    for key in COMUNA_KEYS:
        ids = []
        for ft in feats:
            props = {str(k).lower(): v for k, v in (ft.get("properties") or {}).items()}
            m = re.search(r"(\d{1,2})", str(props.get(key, "")))
            ids.append(int(m.group(1)) if m else None)
        ok = [i for i in ids if i and 1 <= i <= 22]
        if len(set(ok)) >= 20:
            chosen = key
            break
    if not chosen:
        names = sorted({k for ft in feats for k in (ft.get("properties") or {})})
        raise FetchError(f"no se pudo identificar la comuna en las propiedades: {names}")
    out = []
    for ft in feats:
        props = {str(k).lower(): v for k, v in (ft.get("properties") or {}).items()}
        m = re.search(r"(\d{1,2})", str(props.get(chosen, "")))
        cid = int(m.group(1)) if m else None
        if not cid or not 1 <= cid <= 22 or not ft.get("geometry"):
            continue
        x, y = first_coord(ft["geometry"]["coordinates"])[:2]
        if abs(x) > 180 or abs(y) > 90:
            raise FetchError("las coordenadas no están en WGS84 (EPSG:4326); pedir el GeoJSON en 4326")
        geom = {"type": ft["geometry"]["type"], "coordinates": round_coords(ft["geometry"]["coordinates"])}
        out.append({"type": "Feature", "properties": {"comuna_id": cid, "nombre": f"Comuna {cid}"},
                    "geometry": geom})
    if len({f["properties"]["comuna_id"] for f in out}) < 20:
        raise FetchError("menos de 20 comunas con geometría")
    return {"type": "FeatureCollection", "features": out}, chosen


# ---------------------------------------------------------------- orquestación
def run(fetcher, out_dir, only=None):
    cfg = json.load(open(os.path.join(ROOT, "sources.json"), encoding="utf-8"))
    portal = cfg["portal"]
    raw_dir, clean_dir = os.path.join(out_dir, "raw"), os.path.join(out_dir, "clean")
    os.makedirs(raw_dir, exist_ok=True)
    os.makedirs(clean_dir, exist_ok=True)
    manifest = {"mode": fetcher.mode, "run_started": datetime.now(BOGOTA).isoformat(timespec="seconds"),
                "sources": {}}
    for src in cfg["sources"]:
        sid = src["id"]
        if not src.get("integrated") or (only and sid not in only):
            continue
        entry = {"status": "error", "name": src["name"], "entity": src["entity"], "periodo": src["periodo"]}
        manifest["sources"][sid] = entry
        try:
            try:
                entry.update(ckan_package(fetcher, portal, src["package"]))
            except Exception as e:
                entry["package_error"] = str(e)
                entry["license_title"] = "no declara"  # no se supone una licencia
            if src["kind"] == "ckan_datastore":
                try:
                    records, url, status = ckan_datastore(fetcher, portal, src["resource_id"])
                    method = "datastore_search"
                except Exception as e:
                    entry["datastore_error"] = str(e)
                    records, url, status = csv_fallback(fetcher, src["csv_fallback"])
                    method = "csv_directo"
                raw = json.dumps(records, ensure_ascii=False).encode("utf-8")
                with open(os.path.join(raw_dir, f"{sid}.json"), "wb") as f:
                    f.write(raw)
                rows = CLEANERS[sid](records)
                write_csv(os.path.join(clean_dir, src["clean_file"]), rows)
                entry.update(method=method, url_used=url, http_status=status, rows_raw=len(records),
                             rows_clean=len(rows), sha256_raw=sha256(raw))
            else:  # geojson_candidates
                urls = []
                if os.environ.get(src.get("override_env", "")):
                    urls.append(os.environ[src["override_env"]])
                urls += src["candidates"]
                errors, gj, used = [], None, None
                for u in urls:
                    try:
                        status, body = fetcher.get(u, retries=2)
                        gj, used = json.loads(body), u
                        raw = body
                        break
                    except Exception as e:
                        errors.append(f"{u} -> {e}")
                if gj is None:
                    raise FetchError("ninguna URL de comunas respondió: " + " | ".join(errors))
                with open(os.path.join(raw_dir, f"{sid}.json"), "wb") as f:
                    f.write(raw)
                fc, key = clean_comunas(gj)
                with open(os.path.join(clean_dir, src["clean_file"]), "w", encoding="utf-8") as f:
                    json.dump(fc, f, ensure_ascii=False, separators=(",", ":"))
                entry.update(method="geojson", url_used=used, http_status=status, rows_raw=len(gj["features"]),
                             rows_clean=len(fc["features"]), sha256_raw=sha256(raw), campo_comuna=key)
            entry["status"] = "ok"
            entry["tested_at"] = today_bogota()  # solo si la fuente respondió de verdad
        except Exception as e:
            entry["error"] = str(e)
            print(f"[{sid}] ERROR: {e}", file=sys.stderr)
        print(f"[{sid}] {entry['status']}" + (f" ({entry.get('method')}, {entry.get('rows_clean')} filas)"
                                               if entry["status"] == "ok" else ""))
    manifest["run_finished"] = datetime.now(BOGOTA).isoformat(timespec="seconds")
    with open(os.path.join(out_dir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    return manifest


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "lago"))
    ap.add_argument("--fixtures", help="carpeta con respuestas SINTÉTICAS (solo pruebas)")
    ap.add_argument("--only", nargs="*", help="IDs a descargar, p. ej. F01 F03")
    a = ap.parse_args()
    fetcher = FixtureFetcher(a.fixtures) if a.fixtures else LiveFetcher()
    m = run(fetcher, a.out, a.only)
    ok = sum(1 for s in m["sources"].values() if s["status"] == "ok")
    print(f"{ok}/{len(m['sources'])} fuentes integradas")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
