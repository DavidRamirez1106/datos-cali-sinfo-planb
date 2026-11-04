"use strict";
/* Cali en datos: lee site/data/*.json (generados por scripts/build_site_data.py).
   Ninguna cifra se dibuja sin su ficha de fuente (fuentes.json). */

const $ = (s, r = document) => r.querySelector(s);
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const nf = new Intl.NumberFormat("es-CO");
const fmt = (v) => (v == null ? "sin dato" : nf.format(v));
const title = (s) => s.replace(/(^|[\s(-])(\p{L})/gu, (m, a, c) => a + c.toUpperCase());
const getJSON = (p) => fetch(p, { cache: "no-cache" }).then((r) => (r.ok ? r.json() : null)).catch(() => null);

let FUENTES = {}, STATUS = null;
const RESIZE = new Map();
let _rt; addEventListener("resize", () => { clearTimeout(_rt); _rt = setTimeout(() => { [...RESIZE.values()].forEach((f) => f()); if (window.__map) { window.__map.resize(); window.__fit && window.__fit(); } }, 200); });

/* ------------------------------------------------------------ tooltip */
const tipEl = $("#tip");
function tip(html, x, y) {
  tipEl.innerHTML = html;
  tipEl.style.display = "block";
  const w = tipEl.offsetWidth, h = tipEl.offsetHeight;
  tipEl.style.left = Math.max(8, Math.min(x + 12, innerWidth - w - 8)) + "px";
  tipEl.style.top = Math.max(8, Math.min(y - h - 12, innerHeight - h - 8)) + "px";
}
const hideTip = () => { tipEl.style.display = "none"; };

/* ------------------------------------------------------------ ficha de fuente */
const METHODS = {
  datastore_search: "API abierta del portal (datastore_search), sin llave",
  csv_directo: "Descarga directa del CSV",
  geojson: "Descarga directa del GeoJSON",
  copia_local: "Copia descargada a mano por el grupo (el portal estaba fuera de línea)",
};
function srcBtn(id) {
  return `<button class="src" data-src="${id}" aria-label="Ver la fuente ${id}">${id} · fuente</button>`;
}
function openSource(id) {
  const f = FUENTES[id];
  if (!f) return;
  $("#srctitle").textContent = `${f.id} · ${f.name}`;
  const rows = [
    ["Publica", f.entity],
    ["Licencia (tal como aparece)", f.license],
    ["Periodo que cubre", f.periodo],
    ["Vigencia (última modificación en el portal)", f.vigencia],
    ["Fecha en que se probó", f.tested_at],
    ["Cómo se obtuvo", METHODS[f.method] || f.method],
    ["Filas en el lago", fmt(f.rows)],
  ].concat(f.nota ? [["Nota", f.nota]] : []);
  const link = f.url ? `<a href="${esc(f.url)}" target="_blank" rel="noopener">${esc(f.url)}</a>` : "";
  $("#srcbody").innerHTML = rows.map(([k, v]) => `<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join("") +
    (link ? `<dt>Enlace</dt><dd>${link}</dd>` : "");
  $("#srcdialog").showModal();
}
document.addEventListener("click", (e) => {
  const b = e.target.closest("button.src");
  if (b) openSource(b.dataset.src);
});
$("#srcclose").addEventListener("click", () => $("#srcdialog").close());
$("#srcdialog").addEventListener("click", (e) => { if (e.target.id === "srcdialog") e.target.close(); });

function setHead(id, ok) { $(`#src-${id}`).innerHTML = ok ? srcBtn(id) : ""; }
function unavailable(el, id) {
  const why = STATUS && STATUS.failed && STATUS.failed[id];
  el.innerHTML = `<div class="empty">Esta vista no está disponible: la fuente ${id} no respondió en la última corrida` +
    (why ? ` (${esc(why.slice(0, 140))})` : "") + `. Se vuelve a intentar en la siguiente ejecución de la ingesta.</div>`;
}

/* ------------------------------------------------------------ gráficos SVG */
function niceMax(v) {
  if (v <= 0) return 1;
  const p = Math.pow(10, Math.floor(Math.log10(v)));
  for (const m of [1, 2, 2.5, 5, 10]) if (m * p >= v) return m * p;
  return 10 * p;
}
/* Línea con huecos donde no hay dato. opts: labels[], series[{values, hi}], unit */
function lineChart(el, opts) {
  const W = Math.max(280, Math.round(el.clientWidth || 640)), L = 40, R = 12, T = 12, B = 28;
  // opts.note: texto que va DENTRO del gráfico (p. ej. por qué la serie se corta); se parte en líneas según el ancho
  const noteLines = [];
  if (opts.note) {
    let line = "";
    for (const wd of opts.note.split(" ")) {
      if ((line + " " + wd).trim().length * 5.6 > W - L - R && line) { noteLines.push(line); line = wd; } else line = (line + " " + wd).trim();
    }
    if (line) noteLines.push(line);
  }
  const H = (W < 480 ? 220 : 240) + (noteLines.length ? noteLines.length * 14 + 10 : 0);
  const PB = H - (noteLines.length ? noteLines.length * 14 + 10 : 0); // alto del área del gráfico sin la nota
  RESIZE.set(el, () => lineChart(el, opts));
  const all = opts.series.flatMap((s) => s.values).filter((v) => v != null);
  if (!all.length) { el.innerHTML = `<div class="empty">Sin datos para esta selección.</div>`; return; }
  const ymax = niceMax(Math.max(...all));
  const n = opts.labels.length;
  const X = (i) => L + (n === 1 ? (W - L - R) / 2 : (i * (W - L - R)) / (n - 1));
  const Y = (v) => T + (1 - v / ymax) * (PB - T - B);
  let g = "";
  for (let k = 0; k <= 4; k++) {
    const v = (ymax * k) / 4, y = Y(v);
    g += `<line class="grid" x1="${L}" x2="${W - R}" y1="${y}" y2="${y}"/><text x="${L - 6}" y="${y + 4}" text-anchor="end">${nf.format(v)}</text>`;
  }
  const tickEvery = Math.max(1, Math.ceil(n / 7));
  opts.labels.forEach((lb, i) => {
    if (i % tickEvery === 0 || (i === n - 1 && (n - 1) % tickEvery >= tickEvery * 0.6)) g += `<text x="${X(i)}" y="${PB - 8}" text-anchor="middle">${esc(lb)}</text>`;
  });
  const ordered = [...opts.series].sort((a, b) => (a.hi ? 1 : 0) - (b.hi ? 1 : 0)); // el resaltado va encima
  for (const s of ordered) {
    let d = "", pen = false, singles = "";
    s.values.forEach((v, i) => {
      if (v == null) { pen = false; return; }
      d += `${pen ? "L" : "M"}${X(i).toFixed(1)},${Y(v).toFixed(1)}`;
      pen = true;
      const prev = s.values[i - 1], next = s.values[i + 1];
      if (s.hi && prev == null && next == null) singles += `<circle cx="${X(i)}" cy="${Y(v)}" r="3.5" fill="var(--series)"/>`;
    });
    g += `<path d="${d}" fill="none" stroke="${s.hi ? "var(--series)" : "var(--muted-series)"}" stroke-width="${s.hi ? 2 : 1}" stroke-linejoin="round" stroke-linecap="round"/>${singles}`;
  }
  noteLines.forEach((ln, k) => { g += `<text class="chartnote" x="${L}" y="${PB + 8 + k * 14}" text-anchor="start">${esc(ln)}</text>`; });
  g += `<line id="cross" class="axis" y1="${T}" y2="${PB - B}" style="display:none"/><circle id="dot" r="4.5" fill="var(--series)" stroke="var(--card)" stroke-width="2" style="display:none"/>`;
  el.innerHTML = `<svg class="chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(opts.aria)}">${g}<rect id="hit" x="${L}" y="${T}" width="${W - L - R}" height="${PB - T - B}" fill="transparent"/></svg>`;
  const svg = $("svg", el), hi = opts.series.find((s) => s.hi) || opts.series[0];
  const move = (ev) => {
    const r = svg.getBoundingClientRect();
    const px = ((ev.clientX - r.left) / r.width) * W;
    const i = Math.max(0, Math.min(n - 1, Math.round(((px - L) / (W - L - R)) * (n - 1))));
    const v = hi.values[i], cross = $("#cross", svg), dot = $("#dot", svg);
    cross.setAttribute("x1", X(i)); cross.setAttribute("x2", X(i)); cross.style.display = "";
    if (v != null) { dot.setAttribute("cx", X(i)); dot.setAttribute("cy", Y(v)); dot.style.display = ""; } else dot.style.display = "none";
    tip(`<b>${esc(opts.labels[i])}</b><br>${v == null ? "sin dato" : nf.format(v) + (opts.unit ? " " + opts.unit : "")}`, ev.clientX, ev.clientY);
  };
  const hit = $("#hit", svg);
  hit.addEventListener("pointermove", move);
  hit.addEventListener("pointerdown", move);
  hit.addEventListener("pointerleave", () => { hideTip(); $("#cross", svg).style.display = "none"; $("#dot", svg).style.display = "none"; });
}

function tableView(summary, head, rows) {
  return `<details><summary>${esc(summary)}</summary><div class="tablewrap"><table><thead><tr>${head.map((h, i) => `<th class="${i ? "n" : ""}">${esc(h)}</th>`).join("")}</tr></thead><tbody>${rows.map((r) => `<tr>${r.map((c, i) => `<td class="${i ? "n" : ""}">${esc(c)}</td>`).join("")}</tr>`).join("")}</tbody></table></div></details>`;
}

/* ------------------------------------------------------------ Homicidios + mapa */
async function seguridad(H, GJ) {
  const body = $("#seguridad-body");
  if (!H) return unavailable(body, "F01");
  setHead("F01", true);
  if (FUENTES.F11) $("#src-F01").innerHTML += " " + srcBtn("F11");
  const years = H.years;
  body.innerHTML = `
    <div class="controls"><label for="yearsel">Mostrar</label>
      <select id="yearsel"><option value="all">Acumulado ${years[0]}–${years[years.length - 1]}</option>${[...years].reverse().map((y) => `<option value="${y}">Año ${y}</option>`).join("")}</select></div>
    <h3 class="subhead">Total de las 22 comunas por año</h3>
    <div id="cityline"></div>
    <div id="mapzone"></div>
    <div class="legend" id="legend"></div>
    <div id="detail" class="detail"></div>
    <details open><summary>Ranking de comunas (tabla)</summary><div class="tablewrap"><table><thead><tr><th>#</th><th>Comuna</th><th class="n">Homicidios</th></tr></thead><tbody id="rank"></tbody></table></div></details>
    <p class="sub" id="notes"></p>`;
  const cutNote = H.corte ? `La serie termina en ${H.corte.ultimo_anio_confiable} a propósito: ${H.corte.razon.charAt(0).toLowerCase() + H.corte.razon.slice(1)}` : "";
  const valueOf = (c, mode) => (mode === "all" ? c.total : c.serie[mode] ?? null);
  let mode = "all", selected = null, map = null, mapReady = false, breaks = [];
  const RAMP = ["var(--ramp-0)", "var(--ramp-1)", "var(--ramp-2)", "var(--ramp-3)", "var(--ramp-4)"];
  const rampPx = RAMP.map((v) => getComputedStyle(document.documentElement).getPropertyValue(v.slice(4, -1)).trim());

  function computeBreaks() {
    const vals = H.comunas.map((c) => valueOf(c, mode)).filter((v) => v != null).sort((a, b) => a - b);
    const q = (p) => vals[Math.min(vals.length - 1, Math.floor(p * vals.length))];
    breaks = [...new Set([q(0.2), q(0.4), q(0.6), q(0.8)])];
  }
  const bin = (v) => { if (v == null) return -1; let b = 0; for (const t of breaks) if (v >= t) b++; return b; };

  function legend() {
    const edges = [0, ...breaks];
    $("#legend").innerHTML = edges.map((lo, i) => {
      const hi = breaks[i];
      const txt = i === 0 ? `menos de ${fmt(hi)}` : hi == null ? `${fmt(lo)} o más` : `${fmt(lo)} a ${fmt(hi - 1)}`;
      return `<span><i style="background:${rampPx[Math.min(i, 4)]}"></i>${txt}</span>`;
    }).join("") + `<span><i style="background:var(--nodata)"></i>sin dato</span>`;
  }
  function rank() {
    const rows = H.comunas.map((c) => ({ c, v: valueOf(c, mode) })).sort((a, b) => (b.v ?? -1) - (a.v ?? -1));
    $("#rank").innerHTML = rows.map((r, i) => `<tr data-id="${r.c.id}" class="${r.c.id === selected ? "sel" : ""}"><td>${i + 1}</td><td>${esc(r.c.nombre)}</td><td class="n">${fmt(r.v)}</td></tr>`).join("");
    $("#rank").querySelectorAll("tr").forEach((tr) => tr.addEventListener("click", () => select(+tr.dataset.id)));
  }
  function detail() {
    const el = $("#detail");
    if (selected == null) { el.innerHTML = `<span class="sub">Toca una comuna del mapa o de la tabla para ver su historia.</span>`; return; }
    const c = H.comunas.find((x) => x.id === selected);
    const missing = years.filter((y) => c.serie[y] == null).length;
    const peak = years.reduce((b, y) => ((c.serie[y] ?? -1) > (c.serie[b] ?? -1) ? y : b), years[0]);
    el.innerHTML = `<h3>${esc(c.nombre)} ${srcBtn("F01")}</h3>
      <div class="kpis"><div class="kpi"><b>${fmt(c.total)}</b><span>acumulado ${years[0]}–${years[years.length - 1]}</span></div>
      <div class="kpi"><b>${fmt(c.serie[peak])}</b><span>año más alto: ${peak}</span></div>
      <div class="kpi"><b>${fmt(c.serie[years[years.length - 1]])}</b><span>en ${years[years.length - 1]}</span></div></div>
      <div id="spark"></div>${missing ? `<p class="sub">${missing} año(s) sin dato en la fuente; no se suman al acumulado.</p>` : ""}`;
    lineChart($("#spark"), { labels: years, series: [{ values: years.map((y) => c.serie[y] ?? null), hi: true }], unit: "homicidios", aria: `Homicidios por año en ${c.nombre}`, note: cutNote });
  }
  function paint() {
    computeBreaks(); legend(); rank(); detail();
    if (mapReady) {
      const src = map.getSource("comunas");
      src.setData({ ...GJ, features: GJ.features.map((f) => {
        const c = H.comunas.find((x) => x.id === f.properties.comuna_id);
        const v = c ? valueOf(c, mode) : null;
        return { ...f, properties: { ...f.properties, valor: v, bin: bin(v) } };
      }) });
    }
    $("#notes").textContent = `Son conteos, no tasas: no hay población por comuna para normalizarlos.`;
  }
  function select(id) {
    selected = id; detail(); rank();
    if (mapReady) map.setFilter("sel", ["==", ["get", "comuna_id"], id]);
  }
  $("#yearsel").addEventListener("change", (e) => { mode = e.target.value; paint(); });

  const zone = $("#mapzone");
  if (!GJ) {
    zone.innerHTML = `<div class="empty">El mapa no está disponible: la capa de comunas (F11) no respondió en la última corrida. La tabla de abajo muestra los mismos datos.</div>`;
  } else {
    zone.innerHTML = `<div class="mapbox"><div id="map"></div></div>`;
    try {
      const style = { version: 8, sources: {}, layers: [{ id: "bg", type: "background", paint: { "background-color": getComputedStyle(document.documentElement).getPropertyValue("--nodata").trim() } }] };
      map = new maplibregl.Map({ container: "map", style, attributionControl: false, cooperativeGestures: true });
      map.on("error", () => {});
      map.on("load", () => {
        map.addSource("comunas", { type: "geojson", data: GJ, promoteId: "comuna_id" });
        const colorExpr = ["match", ["get", "bin"], 0, rampPx[0], 1, rampPx[1], 2, rampPx[2], 3, rampPx[3], 4, rampPx[4], getComputedStyle(document.documentElement).getPropertyValue("--nodata").trim()];
        map.addLayer({ id: "fill", type: "fill", source: "comunas", paint: { "fill-color": colorExpr, "fill-opacity": 1 } });
        map.addLayer({ id: "line", type: "line", source: "comunas", paint: { "line-color": getComputedStyle(document.documentElement).getPropertyValue("--card").trim(), "line-width": 1.5 } });
        map.addLayer({ id: "sel", type: "line", source: "comunas", filter: ["==", ["get", "comuna_id"], -1], paint: { "line-color": getComputedStyle(document.documentElement).getPropertyValue("--text").trim(), "line-width": 3 } });
        const xs = GJ.features.flatMap((f) => JSON.stringify(f.geometry.coordinates).match(/-?\d+\.?\d*/g).map(Number));
        const lons = xs.filter((_, i) => i % 2 === 0), lats = xs.filter((_, i) => i % 2 === 1);
        const fit = () => map.fitBounds([[Math.min(...lons), Math.min(...lats)], [Math.max(...lons), Math.max(...lats)]], { padding: 16, animate: false });
        window.__map = map; window.__fit = fit; map.resize(); fit(); requestAnimationFrame(() => { map.resize(); fit(); });
        map.on("click", "fill", (e) => select(e.features[0].properties.comuna_id));
        map.on("mousemove", "fill", (e) => {
          const p = e.features[0].properties;
          tip(`<b>Comuna ${p.comuna_id}</b><br>${p.valor == null || p.valor === "null" ? "sin dato" : fmt(+p.valor) + " homicidios"}`, e.originalEvent.clientX, e.originalEvent.clientY);
        });
        map.on("mouseleave", "fill", hideTip);
        mapReady = true; paint();
      });
    } catch (err) {
      zone.innerHTML = `<div class="empty">Este navegador no pudo dibujar el mapa. La tabla de abajo muestra los mismos datos.</div>`;
    }
  }
  paint();
  lineChart($("#cityline"), { labels: years, series: [{ values: years.map((y) => H.ciudad[y] ?? null), hi: true }], unit: "homicidios (suma de lo que hay dato)", aria: "Total anual de homicidios en las 22 comunas", note: cutNote });
}

/* ------------------------------------------------------------ Aire */
function aire(A) {
  const body = $("#aire-body");
  if (!A) return unavailable(body, "F03");
  setHead("F03", true);
  const st = [...A.estaciones].sort((a, b) => b.promedio - a.promedio);
  body.innerHTML = `<div class="controls"><label for="stsel">Estación</label><select id="stsel">${st.map((s) => `<option>${esc(s.nombre)}</option>`).join("")}</select></div>
    <div id="aire-chart"></div>
    <p class="sub">La línea azul es la estación elegida; las grises son las demás. Los meses sin medición quedan como hueco: no se rellenan.</p>
    <table><thead><tr><th>Estación (peor promedio primero)</th><th class="n">Promedio ICA</th><th class="n">Meses con dato</th></tr></thead><tbody>${st.map((s) => `<tr><td>${esc(s.nombre)}</td><td class="n">${fmt(s.promedio)}</td><td class="n">${s.con_dato} de ${A.months.length}</td></tr>`).join("")}</tbody></table>`;
  const draw = () => {
    const sel = $("#stsel").value;
    lineChart($("#aire-chart"), { labels: A.months, series: A.estaciones.map((s) => ({ values: s.valores, hi: s.nombre === sel })), unit: "ICA", aria: `ICA mensual, estación ${sel}` });
  };
  $("#stsel").addEventListener("change", draw);
  draw();
}

/* ------------------------------------------------------------ Educación */
function educacion(E) {
  const body = $("#educacion-body");
  if (!E) return unavailable(body, "F04");
  setHead("F04", true);
  const max = Math.max(...E.top_instituciones.map((i) => i.programas), 1);
  const jmax = Math.max(...E.jornadas.map((j) => j.programas), 1);
  const bars = (arr, key, val, m, tipUnit) => `<div class="bars">${arr.map((r) => `<div class="bar" data-tip="${esc(title(r[key]))}: ${fmt(r[val])} ${tipUnit}"><span class="lab" title="${esc(r[key])}">${esc(title(r[key]))}</span><span class="track"><div class="fill" style="width:${(r[val] / m) * 100}%"></div></span><span class="v">${fmt(r[val])}</span></div>`).join("")}</div>`;
  body.innerHTML = `<div class="kpis"><div class="kpi"><b>${fmt(E.programas)}</b><span>programas</span></div><div class="kpi"><b>${fmt(E.instituciones)}</b><span>instituciones</span></div></div>
    <h3 style="font-size:1rem;margin:12px 0 0">Instituciones con más programas</h3>${bars(E.top_instituciones, "nombre", "programas", max, "programas")}
    <h3 style="font-size:1rem;margin:16px 0 0">Programas por jornada</h3>${bars(E.jornadas, "jornada", "programas", jmax, "programas")}
    <p class="sub">Un programa puede dictarse en más de una jornada, por eso las jornadas suman más que el total de programas.</p>`;
  body.querySelectorAll(".bar").forEach((b) => {
    b.addEventListener("pointermove", (e) => tip(b.dataset.tip, e.clientX, e.clientY));
    b.addEventListener("pointerleave", hideTip);
  });
}

/* ------------------------------------------------------------ Población */
function poblacion(P) {
  const body = $("#poblacion-body");
  if (!P) return unavailable(body, "F09");
  setHead("F09", true);
  RESIZE.set(body, () => poblacion(P));
  const cs = P.censos.filter((c) => c.total != null);
  const last = cs[cs.length - 1];
  const W = Math.max(280, Math.round(body.clientWidth || 640)), H = 220, L = 52, R = 8, T = 12, B = 28;
  const ymax = niceMax(Math.max(...cs.map((c) => c.total)));
  const bw = (W - L - R) / cs.length;
  let g = "";
  for (let k = 0; k <= 4; k++) { const v = (ymax * k) / 4, y = T + (1 - v / ymax) * (H - T - B); g += `<line class="grid" x1="${L}" x2="${W - R}" y1="${y}" y2="${y}"/><text x="${L - 6}" y="${y + 4}" text-anchor="end">${nf.format(v)}</text>`; }
  cs.forEach((c, i) => {
    const base = H - B, h = Math.max(6, (c.total / ymax) * (H - T - B)), x = L + i * bw + bw * 0.2, w = bw * 0.6, top = base - h;
    g += `<path class="bar-m" data-i="${i}" d="M${x},${base} V${top + 4} a4,4 0 0 1 4,-4 h${w - 8} a4,4 0 0 1 4,4 V${base}z" fill="var(--series)"/>`;
    g += `<text x="${x + w / 2}" y="${H - 8}" text-anchor="middle">${c.anio}</text>`;
  });
  body.innerHTML = `<div class="kpis"><div class="kpi"><b>${fmt(last.total)}</b><span>habitantes en el censo de ${last.anio} (el último de esta fuente)</span></div></div>
    <svg class="chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="Población total por censo">${g}</svg>
    <p class="sub">Esta fuente termina en ${last.anio}. No incluye el censo de 2018 ni proyecciones; por eso no se usa para calcular tasas.</p>
    ${tableView("Ver como tabla", ["Año", "Total", "Cabecera", "Resto", "% cabecera"], P.censos.map((c) => [c.anio, fmt(c.total), fmt(c.cabecera), fmt(c.resto), c.pct_cabecera == null ? "sin dato" : c.pct_cabecera + " %"]))}`;
  body.querySelectorAll(".bar-m").forEach((p) => {
    const c = cs[+p.dataset.i];
    const f = (e) => tip(`<b>Censo ${c.anio}</b><br>${fmt(c.total)} habitantes${c.pct_cabecera != null ? `<br>${c.pct_cabecera} % en cabecera` : ""}`, e.clientX, e.clientY);
    p.addEventListener("pointermove", f); p.addEventListener("pointerdown", f); p.addEventListener("pointerleave", hideTip);
  });
}

/* ------------------------------------------------------------ arranque */
async function main() {
  const [group, status, fuentes, H, A, E, P, GJ] = await Promise.all(
    ["group.json", "data/status.json", "data/fuentes.json", "data/homicidios.json", "data/ica.json", "data/educacion.json", "data/poblacion.json", "data/comunas.geojson"].map(getJSON));
  STATUS = status; FUENTES = fuentes || {};
  const names = (group && group.nombres) || ["[escribir los nombres del grupo en site/group.json]"];
  $("#group").textContent = "Grupo: " + names.join(", ");
  $("#footer").innerHTML = `Ciudad: Santiago de Cali · Grupo: ${esc(names.join(", "))}` +
    (group && group.repo ? ` · <a href="${esc(group.repo)}" target="_blank" rel="noopener">Repositorio</a>` : "") +
    (status ? (status.mode === "snapshot" && status.snapshot ? ` · Copia de datos del ${esc(status.snapshot.descargada_el)}` : ` · Datos descargados: ${esc((status.built_from_run || "").slice(0, 10))}`) : "");

  const banner = $("#banner");
  if (!status) {
    banner.textContent = "Todavía no hay datos: corre la ingesta (python scripts/run_all.py) o espera la primera ejecución de la acción de GitHub.";
    banner.classList.remove("hidden");
  } else if (status.mode === "snapshot") {
    const sn = status.snapshot || {};
    banner.textContent = `Copia de datos del ${sn.descargada_el || "?"}: el portal de la Alcaldía (datos.cali.gov.co) está fuera de línea desde el 21 de octubre de 2026, así que las fuentes ${(sn.sources || []).join(", ")} salen de la copia que el grupo descargó a mano antes del cierre.` +
      (Object.keys(status.failed || {}).length ? " Sin datos: " + Object.keys(status.failed).join(", ") + "." : "");
    banner.classList.remove("hidden");
  } else if (status.mode !== "live") {
    banner.textContent = "DATOS DE PRUEBA: son cifras sintéticas para probar el sistema, no son datos de Cali.";
    banner.classList.remove("hidden");
  } else if (Object.keys(status.failed || {}).length) {
    banner.textContent = "Algunas fuentes no respondieron en la última corrida: " + Object.keys(status.failed).join(", ") + ". Esas vistas aparecen como no disponibles.";
    banner.classList.remove("hidden");
  }

  const qs = [
    { ok: !!H, t: "¿Qué comunas concentran más homicidios y cómo cambió entre 1993 y 2018?", a: "#seguridad", why: "falta F01" },
    { ok: !!A, t: "¿Qué estación de monitoreo registra peor calidad del aire mes a mes?", a: "#aire", why: "falta F03" },
    { ok: !!E, t: "¿Qué instituciones ofrecen más programas de educación para el trabajo y en qué jornada?", a: "#educacion", why: "falta F04" },
    { ok: false, t: "¿Qué tan grave es un indicador comparado con la población actual de cada comuna?", a: "#limites", why: "pendiente: la Alcaldía publica población por comuna («Población y densidad»), pero no se pudo descargar mientras su portal estuvo fuera de línea" },
  ];
  $("#qlist").innerHTML = qs.map((q) => `<li><span class="tag ${q.ok ? "ok" : "pend"}">${q.ok ? "Respondida" : "Pendiente"}</span><span><a href="${q.a}">${esc(q.t)}</a>${q.ok ? "" : ` <span class="sub">(${esc(q.why)})</span>`}</span></li>`).join("");

  await seguridad(H, GJ);
  aire(A); educacion(E); poblacion(P);
}
main();
