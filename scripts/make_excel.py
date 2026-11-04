#!/usr/bin/env python3
"""Genera el Excel del diccionario a partir de lo que de verdad está en el lago.

    python scripts/make_excel.py

Fuentes de verdad:
  lago/manifest.json     licencia, estado y fecha de prueba (si la ingesta real ya corrió)
  dictionary.json        campos de lago/clean
  ai_log.json            bitácora de IA
  site/group.json        nombres del grupo
Si todavía no hay manifiesto real, usa la evidencia de la prueba manual del 2026-09-28
(respuestas reales de la API del portal) y lo dice en «Observaciones».
Una fuente solo aparece si está integrada: las demás viven en el README.
"""
import json
import os
import sys

import openpyxl

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE = os.path.join(ROOT, "entrega", "plantilla_diccionario_profesor.xlsx")
OUT = os.path.join(ROOT, "entrega", "Diccionario_de_datos_TallerDatos_Cali.xlsx")

# Evidencia de la prueba manual (respuestas reales de la API, 2026-09-28)
FALLBACK = {
    "F01": ("Creative Commons Attribution", "2026-09-28"),
    "F03": ("Creative Commons Attribution Share-Alike", "2026-09-28"),
    "F04": ("Creative Commons Attribution Share-Alike", "2026-09-28"),
    "F09": ("Creative Commons Attribution", "2026-09-28"),
}
META = {  # columnas de la hoja Fuentes que no dependen de la corrida
    "F01": dict(url="https://datos.cali.gov.co/api/3/action/datastore_search?resource_id=17d369c4-6ba0-4b77-b7e7-d034f70d6f97",
                fmt="CSV", how="API sin llave", cov="Municipio de Santiago de Cali, por comuna", freq="No se sabe",
                found="Búsqueda guiada por IA en datos.cali.gov.co (tema homicidios)",
                obs="No declara periodicidad; el último corte es 2021. Se descarta la fila de totales y los «ND»."),
    "F03": dict(url="https://datos.cali.gov.co/api/3/action/datastore_search?resource_id=b247bee0-596c-4515-bdd4-2ebdf6542caf",
                fmt="CSV", how="API sin llave", cov="Municipio de Santiago de Cali, 9 estaciones de monitoreo", freq="Mensual",
                found="Búsqueda guiada por IA en datos.cali.gov.co (tema calidad del aire)",
                obs="Los meses sin medición vienen como «ND»; no se rellenan, quedan como hueco en la gráfica."),
    "F04": dict(url="https://datos.cali.gov.co/api/3/action/datastore_search?resource_id=d3d5d6ef-170e-408f-b3eb-9c6fa1570254",
                fmt="CSV", how="API sin llave", cov="Municipio de Santiago de Cali", freq="Anual",
                found="Búsqueda guiada por IA en datos.cali.gov.co (tema educación)",
                obs="Trae instituciones (personas jurídicas), no personas. Revisar a mano que ningún nombre de institución sea el de una persona natural."),
    "F09": dict(url="https://datos.cali.gov.co/api/3/action/datastore_search?resource_id=0fcd7b53-11a5-437b-8fbb-ce5d0d4324ea",
                fmt="CSV", how="API sin llave", cov="Municipio de Santiago de Cali (cabecera y resto)", freq="Única vez",
                found="Búsqueda guiada por IA en datos.cali.gov.co (tema población / censo)",
                obs="Termina en un censo antiguo; no sirve para tasas actuales. El punto de miles se convierte (ver diccionario)."),
    "F11": dict(url="(la que haya respondido; ver lago/manifest.json, campo url_used)", fmt="GeoJSON", how="Descarga directa",
                cov="Municipio de Santiago de Cali, 22 comunas", freq="No se sabe",
                found="Búsqueda guiada por IA (portal nacional datos.gov.co, «Comunas de Santiago de Cali»)",
                obs="Capa de polígonos para el mapa."),
}


def load(name):
    return json.load(open(os.path.join(ROOT, name), encoding="utf-8"))


def main():
    manifest_path = os.path.join(ROOT, "lago", "manifest.json")
    manifest = json.load(open(manifest_path, encoding="utf-8")) if os.path.exists(manifest_path) else None
    live = bool(manifest and manifest.get("mode") == "live")
    cfg, dic, ailog = load("sources.json"), load("dictionary.json"), load("ai_log.json")
    names = load(os.path.join("site", "group.json"))["nombres"]

    rows, included = [], []
    for s in cfg["sources"]:
        sid, m = s["id"], META[s["id"]]
        if live:
            e = manifest["sources"].get(sid, {})
            if e.get("status") != "ok":
                continue
            lic, tested, note = e["license_title"], e["tested_at"], "Fecha y licencia tomadas de lago/manifest.json (corrida real)."
            url = e.get("url_used") if sid == "F11" else m["url"]
        else:
            if sid not in FALLBACK:
                continue  # F11 no se puede afirmar sin una corrida real
            lic, tested = FALLBACK[sid]
            url = m["url"]
            note = "Fecha y licencia de la prueba manual del 2026-09-28 (respuesta real de la API). Volver a correr scripts/make_excel.py después de la ingesta real."
        included.append(sid)
        rows.append([sid, s["name"], s["entity"], "Entidad pública", url, m["fmt"], m["how"], lic, "No", m["cov"],
                     s["periodo"], m["freq"], tested, "Integrada al lago", m["found"], (m["obs"] + " " + note).strip()])

    wb = openpyxl.load_workbook(TEMPLATE)
    ws = wb["Instrucciones"]
    ws["C5"], ws["C6"] = "Cali", ", ".join(names)
    ws["C7"] = "(escribir aquí el enlace al repositorio)"
    for sheet, ncols in (("1. Fuentes", 16), ("2. Diccionario", 13), ("3. Bitácora IA", 8)):
        for c in range(1, ncols + 1):
            wb[sheet].cell(row=4, column=c).value = None  # se borra la fila de ejemplo (Medellín)
    ws = wb["1. Fuentes"]
    for i, r in enumerate(rows):
        for j, v in enumerate(r):
            ws.cell(row=5 + i, column=1 + j, value=v)
    ws = wb["2. Diccionario"]
    r = 5
    for fname, spec in dic["files"].items():
        if spec["source"] not in included:
            continue
        for f in spec["fields"]:
            vals = [spec["source"], "lago/clean/" + fname, f["name"], f["original"], f["means"], f["type"], f["unit"],
                    f["example"], f["nullable"], f["range"], f["class"], f["transform"], f["question"]]
            for j, v in enumerate(vals):
                ws.cell(row=r, column=1 + j, value=v)
            r += 1
    ws = wb["3. Bitácora IA"]
    for i, e in enumerate(ailog):
        vals = [i + 1, e["tool"], e["task"], e["answer"], e["check"], e["result"], e["ids"], e["learned"]]
        for j, v in enumerate(vals):
            ws.cell(row=5 + i, column=1 + j, value=v)
    wb.save(OUT)
    print(f"Excel escrito: {OUT}\n  fuentes: {included} ({'corrida real' if live else 'evidencia del 2026-09-28'})")


if __name__ == "__main__":
    sys.exit(main())
