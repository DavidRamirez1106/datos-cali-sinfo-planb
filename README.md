# Cali en datos — Taller de datos, parte 2

**Grupo:** Tomas Gañan Rivera, David Ramírez, Camilo Melo · **Ciudad:** Santiago de Cali
**Sistema publicado:** [pegar el enlace] · **Repositorio:** https://github.com/triveraEafit/datos-cali-sinfo

Sistema web que convierte el lago de la primera entrega en cuatro vistas: homicidios por comuna (con mapa), calidad del aire por estación, educación para el trabajo y población histórica. Cada cifra tiene a un clic su fuente (ID, licencia, vigencia, fecha de prueba).

---

## 0. Estado real de este repositorio (leer primero)

**Actualización (4 de noviembre de 2026): el portal de la Alcaldía está fuera de línea.** Desde el 21 de octubre de 2026 `datos.cali.gov.co` muestra un «Comunicado oficial» de la Alcaldía: servicios web suspendidos temporalmente por medidas de seguridad (captura en `evidencia/`). Nuestra primera ingesta real, el 3 de noviembre, dio HTTP 403 en las cuatro fuentes. Qué hicimos y qué no:

- **Plan B, `copia_local/`:** los archivos que el grupo descargó a mano y limpió el **2026-10-06** (F01, F03, F04, F09). `scripts/snapshot.py` los convierte al formato de `lago/clean` solo para las fuentes que la ingesta no pudo traer; cuando el portal vuelva, la ingesta real manda. La ficha de cada fuente dice «copia descargada el 2026-10-06» y no finge una descarga nueva. Las licencias son las que el grupo copió en el Excel de la primera entrega.
- **ICA en 0 → faltante** (F03). **F01 solo 1993–2018:** en 2019–2021 la fuente no es creíble (el total pasa de 1.170 a 15.647 y las cifras de las comunas 2 a 22 son múltiplos exactos del número de comuna); la nota está escrita dentro del gráfico. Al pasar de sexo a total por comuna y año, se descartan 36 de 624 comuna-año donde falta alguno de los dos sexos (no se supone 0).
- **Sigue sin hacerse:** la **población por comuna** (para tasas) y los **polígonos de comunas** (mapa). Ninguna se pudo descargar; la vista territorial es hoy la tabla de ranking. La pregunta de tasas queda pendiente.
- **No se hizo en código:** la limpieza de F02 (tránsito) y la corrección de las fechas invertidas de F03 se hicieron a mano en la primera entrega y están descritas en `Taller_de_Datos_Cali_Entrega1/lago/README.md`; solo se ejecuta aquí el resultado ya limpio. F02 no se muestra en el sitio.
- La conversión de la copia local y el corte de F01 se probaron con 14 pruebas automáticas y con una corrida local con los datos reales de la copia; **no se ha probado la publicación con la copia en GitHub Actions**.


Lo que se probó y lo que no, sin adornos:

| Probado | Cómo |
|---|---|
| Los scripts de ingesta, limpieza y verificación | 10 pruebas automáticas (`python -m unittest discover -s tests`) con **datos sintéticos** que imitan la forma de las respuestas del portal |
| El sitio abre a 390 px de ancho, sin barra horizontal y sin errores de JavaScript | Navegador Chromium simulando un teléfono, con datos sintéticos |
| Mapa, selector de año, tabla, detalle de comuna y ficha de fuente | Probados con clics en ese mismo navegador |

| **No** probado | Qué falta |
|---|---|
| **Ninguna descarga real.** El entorno donde se escribió el código no podía llegar a datos.cali.gov.co | Correr `python scripts/run_all.py` (o la acción de GitHub). Esa primera corrida real es la prueba de verdad y fija las fechas de prueba |
| **La capa de comunas (F11)**: las dos URL del portal nacional son una suposición | Si ninguna responde, el script lo dice y se fija la correcta con `COMUNAS_GEOJSON_URL`. Mientras tanto el mapa se reemplaza por la tabla |
| La conversión del punto de miles de la población (F09) | `verify.py` la delata si está mal (exige población creciente y ≥ 10 000) |
| Un teléfono físico, el modo oscuro, la publicación en GitHub Pages/Vercel | Revisar a mano |
| Los colores del mapa | Se usó la rampa azul de la paleta de referencia; no se corrió ningún validador de color |

Hasta que corra la ingesta real, el sitio muestra «Todavía no hay datos». Si se construye con los datos sintéticos, muestra un aviso amarillo **DATOS DE PRUEBA**, y `verify.py --strict` se niega a aprobarlo.

## 1. Cómo correrlo y publicarlo

```bash
python scripts/run_all.py                      # pruebas → ingesta real → datos del sitio → verificación estricta
python scripts/make_excel.py                   # regenera entrega/Diccionario_de_datos_TallerDatos_Cali.xlsx con lo que quedó en el lago
python -m http.server -d site 8000             # ver en http://localhost:8000
```

La ingesta, la verificación y las pruebas usan solo la biblioteca estándar de Python 3.10+. Solo `make_excel.py` necesita `pip install openpyxl`. No hay llaves ni cuentas.

- **GitHub Pages (recomendado):** subir el repositorio, en *Settings → Pages* poner *Source = GitHub Actions*. `.github/workflows/pipeline.yml` corre pruebas, ingesta y verificación estricta, y publica. Si la ingesta o la verificación fallan (por ejemplo, porque el portal de la Alcaldía está fuera de línea desde el 21 de octubre de 2026), el sitio igual se publica con un aviso visible de las fuentes que no respondieron, y el paso queda marcado como fallido en la pestaña *Actions*. Las pruebas con datos sintéticos sí deben pasar. También corre el día 1 de cada mes, y cuando el portal vuelva se llenará solo.
- **Vercel/Netlify (estático):** correr `run_all.py` en local, subir `lago/` y `site/data/`, y publicar la carpeta `site/`.
- **Nombres del grupo:** editar `site/group.json` (aparecen en la cabecera y el pie del sitio).
- **Compuerta:** no se puso. Si el profesor la pide, la clave se le entrega aparte y nunca va en el repositorio.

## 2. Lo mínimo que pide la entrega

| Requisito | Dónde / estado |
|---|---|
| ≥ 3 fuentes integradas con su script de ingesta | F01, F03, F04, F09 (+ F11 para el mapa) en `scripts/ingest.py`. **Pendiente de la primera corrida real** |
| Abre bien desde un teléfono | Simulado a 390 px; falta un aparato real |
| Cada cifra, a un clic su fuente (ID, vigencia, fecha de prueba) | Botón «F0x · fuente» en cada tarjeta y en el detalle de comuna; `verify.py` falla si un archivo del sitio no trae su ficha |
| Una vista del territorio | Mapa por comuna (F01 + F11), con tabla equivalente |
| Responde ≥ 2 preguntas y dice cuáles quedan pendientes | 3 respondidas y 1 pendiente (tasas por habitante), listadas arriba del sitio |
| Ningún dato de personas | F05 y F06 no se descargan; `verify.py` bloquea columnas con aspecto de datos personales y que F05/F06 aparezcan en el sitio |
| Datos simulados o aproximados (PROXY) se ven como tales | No hay ninguno. Los datos de prueba llevan un aviso en la parte de arriba |
| Sin llave paga ni tarjeta | MapLibre va dentro del repositorio; el mapa no usa teselas externas; hosting gratuito |

## 3. Las cuatro decisiones

**Qué mostrar.** Tres preguntas de la primera entrega (homicidios por comuna y su cambio 1993–2021; aire por estación; oferta de educación para el trabajo) más la población histórica como contexto. Lo que no se pudo responder se dice en el sitio: tasas por habitante (no hay población actual por comuna en datos abiertos) y movilidad.

**Si los datos se pueden usar.** Cada corrida copia la licencia tal como la declara la API del portal (`lago/manifest.json`); en la prueba manual del 2026-09-28 fueron *Creative Commons Attribution* (F01, F09) y *Creative Commons Attribution Share-Alike* (F03, F04), sin versión declarada. La atribución va en la ficha de cada fuente. La licencia *Share-Alike* pide compartir lo derivado bajo la misma licencia: confirmar con el profesor cómo debe declararse en el repositorio. Si una fuente no declara licencia, el Excel dice «no declara»; no se supone una.

**Cómo se protegieron.** (1) Las dos fuentes sobre personas en riesgo (F05 trata de personas, F06 líderes amenazados) no entran, ni siquiera agregadas: con pocos casos por comuna, un conteo puede señalar a alguien. (2) `verify.py` revisa que ninguna columna parezca de personas y que F05/F06 no aparezcan en el sitio. (3) Lo que sí se publica son conteos por comuna y año, índices por estación e instituciones (personas jurídicas). Riesgo abierto: un nombre de institución puede ser el de una persona natural; revisarlo a mano tras la primera corrida. (4) El sitio no guarda ni envía nada de quien lo visita.

**Con qué herramienta.** Sitio estático con MapLibre GL JS para el mapa y gráficos SVG propios. Ver la bitácora siguiente.

## 4. Bitácora de exploración

Mismos datos (los sintéticos del repositorio, `tests/make_fixtures.py`) y mismos criterios para las dos herramientas probadas. Probadas en un entorno sin acceso al portal; no se probó con datos reales.

| Criterio | MapLibre GL JS 4.7.1 + SVG propio (**quedó**) | Streamlit 1.66.1 + Plotly 7.1.0 (descartada) |
|---|---|---|
| Qué pidió para empezar | `npm install` solo para copiar dos archivos a `site/vendor/`; sin cuenta ni llave | `pip install streamlit plotly pandas` (~1 min; Streamlit solo pesa 35 MB instalado); sin cuenta para correrlo |
| Licencia | BSD-3-Clause | Apache-2.0 (Streamlit), MIT (Plotly) |
| Dónde quedan los datos al publicar | En archivos JSON del propio sitio (GitHub Pages/Vercel) | En el servidor de Python que corre la app (no se probó ningún despliegue; publicarla exige un servidor activo, no una página estática) |
| Qué resolvió | Mapa por comuna que abre en teléfono y no necesita servidor ni teselas; todo el sitio pesa ~0,9 MB | Selector + mapa + ficha de fuente en 9 líneas de código; el servidor arrancó y respondió |
| Qué no resolvió | Todo lo demás hubo que escribirlo: leyendas, tooltips, tabla, ~330 líneas de JavaScript. Necesita WebGL (si no hay, el sitio muestra la tabla) | En la prueba, dibujó la barra de color pero **no los polígonos**: el entorno bloqueó `cdn.plot.ly`, de donde Plotly baja archivos de base. No sé si en una red normal dibuja |
| Por qué quedó / no quedó | Se publica gratis como página estática, sin dependencias externas en ejecución | Lo más cómodo de programar, pero exige servidor y, en la prueba, dependía de un sitio externo |

No se probaron Datawrapper, Observable, kepler.gl, Power BI ni Looker Studio.

## 5. Catálogo de fuentes

**Entran al lago** (detalle de campos en `dictionary.json` y en la hoja 2 del Excel):

| ID | Fuente | Publica |
|---|---|---|
| F01 | Homicidios por año y comuna 1993–2021 | Secretaría de Seguridad y Justicia |
| F03 | Índice de Calidad del Aire por estación | DAGMA |
| F04 | Programas de Educación para el Trabajo y Desarrollo Humano | Secretaría de Educación |
| F09 | Población total censada por área | Planeación Municipal (cifras DANE) |
| F11 | Polígonos de las comunas | Planeación Municipal (portal nacional) |

**No entraron:**

| ID | Fuente | Razón |
|---|---|---|
| F02 | Lesionados en accidentes de tránsito 2016–2025 | La descarga directa dio 403 a las herramientas automáticas y la ficha no confirma desglose por comuna; candidata para una versión siguiente |
| F05 | Posibles víctimas de trata de personas | Personas en riesgo. No se descarga ni se publica |
| F06 | Líderes y lideresas sociales amenazados | Personas en riesgo. No se descarga ni se publica |
| F07 | POT – suelo de expansión urbana | No responde a ninguna pregunta del sistema; F11 cubre lo territorial |
| F08 | Vistas de Wikipedia sobre «Cali» | No se pudo probar y no responde a las preguntas del sistema |
| F10 | GTFS del MIO (Metro Cali S.A.) | No existe (la inventó la IA): no hay feed oficial descargable; solo noticias y un repositorio no oficial |

## 6. Bitácora de IA

Las 12 entradas completas están en la hoja «3. Bitácora IA» del Excel (generadas desde `ai_log.json`). Resumen de los errores, que valen tanto como los aciertos:

- **Inventado:** un feed GTFS del MIO que «debía existir» (F10).
- **Incorrecto:** una URL de Wikipedia copiada de Medellín a Cali que nunca respondió (F08).
- **Parcial, con lección:** los scripts pasaron sus pruebas solo con datos sintéticos; las URL de las comunas son una suposición; el punto de miles de la población es una inferencia; la primera versión del sitio tenía una gráfica ilegible en teléfono y un mapa que parecía cortado por un defecto de la captura, no del sitio.
- **Acierto pleno:** encontrar el conjunto de homicidios por comuna y comprobarlo con la API (F01).

## 7. Dos reflexiones

> **BORRADOR para que el grupo lo adopte o lo cambie.** El enunciado exacto de las dos reflexiones está en la guía del taller y no se pudo leer; pegarlo aquí y ajustar la respuesta.

**De datos.** Un conjunto abierto no es neutral ni completo. Mostrar homicidios como conteos hace que las comunas más pobladas parezcan peores solo por su tamaño, y no hay denominador abierto para corregirlo. Nuestra posición: mostrar el conteo con el aviso a la vista y dejar la pregunta de las tasas como pendiente, antes que inventar una población por comuna.

**De seguridad.** «Público» no significa «inofensivo»: dos datos inocentes cruzados pueden señalar a una persona. Por eso F05 y F06 no entran ni agregadas, y una verificación automática vigila que no se cuelen. Esa verificación solo atrapa lo que sabe buscar; el criterio humano sigue siendo la última barrera.

## 8. En clase (guion de tres respuestas)

- **¿Qué herramienta descartaron que casi eligen?** Streamlit: lo hizo en 9 líneas frente a unas 330. Se descartó porque exige un servidor y, en la prueba, dependía de un sitio externo para dibujar el mapa.
- **¿Qué decidieron no mostrar?** Los datos de personas en riesgo (F05, F06), y tasas por habitante.
- **¿Qué tendría que cambiar para que la respuesta fuera otra?** Si hubiera población abierta por comuna, se mostrarían tasas. Si el grupo tuviera servidor propio y poca experiencia con JavaScript, Streamlit ganaría. Si las fuentes de personas en riesgo se publicaran solo con un umbral mínimo de casos, se podría reconsiderar.

## 9. Estructura

```
sources.json            catálogo de fuentes (qué entra y por qué no entran las demás)
dictionary.json         diccionario: una entrada por columna real de lago/clean
ai_log.json             bitácora de IA (alimenta el Excel)
scripts/ingest.py       descarga, limpia y escribe lago/ + manifest.json (fecha real de prueba)
scripts/verify.py       verificación (--strict para entregar)
scripts/build_site_data.py   lago → site/data
scripts/make_excel.py   Excel del diccionario desde lo que hay en el lago
scripts/run_all.py      todo lo anterior en orden
tests/                  pruebas con datos sintéticos
lago/                   raw/ (crudo), clean/ (tablas limpias), manifest.json
site/                   el sistema (HTML, CSS, JS, MapLibre en vendor/)
entrega/                Excel generado y plantillas originales del profesor
.github/workflows/      publicación en GitHub Pages
```
