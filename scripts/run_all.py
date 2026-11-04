#!/usr/bin/env python3
"""Un solo comando: descarga el lago, arma los datos del sitio y verifica.

    python scripts/run_all.py

Necesita internet (portal datos.cali.gov.co). No usa llaves ni cuentas.
Luego ver el sitio en local:  python -m http.server -d site 8000
"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def step(title, *args, must=True):
    print(f"\n== {title}")
    r = subprocess.run([sys.executable, *args], cwd=ROOT)
    if r.returncode and must:
        print(f"\nSe detuvo en: {title}")
        sys.exit(r.returncode)
    return r.returncode


step("1/4 Pruebas del pipeline (datos sintéticos, sin red)", "-m", "unittest", "discover", "-s", "tests")
ing = step("2/4 Ingesta real de las fuentes", "scripts/ingest.py", must=False)
if ing:
    print("\nHubo fuentes que no respondieron (¿portal fuera de línea?). Se usa la copia local de copia_local/ para esas.")
    step("2b/4 Copia local para las fuentes que fallaron", "scripts/snapshot.py")
step("3/4 Datos del sitio", "scripts/build_site_data.py")
step("4/4 Verificación estricta (el lago no puede ser de prueba, mínimo 3 fuentes)", "scripts/verify.py", "--strict")
print("\nListo. Abre el sitio con:  python -m http.server -d site 8000   y entra a http://localhost:8000")
