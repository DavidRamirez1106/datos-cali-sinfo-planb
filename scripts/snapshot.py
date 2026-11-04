#!/usr/bin/env python3
"""Copia local: llena el lago con los archivos que el grupo descargó a mano.

Se usa solo cuando el portal no responde (como desde el 21-oct-2026). Toma las
fuentes que la ingesta no pudo traer, lee su copia de copia_local/ (descargada y
limpiada por el grupo el 2026-10-06) y la convierte al formato de lago/clean.
La ficha de cada fuente dice la verdad: fecha de la copia, no de una descarga nueva.

  python scripts/snapshot.py            # rellena solo lo que falló
  python scripts/snapshot.py --force    # usa la copia para todo
"""
import argparse
import csv
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOGOTA = timezone(timedelta(hours=-5))
ULTIMO_ANIO_F01 = 2018  # 2019-2021 no son creíbles (ver sources.json > calidad.F01)


def read_csv(path):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path, header, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=header)
        w.writeheader()
        w.writerows(rows)


def conv_f01(rows):
    """comuna × año × sexo → comuna × año (suma de F y M). Quita los años dudosos.

    Si falta alguno de los dos sexos, el total del año queda vacío (no se supone 0)."""
    by = defaultdict(dict)
    names = {}
    for r in rows:
        if r["dato_dudoso"] == "1" or int(r["anio"]) > ULTIMO_ANIO_F01:
            continue
        key = (r["comuna"], int(r["anio"]))
        by[key][r["sexo"]] = int(float(r["homicidios"])) if r["homicidios"].strip() else None
        names[r["comuna"]] = r["comuna"]
    out = []
    for (comuna, anio), v in sorted(by.items(), key=lambda kv: (kv[0][0].zfill(3) if kv[0][0].isdigit() else "z" + kv[0][0], kv[0][1])):
        if len(v) < 2 or any(x is None for x in v.values()):
            continue
        cid = int(comuna) if comuna.isdigit() else ""
        nombre = f"Comuna {comuna}" if comuna.isdigit() else comuna
        out.append({"comuna_id": cid, "comuna": nombre, "anio": anio, "homicidios": sum(v.values())})
    return ["comuna_id", "comuna", "anio", "homicidios"], out


def conv_f03(rows):
    """Tabla ancha diaria → larga. Los ICA en 0 son faltantes (criterio del profesor)."""
    out = []
    for r in rows:
        fecha = r["fecha"]
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", fecha):
            continue
        for k, v in r.items():
            if k == "fecha" or not (v or "").strip():
                continue
            val = float(v)
            if val > 0:
                out.append({"fecha": fecha, "estacion": k.strip(), "ica": val})
    return ["fecha", "estacion", "ica"], out


def conv_f04(rows):
    out = []
    for r in rows:
        jor = []
        for k in ("jornada_1", "jornada_2", "jornada_3"):
            j = (r.get(k) or "").strip().lower()
            if j and j not in jor:
                jor.append(j)
        out.append({"codigo_institucion": r["codigo_institucion"], "institucion": r["nombre_institucion"],
                    "codigo_programa": r["codigo_programa"], "programa": r["nombre_programa"],
                    "tipo_certificado": r["tipo_certificado"], "jornadas": ";".join(jor)})
    return ["codigo_institucion", "institucion", "codigo_programa", "programa", "tipo_certificado", "jornadas"], out


def conv_f09(rows):
    out = [{"anio_censo": r["anio_censo"], "poblacion_total": r["poblacion_total"],
            "poblacion_cabecera": r["poblacion_cabecera"], "poblacion_resto": r["poblacion_resto"],
            "pct_cabecera": r["poblacion_cabecera_pct"]} for r in rows]
    return ["anio_censo", "poblacion_total", "poblacion_cabecera", "poblacion_resto", "pct_cabecera"], out


CONV = {"F01": ("F01_homicidios_comuna.csv", conv_f01), "F03": ("F03_ica_estaciones.csv", conv_f03),
        "F04": ("F04_programas_etdh.csv", conv_f04), "F09": ("F09_poblacion_censos.csv", conv_f09)}


def run(lago, copia_dir, force=False):
    cfg = json.load(open(os.path.join(copia_dir, "COPIA.json"), encoding="utf-8"))
    mpath = os.path.join(lago, "manifest.json")
    if os.path.exists(mpath):
        manifest = json.load(open(mpath, encoding="utf-8"))
    else:
        manifest = {"mode": "live", "sources": {}}
    used = []
    for sid, spec in cfg["fuentes"].items():
        cur = manifest["sources"].get(sid, {})
        if cur.get("status") == "ok" and not force:
            continue
        fname, conv = CONV[sid]
        header, rows = conv(read_csv(os.path.join(copia_dir, spec["archivo"])))
        write_csv(os.path.join(lago, "clean", fname), header, rows)
        manifest["sources"][sid] = {
            "status": "ok", "tested_at": cfg["descargada_el"], "license_title": spec["licencia"],
            "metadata_modified": None, "method": "copia_local", "rows_clean": len(rows),
            "package_url": "", "url_used": "copia_local/" + spec["archivo"]}
        used.append(sid)
    if used:
        manifest["mode"] = "snapshot"
        manifest["snapshot"] = {"sources": used, "descargada_el": cfg["descargada_el"], "motivo": cfg["motivo"]}
    manifest["run_finished"] = datetime.now(BOGOTA).isoformat(timespec="seconds")
    os.makedirs(lago, exist_ok=True)
    json.dump(manifest, open(mpath, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return used


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lago", default=os.path.join(ROOT, "lago"))
    ap.add_argument("--copia", default=os.path.join(ROOT, "copia_local"))
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    used = run(a.lago, a.copia, a.force)
    print("Copia local usada para:", used or "ninguna (todas las fuentes respondieron)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
