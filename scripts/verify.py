#!/usr/bin/env python3
"""Verificación del lago y del sitio. Sale con código 1 si algo falla.

Comprueba:
  1. Al menos 3 fuentes integradas de verdad (status ok, con fecha de prueba).
  2. Cada columna de lago/clean existe en dictionary.json y viceversa.
  3. Ningún campo de datos de personas (nombres, documentos, teléfonos...).
  4. Rangos y reglas por fuente (sin 'ND' sueltos, ICA 0-500, población creciente...).
  5. Cada archivo de site/data trae su ficha de fuente con licencia y fecha.
  6. Con --strict: el lago debe ser real (no de prueba) y las fuentes de
     personas en riesgo (F05, F06) no deben aparecer en ningún lado.
"""
import argparse
import csv
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PERSONAL = re.compile(r"(nombre_persona|nombres?_victima|c[eé]dula|documento|telef|celular|direcci[oó]n|correo|email|"
                      r"apellid|fecha_nacimiento|lider|lideresa|victima_)", re.I)
FORBIDDEN_SOURCES = ("F05", "F06")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lago", default=os.path.join(ROOT, "lago"))
    ap.add_argument("--site-data", default=os.path.join(ROOT, "site", "data"))
    ap.add_argument("--strict", action="store_true")
    a = ap.parse_args()
    errors, warns = [], []

    def err(m):
        errors.append(m)

    mpath = os.path.join(a.lago, "manifest.json")
    if not os.path.exists(mpath):
        print("FALLA: no existe lago/manifest.json (corre scripts/ingest.py)")
        sys.exit(1)
    manifest = json.load(open(mpath, encoding="utf-8"))
    dic = json.load(open(os.path.join(ROOT, "dictionary.json"), encoding="utf-8"))["files"]
    cfg = json.load(open(os.path.join(ROOT, "sources.json"), encoding="utf-8"))
    clean = os.path.join(a.lago, "clean")

    # 1. fuentes integradas
    good = {sid for sid, s in manifest["sources"].items() if s["status"] == "ok" and s.get("tested_at")}
    print(f"Fuentes integradas: {sorted(good)}")
    if len(good) < 3:
        err(f"solo {len(good)} fuentes integradas; el mínimo es 3")
    for sid, s in manifest["sources"].items():
        if s["status"] != "ok":
            warns.append(f"{sid} no se integró: {s.get('error', '')[:160]}")
        elif s.get("license_title") in (None, "", "no declara"):
            warns.append(f"{sid}: la API no declaró licencia (el Excel debe decir «no declara»)")

    # 2 y 3. diccionario vs archivos
    for fname, spec in dic.items():
        if spec["source"] not in good:
            continue
        path = os.path.join(clean, fname)
        if not os.path.exists(path):
            err(f"falta lago/clean/{fname}")
            continue
        names = [f["name"] for f in spec["fields"]]
        if fname.endswith(".csv"):
            with open(path, encoding="utf-8", newline="") as f:
                reader = csv.DictReader(f)
                header = reader.fieldnames
                rows = list(reader)
            if header != names:
                err(f"{fname}: columnas {header} no coinciden con el diccionario {names}")
            for h in header:
                if PERSONAL.search(h):
                    err(f"{fname}: columna que parece de personas: {h}")
            check_rows(fname, rows, err)
        else:
            gj = json.load(open(path, encoding="utf-8"))
            for ft in gj["features"]:
                extra = set(ft["properties"]) - {"comuna_id", "nombre"}
                if extra:
                    err(f"{fname}: propiedades no documentadas {extra}")
                    break
    on_disk = {f for f in os.listdir(clean) if not f.startswith(".")} if os.path.isdir(clean) else set()
    for f in on_disk - set(dic):
        err(f"lago/clean/{f} no está en el diccionario")

    # 5. site/data
    if os.path.isdir(a.site_data) and os.path.exists(os.path.join(a.site_data, "fuentes.json")):
        fichas = json.load(open(os.path.join(a.site_data, "fuentes.json"), encoding="utf-8"))
        for fn in os.listdir(a.site_data):
            if fn in ("fuentes.json", "status.json", "comunas.geojson") or not fn.endswith(".json"):
                continue
            d = json.load(open(os.path.join(a.site_data, fn), encoding="utf-8"))
            sid = d.get("source")
            f = fichas.get(sid)
            if not f:
                err(f"site/data/{fn}: no tiene ficha de fuente ({sid})")
            else:
                for k in ("license", "tested_at", "vigencia", "name"):
                    if not f.get(k):
                        err(f"ficha {sid} sin {k}")
        blob = json.dumps(fichas)
        for bad in FORBIDDEN_SOURCES:
            if bad in blob:
                err(f"{bad} (datos de personas en riesgo) no puede estar en el sitio")
    else:
        warns.append("site/data aún no existe (corre scripts/build_site_data.py)")

    # 6. estricto
    if a.strict:
        if manifest["mode"] == "fixtures":
            err("modo 'fixtures': el lago es de PRUEBA, no se puede entregar")
        elif manifest["mode"] == "snapshot":
            warns.append("modo 'snapshot': datos de la copia local del %s (el portal no respondió); la ficha de cada fuente lo dice"
                         % manifest.get("snapshot", {}).get("descargada_el", "?"))
    for w in warns + warns_out:
        print("AVISO:", w)
    for e in errors:
        print("FALLA:", e)
    print("VERIFICACIÓN", "FALLÓ" if errors else "OK")
    sys.exit(1 if errors else 0)


warns_out = []


def check_rows(fname, rows, err):
    if not rows:
        err(f"{fname}: sin filas")
        return
    for r in rows[:5000]:
        for k, v in r.items():
            if v.strip().upper() == "ND":
                err(f"{fname}: quedó un 'ND' sin limpiar en {k}")
                return
    if fname.startswith("F01"):
        bad = [r for r in rows if int(r["homicidios"]) < 0 or not 1993 <= int(r["anio"]) <= 2018]
        if bad:
            err(f"{fname}: valores fuera de rango (ej. {bad[0]})")
        if any(r["comuna"].lower().startswith("total") for r in rows):
            err(f"{fname}: quedó una fila de totales (se contaría dos veces)")
        # alerta (no corrige): un salto de más de 5 veces entre años seguidos en el total de la ciudad
        tot = {}
        for r in rows:
            tot[int(r["anio"])] = tot.get(int(r["anio"]), 0) + int(r["homicidios"])
        ys = sorted(tot)
        for a_, b_ in zip(ys, ys[1:]):
            if tot[a_] and tot[b_] > 5 * tot[a_]:
                warns_out.append(f"{fname}: el total pasa de {tot[a_]} ({a_}) a {tot[b_]} ({b_}); revisar antes de graficar")
    if fname.startswith("F03"):
        fechas = []
        for r in rows:
            if not fechas or fechas[-1] != r["fecha"]:
                fechas.append(r["fecha"])
        if fechas != sorted(fechas):
            warns_out.append(f"{fname}: las fechas no están en orden cronológico (¿día y mes invertidos?); revisar")
        bad = [r for r in rows if not 0 < float(r["ica"]) <= 500]
        if bad:
            err(f"{fname}: ICA en 0 o fuera de 500 (los ceros son faltantes; ej. {bad[0]})")
    if fname.startswith("F09"):
        tot = [int(r["poblacion_total"]) for r in rows if r["poblacion_total"]]
        if any(t < 10000 for t in tot):
            err(f"{fname}: población < 10 000; probable error con el punto de miles")
        if tot != sorted(tot):
            err(f"{fname}: la población no crece censo a censo (revisa la conversión de miles)")


if __name__ == "__main__":
    main()
