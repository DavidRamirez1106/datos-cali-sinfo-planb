#!/usr/bin/env python3
"""Genera respuestas SINTÉTICAS con la misma forma que las del portal.

NO son datos de Cali. Sirven solo para probar los scripts sin red.
Cualquier sitio construido con ellos muestra el aviso «DATOS DE PRUEBA».
"""
import json
import os
import random
import sys

OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "fixtures")
os.makedirs(OUT, exist_ok=True)
rnd = random.Random(7)


def dump(name, obj):
    with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False)


cfg = json.load(open(os.path.join(os.path.dirname(__file__), "..", "sources.json"), encoding="utf-8"))
for s in cfg["sources"]:
    dump(s["package"] + ".package.json", {"success": True, "result": {
        "license_title": "SINTETICO (no es una licencia real)", "metadata_modified": "2000-01-01T00:00:00",
        "organization": {"title": "FIXTURE"}}})

# F01
recs = []
for c in range(1, 23):
    r = {"_id": c, "Comuna": f"Comuna {c}"}
    for y in range(1993, 2022):
        r[f"F{y}"] = rnd.randint(0, 9)
        r[f"M{y}"] = rnd.randint(0, 60)
        r[f"Total {y}"] = "ND" if (c == 5 and y == 1993) else r[f"F{y}"] + r[f"M{y}"]
    recs.append(r)
recs.append({"_id": 23, "Comuna": "Zona rural", **{f"Total {y}": rnd.randint(0, 5) for y in range(1993, 2022)}})
recs.append({"_id": 24, "Comuna": "Total", **{f"Total {y}": 999 for y in range(1993, 2022)}})
dump("17d369c4-6ba0-4b77-b7e7-d034f70d6f97.datastore.0.json",
     {"success": True, "result": {"total": len(recs), "records": recs}})

# F03
stations = ["ERA - Obrero", "La Flora", "Pance", "Univalle", "Base Aerea", "Compartir", "La Ermita",
            "Cañaveralejo", "Transitoria"]
recs, i = [], 0
for y in range(2010, 2021):
    for m in range(1, 13):
        i += 1
        r = {"_id": i, "id": i, "Fecha": f"{y}-{m:02d}-01T00:00:00"}
        for s in stations:
            r[s] = "ND" if (y < 2013 or rnd.random() < 0.2) else rnd.randint(20, 120)
        recs.append(r)
dump("b247bee0-596c-4515-bdd4-2ebdf6542caf.datastore.0.json",
     {"success": True, "result": {"total": len(recs), "records": recs}})

# F04 (1200 registros para probar la paginación de 1000)
jor = ["diurna", "nocturna", "fin de semana"]
recs = []
for i in range(1, 1201):
    inst = rnd.randint(1, 80)
    recs.append({"_id": i, "codigo_institucion": 1000 + inst, "nombre_institucion": f"  Instituto   Sintético {inst} ",
                 "codigo_programa": 5000 + i, "nombre_programa": f"Programa {i}", "tipo_certificado": "Certificado X",
                 "jornada_1": rnd.choice(jor), "jornada_2": rnd.choice(jor + [None]), "jornada_3": None})
for off in (0, 1000):
    dump(f"d3d5d6ef-170e-408f-b3eb-9c6fa1570254.datastore.{off}.json",
         {"success": True, "result": {"total": 1200, "records": recs[off:off + 1000]}})

# F09 (el datastore entrega las poblaciones como 637.929 numérico)
recs = [
    {"_id": 1, "Año": 1912, "Población total": 27.747, "Población cabecera": "ND", "% Cabecera": "ND", "Población resto": "ND"},
    {"_id": 2, "Año": 1918, "Población total": 45.525, "Población cabecera": "ND", "% Cabecera": "ND", "Población resto": "ND"},
    {"_id": 3, "Año": 1938, "Población total": 101.883, "Población cabecera": "88.366", "% Cabecera": "86.7%", "Población resto": "13.517"},
    {"_id": 4, "Año": 1951, "Población total": 284.186, "Población cabecera": "241.357", "% Cabecera": "84.9%", "Población resto": "42.829"},
    {"_id": 5, "Año": 1964, "Población total": 637.929, "Población cabecera": "618.215", "% Cabecera": "96.9%", "Población resto": "19.714"},
]
dump("0fcd7b53-11a5-437b-8fbb-ce5d0d4324ea.datastore.0.json",
     {"success": True, "result": {"total": len(recs), "records": recs}})

# F11: 22 cuadrados en una rejilla 6x4 cerca de Cali (SINTÉTICO, no son los límites reales)
feats = []
for n in range(22):
    cx, cy = -76.58 + (n % 6) * 0.025, 3.55 - (n // 6) * 0.03
    ring = [[cx, cy], [cx + 0.024, cy], [cx + 0.024, cy - 0.029], [cx, cy - 0.029], [cx, cy]]
    feats.append({"type": "Feature", "properties": {"comuna": f"Comuna {n + 1}", "area": 1.0},
                  "geometry": {"type": "Polygon", "coordinates": [ring]}})
dump("comunas.geojson", {"type": "FeatureCollection", "features": feats})
print("fixtures sintéticos en", OUT)
