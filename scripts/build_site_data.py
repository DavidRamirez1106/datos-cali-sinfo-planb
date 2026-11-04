#!/usr/bin/env python3
"""Convierte lago/clean + lago/manifest.json en los JSON que lee el sitio.

Cada archivo de site/data/ lleva el ID de su fuente; sources.json (de salida)
reúne la ficha de cada fuente: licencia copiada de la API, vigencia y fecha
real de prueba. El sitio no muestra ninguna cifra sin esa ficha.
"""
import argparse
import csv
import json
import os
import shutil
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read_csv(path):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def num(v):
    return None if v in ("", None) else float(v)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lago", default=os.path.join(ROOT, "lago"))
    ap.add_argument("--out", default=os.path.join(ROOT, "site", "data"))
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    manifest = json.load(open(os.path.join(a.lago, "manifest.json"), encoding="utf-8"))
    cfg = json.load(open(os.path.join(ROOT, "sources.json"), encoding="utf-8"))
    clean = os.path.join(a.lago, "clean")
    ok = {sid for sid, s in manifest["sources"].items() if s["status"] == "ok"}
    status = {"mode": manifest["mode"], "snapshot": manifest.get("snapshot"), "built_from_run": manifest.get("run_finished"), "available": sorted(ok),
              "failed": {sid: s.get("error", "") for sid, s in manifest["sources"].items() if s["status"] != "ok"}}

    # --- fichas de fuente
    fichas = {}
    for s in cfg["sources"]:
        m = manifest["sources"].get(s["id"])
        if not m or m["status"] != "ok":
            continue
        fichas[s["id"]] = {
            "id": s["id"], "name": s["name"], "entity": s["entity"],
            "license": m["license_title"], "periodo": s["periodo"],
            "vigencia": m.get("metadata_modified") or "sin dato",
            "tested_at": m["tested_at"], "url": m.get("package_url", ""), "url_used": m.get("url_used", ""),
            "method": m.get("method", ""), "rows": m.get("rows_clean"),
        }
        if m.get("method") == "copia_local":
            fichas[s["id"]]["nota"] = ("Copia descargada a mano el %s; el portal de la Alcaldía está fuera de línea desde el 21 de octubre de 2026."
                                       % m["tested_at"])
    json.dump(fichas, open(os.path.join(a.out, "fuentes.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(status, open(os.path.join(a.out, "status.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    # --- F01 homicidios
    if "F01" in ok:
        rows = read_csv(os.path.join(clean, "F01_homicidios_comuna.csv"))
        by = defaultdict(dict)
        names = {}
        for r in rows:
            if r["comuna_id"] == "":
                continue  # zonas que no son comunas no van al mapa
            cid = int(r["comuna_id"])
            by[cid][int(r["anio"])] = int(r["homicidios"])
            names[cid] = r["comuna"]
        years = sorted({y for d in by.values() for y in d})
        out = {"source": "F01", "years": years, "corte": cfg.get("calidad", {}).get("F01"),
               "ciudad": {str(y): sum(by[c][y] for c in by if y in by[c]) for y in years},
               "comunas": [{"id": c, "nombre": names[c], "serie": {str(y): v for y, v in sorted(by[c].items())},
                            "total": sum(by[c].values())} for c in sorted(by)]}
        json.dump(out, open(os.path.join(a.out, "homicidios.json"), "w", encoding="utf-8"), ensure_ascii=False)

    # --- F03 ICA
    if "F03" in ok:
        rows = read_csv(os.path.join(clean, "F03_ica_estaciones.csv"))
        sums = defaultdict(lambda: defaultdict(list))
        for r in rows:
            sums[r["estacion"]][r["fecha"][:7]].append(float(r["ica"]))
        # promedio mensual de los días con dato (el ICA de la fuente es diario)
        by = {e: {mm: sum(v) / len(v) for mm, v in ms.items()} for e, ms in sums.items()}
        months = sorted({m for d in by.values() for m in d})
        allm = []
        if months:
            y, m = map(int, months[0].split("-"))
            ye, me = map(int, months[-1].split("-"))
            while (y, m) <= (ye, me):
                allm.append(f"{y}-{m:02d}")
                m += 1
                if m == 13:
                    y, m = y + 1, 1
        out = {"source": "F03", "months": allm,
               "estaciones": [{"nombre": e, "valores": [by[e].get(mm) for mm in allm],
                               "con_dato": len(by[e]), "promedio": round(sum(by[e].values()) / len(by[e]), 1)}
                              for e in sorted(by)]}
        json.dump(out, open(os.path.join(a.out, "ica.json"), "w", encoding="utf-8"), ensure_ascii=False)

    # --- F04 educación
    if "F04" in ok:
        rows = read_csv(os.path.join(clean, "F04_programas_etdh.csv"))
        inst, jor = defaultdict(int), defaultdict(int)
        for r in rows:
            inst[r["institucion"]] += 1
            for j in filter(None, r["jornadas"].split(";")):
                jor[j] += 1
        top = sorted(inst.items(), key=lambda kv: (-kv[1], kv[0]))[:12]
        out = {"source": "F04", "programas": len(rows), "instituciones": len(inst),
               "top_instituciones": [{"nombre": n, "programas": c} for n, c in top],
               "jornadas": [{"jornada": j, "programas": c} for j, c in sorted(jor.items(), key=lambda kv: -kv[1])]}
        json.dump(out, open(os.path.join(a.out, "educacion.json"), "w", encoding="utf-8"), ensure_ascii=False)

    # --- F09 población
    if "F09" in ok:
        rows = read_csv(os.path.join(clean, "F09_poblacion_censos.csv"))
        out = {"source": "F09", "censos": [{"anio": int(r["anio_censo"]), "total": num(r["poblacion_total"]),
                                             "cabecera": num(r["poblacion_cabecera"]), "resto": num(r["poblacion_resto"]),
                                             "pct_cabecera": num(r["pct_cabecera"])} for r in rows]}
        json.dump(out, open(os.path.join(a.out, "poblacion.json"), "w", encoding="utf-8"), ensure_ascii=False)

    # --- F11 comunas
    if "F11" in ok:
        shutil.copy(os.path.join(clean, "comunas.geojson"), os.path.join(a.out, "comunas.geojson"))
    print("site/data listo:", sorted(os.listdir(a.out)))


if __name__ == "__main__":
    main()
