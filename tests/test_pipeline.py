"""Pruebas del pipeline con datos SINTÉTICOS (sin red). Ejecutar: python -m unittest discover -s tests"""
import csv
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import ingest  # noqa: E402



def sh(*args):
    return subprocess.run([sys.executable, *args], capture_output=True, text=True, cwd=ROOT)


class PipelineTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        fx = os.path.join(cls.tmp, "fx")
        assert sh("tests/make_fixtures.py", fx).returncode == 0
        cls.lago = os.path.join(cls.tmp, "lago")
        cls.manifest = ingest.run(ingest.FixtureFetcher(fx), cls.lago)
        open(os.path.join(cls.lago, "clean", ".gitkeep"), "w").close()  # el repositorio lo trae; verify no debe fallar por eso
        cls.site = os.path.join(cls.tmp, "site")
        r = sh("scripts/build_site_data.py", "--lago", cls.lago, "--out", cls.site)
        assert r.returncode == 0, r.stderr

    def test_all_sources_ok_with_test_date(self):
        for sid, s in self.manifest["sources"].items():
            self.assertEqual(s["status"], "ok", sid)
            self.assertRegex(s["tested_at"], r"^\d{4}-\d{2}-\d{2}$")

    def test_pagination(self):
        self.assertEqual(self.manifest["sources"]["F04"]["rows_raw"], 1200)

    def test_pop_value(self):
        self.assertEqual(ingest.pop_value(637.929), 637929)
        self.assertEqual(ingest.pop_value("637.929"), 637929)
        self.assertEqual(ingest.pop_value(241.35), 241350)  # cero final perdido por el float
        self.assertEqual(ingest.pop_value("ND"), None)
        self.assertEqual(ingest.pop_value(1200000), 1200000)

    def test_f01_drops_total_row_and_nd(self):
        rows = ingest.clean_f01([
            {"Comuna": "Comuna 5", "Total 1993": "ND", "Total 1994": 3},
            {"Comuna": "Total", "Total 1994": 999},
            {"Comuna": "Zona rural", "Total 1994": 1}])
        self.assertEqual([(r["comuna"], r["anio"], r["homicidios"]) for r in rows],
                         [("Comuna 5", 1994, 3), ("Zona rural", 1994, 1)])

    def test_f03_drops_nd(self):
        rows = ingest.clean_f03([{"_id": 1, "id": 1, "Fecha": "2012-01-01T00:00:00", "Pance": "ND", "Univalle": 55}])
        self.assertEqual(rows, [{"fecha": "2012-01-01", "estacion": "Univalle", "ica": 55.0}])

    def test_f03_drops_zero_as_missing(self):
        rows = ingest.clean_f03([{"_id": 1, "id": 1, "Fecha": "2012-01-01T00:00:00", "Pance": 0, "Univalle": 55}])
        self.assertEqual(rows, [{"fecha": "2012-01-01", "estacion": "Univalle", "ica": 55.0}])

    def test_f01_cuts_unreliable_years(self):
        rows = ingest.clean_f01([{"Comuna": "Comuna 2", "Total 2018": 10, "Total 2019": 300}])
        self.assertEqual([(r["anio"], r["homicidios"]) for r in rows], [(2018, 10)])

    def test_snapshot_converts_and_marks_mode(self):
        import snapshot
        copia = os.path.join(self.tmp, "copia")
        os.makedirs(copia)
        open(os.path.join(copia, "f01.csv"), "w", encoding="utf-8").write(
            "comuna,anio,sexo,homicidios,dato_dudoso\n"
            "1,2018,F,2,0\n1,2018,M,8,0\n1,2019,F,9,1\n1,2019,M,9,1\n"
            "2,2018,F,,0\n2,2018,M,5,0\nRural,2018,F,1,0\nRural,2018,M,1,0\n")
        open(os.path.join(copia, "f03.csv"), "w", encoding="utf-8").write(
            "fecha,Pance,Univalle\n2012-01-01,0,55\n2012-01-02,40,\n")
        open(os.path.join(copia, "f04.csv"), "w", encoding="utf-8").write(
            "codigo_institucion,nombre_institucion,codigo_programa,nombre_programa,tipo_certificado,jornada_1,jornada_2,jornada_3\n"
            "1,inst,9,prog,cert,diurna,diurna,\n")
        open(os.path.join(copia, "f09.csv"), "w", encoding="utf-8").write(
            "anio_censo,mes,poblacion_total,tasa_crecimiento_pct,poblacion_cabecera,poblacion_cabecera_pct,poblacion_resto,poblacion_resto_pct\n"
            "1993,6,1798475,2.95,1760892,97.9,37583,2.1\n")
        json.dump({"descargada_el": "2026-10-06", "motivo": "x", "fuentes": {
            "F01": {"archivo": "f01.csv", "licencia": "L1"}, "F03": {"archivo": "f03.csv", "licencia": "L3"},
            "F04": {"archivo": "f04.csv", "licencia": "L4"}, "F09": {"archivo": "f09.csv", "licencia": "L9"}}},
            open(os.path.join(copia, "COPIA.json"), "w", encoding="utf-8"))
        lago = os.path.join(self.tmp, "lago_snap")
        used = snapshot.run(lago, copia)
        self.assertEqual(used, ["F01", "F03", "F04", "F09"])
        m = json.load(open(os.path.join(lago, "manifest.json"), encoding="utf-8"))
        self.assertEqual(m["mode"], "snapshot")
        self.assertEqual(m["sources"]["F01"]["tested_at"], "2026-10-06")
        self.assertEqual(m["sources"]["F01"]["license_title"], "L1")
        f01 = list(csv.DictReader(open(os.path.join(lago, "clean", "F01_homicidios_comuna.csv"), encoding="utf-8")))
        # 2019 (dudoso) fuera; comuna 2 con un sexo vacío fuera; comuna 1 suma 10; Rural sin id
        self.assertEqual([(r["comuna_id"], r["anio"], r["homicidios"]) for r in f01], [("1", "2018", "10"), ("", "2018", "2")])
        f03 = list(csv.DictReader(open(os.path.join(lago, "clean", "F03_ica_estaciones.csv"), encoding="utf-8")))
        self.assertEqual([(r["estacion"], r["ica"]) for r in f03], [("Univalle", "55.0"), ("Pance", "40.0")])
        f04 = list(csv.DictReader(open(os.path.join(lago, "clean", "F04_programas_etdh.csv"), encoding="utf-8")))
        self.assertEqual(f04[0]["jornadas"], "diurna")

    def test_snapshot_does_not_override_live_sources(self):
        import snapshot
        lago = os.path.join(self.tmp, "lago_live")
        os.makedirs(lago)
        json.dump({"mode": "live", "sources": {"F01": {"status": "ok"}}}, open(os.path.join(lago, "manifest.json"), "w"))
        copia = os.path.join(self.tmp, "copia")
        used = snapshot.run(lago, copia)
        self.assertNotIn("F01", used)

    def test_failed_source_has_no_test_date(self):
        class Broken(ingest.FixtureFetcher):
            def get(self, url, retries=1):
                raise ingest.FetchError("HTTP 403")
        m = ingest.run(Broken(self.tmp), os.path.join(self.tmp, "broken"))
        for s in m["sources"].values():
            self.assertEqual(s["status"], "error")
            self.assertNotIn("tested_at", s)
            self.assertEqual(s["license_title"], "no declara")  # no se supone licencia

    def test_comunas_projected_crs_rejected(self):
        gj = {"type": "FeatureCollection", "features": [
            {"type": "Feature", "properties": {"comuna": f"Comuna {i}"},
             "geometry": {"type": "Polygon", "coordinates": [[[1060303.0, 860244.0], [1.0, 2.0], [3.0, 4.0], [1060303.0, 860244.0]]]}}
            for i in range(1, 23)]}
        with self.assertRaises(ingest.FetchError):
            ingest.clean_comunas(gj)

    def test_verify_ok_in_test_mode_but_strict_fails(self):
        base = ["scripts/verify.py", "--lago", self.lago, "--site-data", self.site]
        self.assertEqual(sh(*base).returncode, 0, sh(*base).stdout)
        strict = sh(*base, "--strict")
        self.assertEqual(strict.returncode, 1)
        self.assertIn("PRUEBA", strict.stdout)

    def test_verify_catches_personal_column(self):
        path = os.path.join(self.lago, "clean", "F01_homicidios_comuna.csv")
        orig = open(path, encoding="utf-8").read()
        try:
            open(path, "w", encoding="utf-8").write(orig.replace("comuna_id", "nombre_persona", 1))
            r = sh("scripts/verify.py", "--lago", self.lago, "--site-data", self.site)
            self.assertEqual(r.returncode, 1)
            self.assertIn("personas", r.stdout)
        finally:
            open(path, "w", encoding="utf-8").write(orig)

    def test_site_data_has_provenance(self):
        fichas = json.load(open(os.path.join(self.site, "fuentes.json"), encoding="utf-8"))
        for sid in ("F01", "F03", "F04", "F09", "F11"):
            for k in ("license", "tested_at", "vigencia"):
                self.assertTrue(fichas[sid][k], (sid, k))
        self.assertNotIn("F05", fichas)


if __name__ == "__main__":
    unittest.main()
