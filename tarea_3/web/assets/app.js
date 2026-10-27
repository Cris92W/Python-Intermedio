// Dashboard del Niño Costero 2017 y 2023. Datos en data/ (los genera scripts/analizar_datos.py).

const estado = { evento: "2017", departamento: "TODOS", indicador: "inund_anom_km2", zona: "piura", indeci: "damnificados" };
const datos = { zonas: {} };
const DEPARTAMENTOS = ["PIURA", "LAMBAYEQUE", "LA LIBERTAD", "ÁNCASH", "LIMA"];
const COLOR_DEP = { "PIURA": "#0b6e99", "LAMBAYEQUE": "#e07a1f", "LA LIBERTAD": "#2f9e44", "ÁNCASH": "#9c36b5", "LIMA": "#c92a2a" };
const NOMBRE_DEP = { "PIURA": "Piura", "LAMBAYEQUE": "Lambayeque", "LA LIBERTAD": "La Libertad", "ÁNCASH": "Áncash", "LIMA": "Lima" };

// Cortes de color por indicador (azules: más agua, más oscuro)
const ESCALAS = {
  inund_anom_km2: { cortes: [0.1, 1, 5, 20, 50], unidad: "km²" },
  inund_union_km2: { cortes: [0.1, 1, 5, 20, 50], unidad: "km²" },
  inund_max_km2: { cortes: [0.1, 1, 5, 20, 50], unidad: "km²" },
  pct_max: { cortes: [0.05, 0.5, 2, 5, 10], unidad: "%" },
  fechas_con_agua: { cortes: [1, 3, 6, 10, 20], unidad: "fechas" },
};
const AZULES = ["#eef2f5", "#c6dbef", "#9ecae1", "#6baed6", "#3182bd", "#08519c"];

// Categorías de los edificios en 3D
const CATEGORIAS = [
  { id: "destruido", nombre: "Manzana destruida (Copernicus)", color: "#7f1d1d" },
  { id: "grave", nombre: "Manzana con daño grave", color: "#dc2626" },
  { id: "moderado", nombre: "Manzana con daño moderado", color: "#f97316" },
  { id: "leve", nombre: "Manzana con daño leve", color: "#facc15" },
  { id: "huaico", nombre: "En zona de huaico (Copernicus)", color: "#8b5a2b" },
  { id: "inundacion", nombre: "En zona inundada (Copernicus)", color: "#2563eb" },
  { id: "gfm2017", nombre: "En zona inundada (radar 2017)", color: "#06b6d4" },
  { id: "gfm2023", nombre: "En zona inundada (radar 2023)", color: "#a21caf" },
  { id: "ninguna", nombre: "Sin afectación detectada", color: "#d4d4d8" },
];
const COLOR_CAT = Object.fromEntries(CATEGORIAS.map(c => [c.id, c.color]));
// Centro: mediana de los edificios afectados en 2017 (scripts/edificios_afectados.py)
const CENTRO_ZONA = { piura: [-80.635, -5.197], trujillo: [-79.05, -8.049] };

const fmt = (n, d = 0) => (n == null || isNaN(n)) ? "–" : Number(n).toLocaleString("es-PE", { maximumFractionDigits: d, minimumFractionDigits: d });
const nombreDep = d => NOMBRE_DEP[d] || d;

async function cargarJSON(ruta) {
  const r = await fetch(ruta);
  if (!r.ok) throw new Error(`No se pudo cargar ${ruta}`);
  return r.json();
}

async function iniciar() {
  [datos.distritos, datos.serie, datos.indeci, datos.resumen] = await Promise.all([
    cargarJSON("data/distritos.geojson"), cargarJSON("data/serie_gfm.json"),
    cargarJSON("data/indeci.json"), cargarJSON("data/resumen.json"),
  ]);
  llenarBuscador();
  iniciarMapa();
  iniciarGraficos();
  iniciarMapa3D();
  pintarHallazgos();
  conectarControles();
  actualizarTodo();
}

// ---------- Controles ----------
function conectarControles() {
  segmentado("ctl-evento", v => { estado.evento = v; actualizarTodo(); actualizar3D(); });
  segmentado("ctl-zona", v => { estado.zona = v; cargarZona(v); });
  document.getElementById("ctl-departamento").addEventListener("change", e => {
    estado.departamento = e.target.value; actualizarTodo(); encuadrarDepartamento();
  });
  document.getElementById("ctl-indicador").addEventListener("change", e => { estado.indicador = e.target.value; actualizarTodo(); });
  document.getElementById("ctl-indeci").addEventListener("change", e => { estado.indeci = e.target.value; actualizarIndeci(); });
  document.getElementById("ctl-buscar").addEventListener("change", e => buscarDistrito(e.target.value));
  document.querySelectorAll(".capas input").forEach(cb => cb.addEventListener("change", actualizarCapas3D));
}

function segmentado(id, alCambiar) {
  const grupo = document.getElementById(id);
  grupo.addEventListener("click", e => {
    const b = e.target.closest("button");
    if (!b) return;
    grupo.querySelectorAll("button").forEach(x => { x.classList.toggle("activo", x === b); x.setAttribute("aria-checked", x === b); });
    alCambiar(b.dataset.valor);
  });
}

function actualizarTodo() {
  actualizarKPIs();
  actualizarMapa();
  actualizarRanking();
  actualizarSerie();
  actualizarIndeci();
}

const distritosFiltrados = () => datos.distritos.features.filter(f => estado.departamento === "TODOS" || f.properties.NOMBDEP === estado.departamento);
const campo = (ind = estado.indicador, ev = estado.evento) => `${ind}_${ev}`;

// ---------- KPIs ----------
function filaIndeci(evento) {
  const filas = datos.indeci.departamento.filter(r => String(r.evento) === evento && DEPARTAMENTOS.includes(r.departamento));
  const sel = estado.departamento === "TODOS" ? filas : filas.filter(r => r.departamento === estado.departamento);
  const suma = k => sel.reduce((a, r) => a + (r[k] || 0), 0);
  return { damnificados: suma("damnificados"), fallecidos: suma("fallecidos"), destruidas: suma("viviendas_destruidas"),
           inhabitables: suma("viviendas_inhabitables"), afectadas: suma("viviendas_afectadas") };
}

function sumaGFM(evento) {
  const fs = distritosFiltrados();
  return {
    km2: fs.reduce((a, f) => a + (f.properties[`inund_anom_km2_${evento}`] || 0), 0),
    distritos: fs.filter(f => (f.properties[`inund_anom_km2_${evento}`] || 0) >= 0.1).length,
    total: fs.length,
  };
}

function actualizarKPIs() {
  const ev = estado.evento, otro = ev === "2017" ? "2023" : "2017";
  const a = filaIndeci(ev), b = filaIndeci(otro), g = sumaGFM(ev), h = sumaGFM(otro);
  const ambito = estado.departamento === "TODOS" ? "5 departamentos" : nombreDep(estado.departamento);
  const tarjetas = [
    { valor: fmt(a.damnificados), nombre: "Damnificados", comp: `${otro}: ${fmt(b.damnificados)}`, fuente: "INDECI" },
    { valor: fmt(a.fallecidos), nombre: "Fallecidos", comp: `${otro}: ${fmt(b.fallecidos)}`, fuente: "INDECI" },
    { valor: fmt(a.destruidas), nombre: "Viviendas destruidas", comp: `${otro}: ${fmt(b.destruidas)}`, fuente: "INDECI" },
    { valor: `${fmt(g.km2, 0)} km²`, nombre: "Inundación anómala (radar)", comp: `${otro}: ${fmt(h.km2, 0)} km²`, fuente: "Copernicus GFM, sin el agua habitual de 2022" },
    { valor: `${g.distritos} / ${g.total}`, nombre: "Distritos con inundación anómala", comp: `${otro}: ${h.distritos}`, fuente: "Copernicus GFM (≥ 0,1 km²)" },
  ];
  document.getElementById("kpis").innerHTML = tarjetas.map(t => `
    <div class="kpi"><div class="valor">${t.valor}</div><div class="nombre">${t.nombre} · ${ev} · ${ambito}</div>
    <div class="comparacion">${t.comp}</div><div class="fuente">${t.fuente}</div></div>`).join("");
}

// ---------- Mapa 2D ----------
let mapa;
function estiloBase(fuenteTeselas, atribucion) {
  return {
    version: 8,
    sources: { base: { type: "raster", tiles: fuenteTeselas, tileSize: 256, attribution: atribucion } },
    layers: [{ id: "base", type: "raster", source: "base" }],
  };
}
const GRIS = ["https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}"];
const ATRIB_GRIS = "Mapa base © Esri, HERE, Garmin, © OpenStreetMap contributors";

function iniciarMapa() {
  mapa = new maplibregl.Map({ container: "mapa", style: estiloBase(GRIS, ATRIB_GRIS), center: [-78.6, -8.6], zoom: 5.4 });
  mapa.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
  mapa.on("load", () => {
    mapa.addSource("distritos", { type: "geojson", data: datos.distritos, promoteId: "UBIGEO" });
    mapa.addLayer({ id: "relleno", type: "fill", source: "distritos", paint: { "fill-color": colorExpr(), "fill-opacity": 0.85 } });
    mapa.addLayer({ id: "borde", type: "line", source: "distritos", paint: { "line-color": "#ffffff", "line-width": 0.4 } });
    mapa.addLayer({ id: "resalte", type: "line", source: "distritos", paint: {
      "line-color": "#111", "line-width": ["case", ["boolean", ["feature-state", "sel"], false], 2.5, 0] } });
    mapa.on("click", "relleno", e => mostrarPopup(e.features[0], e.lngLat));
    mapa.on("mouseenter", "relleno", () => mapa.getCanvas().style.cursor = "pointer");
    mapa.on("mouseleave", "relleno", () => mapa.getCanvas().style.cursor = "");
    actualizarMapa();
    encuadrarDepartamento(0);
  });
}

function colorExpr() {
  const { cortes } = ESCALAS[estado.indicador];
  const expr = ["step", ["coalesce", ["get", campo()], 0], AZULES[0]];
  cortes.forEach((c, i) => expr.push(c, AZULES[i + 1]));
  return expr;
}

function actualizarMapa() {
  if (!mapa || !mapa.getLayer("relleno")) return;
  mapa.setPaintProperty("relleno", "fill-color", colorExpr());
  const filtro = estado.departamento === "TODOS" ? null : ["==", ["get", "NOMBDEP"], estado.departamento];
  ["relleno", "borde", "resalte"].forEach(id => mapa.setFilter(id, filtro));
  const { cortes, unidad } = ESCALAS[estado.indicador];
  const etiquetas = [`< ${fmt(cortes[0], 2)}`].concat(cortes.map((c, i) => i < cortes.length - 1 ? `${fmt(c, 2)} – ${fmt(cortes[i + 1], 2)}` : `≥ ${fmt(c, 2)}`));
  document.getElementById("leyenda-mapa").innerHTML = `<b>${document.querySelector("#ctl-indicador option:checked").textContent} · ${estado.evento}</b>` +
    etiquetas.map((t, i) => `<div class="item"><span class="muestra" style="background:${AZULES[i]}"></span>${t} ${unidad}</div>`).join("");
}

function encuadrarDepartamento(duracion = 800) {
  const fs = distritosFiltrados();
  const b = new maplibregl.LngLatBounds();
  fs.forEach(f => recorrerCoords(f.geometry.coordinates, c => b.extend(c)));
  mapa.fitBounds(b, { padding: 30, duration: duracion });
}
function recorrerCoords(c, fn) { typeof c[0] === "number" ? fn(c) : c.forEach(x => recorrerCoords(x, fn)); }

let seleccionado = null, popup;
function mostrarPopup(f, lngLat) {
  const p = f.properties;
  if (seleccionado) mapa.setFeatureState({ source: "distritos", id: seleccionado }, { sel: false });
  seleccionado = p.UBIGEO;
  mapa.setFeatureState({ source: "distritos", id: seleccionado }, { sel: true });
  const fila = ev => `<tr><td>${ev}</td><td>${fmt(p[`inund_anom_km2_${ev}`], 2)}</td><td>${fmt(p[`inund_max_km2_${ev}`], 2)}</td><td>${p[`fecha_max_${ev}`] || "–"}</td></tr>`;
  if (popup) popup.remove();
  popup = new maplibregl.Popup({ maxWidth: "320px" }).setLngLat(lngLat).setHTML(`
    <b>${p.NOMBDIST}</b><br><small>${p.NOMBPROV}, ${nombreDep(p.NOMBDEP)} · ${fmt(p.area_km2, 0)} km²</small>
    <table style="margin-top:6px;font-size:12px;border-collapse:collapse" cellpadding="3">
    <tr><th></th><th>Anómalo km²</th><th>Máx. 1 día</th><th>Fecha pico</th></tr>${fila("2017")}${fila("2023")}</table>
    <small>Agua habitual (ene–jun 2022): ${fmt(p.agua_habitual_km2, 2)} km²</small>`).addTo(mapa);
}

function llenarBuscador() {
  document.getElementById("lista-distritos").innerHTML = datos.distritos.features
    .map(f => `<option value="${f.properties.NOMBDIST} (${nombreDep(f.properties.NOMBDEP)})">`).join("");
}
function buscarDistrito(texto) {
  const f = datos.distritos.features.find(x => `${x.properties.NOMBDIST} (${nombreDep(x.properties.NOMBDEP)})` === texto);
  if (!f) return;
  const b = new maplibregl.LngLatBounds();
  recorrerCoords(f.geometry.coordinates, c => b.extend(c));
  mapa.fitBounds(b, { padding: 60, maxZoom: 11, duration: 800 });
  mostrarPopup(f, b.getCenter());
}

function actualizarRanking() {
  const k = campo(), { unidad } = ESCALAS[estado.indicador];
  const top = distritosFiltrados().filter(f => (f.properties[k] || 0) > 0)
    .sort((a, b) => b.properties[k] - a.properties[k]).slice(0, 10);
  const max = top.length ? top[0].properties[k] : 1;
  document.getElementById("titulo-ranking").textContent = `Top 10 distritos · ${estado.evento}`;
  const lista = document.getElementById("ranking");
  lista.innerHTML = top.length ? top.map(f => `<li data-ubigeo="${f.properties.UBIGEO}">
      <span>${f.properties.NOMBDIST} <small>${nombreDep(f.properties.NOMBDEP)}</small></span>
      <b>${fmt(f.properties[k], k.startsWith("fechas") ? 0 : 1)} ${unidad}</b>
      <span class="barra"><span style="width:${100 * f.properties[k] / max}%"></span></span></li>`).join("")
    : "<li>Sin agua detectada en esta selección.</li>";
  lista.querySelectorAll("li[data-ubigeo]").forEach(li => li.addEventListener("click", () => {
    const f = datos.distritos.features.find(x => x.properties.UBIGEO === li.dataset.ubigeo);
    buscarDistrito(`${f.properties.NOMBDIST} (${nombreDep(f.properties.NOMBDEP)})`);
  }));
}

// ---------- Gráficos ----------
let graficoSerie, graficoIndeci;
function iniciarGraficos() {
  Chart.defaults.font.family = "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif";
  Chart.defaults.color = getComputedStyle(document.body).getPropertyValue("--suave").trim() || "#5b6676";
  graficoSerie = new Chart(document.getElementById("grafico-serie"), {
    type: "line",
    data: { datasets: [] },
    options: {
      maintainAspectRatio: false, parsing: false, spanGaps: false,
      interaction: { mode: "nearest", intersect: false },
      scales: {
        x: { type: "time", time: { unit: "week", tooltipFormat: "dd/MM/yyyy" }, title: { display: true, text: "Fecha de la pasada del radar" } },
        y: { beginAtZero: true, title: { display: true, text: "km² inundados" } },
      },
      plugins: { tooltip: { callbacks: {
        title: items => `Semana del ${new Date(items[0].raw.x).toLocaleDateString("es-PE")}`,
        label: c => `${c.dataset.label}: ${fmt(c.raw.y, 1)} km² (pasada del ${c.raw.fecha.split("-").reverse().join("/")})` } } },
    },
  });
  graficoIndeci = new Chart(document.getElementById("grafico-indeci"), {
    type: "bar",
    data: { labels: DEPARTAMENTOS.map(nombreDep), datasets: [] },
    options: { maintainAspectRatio: false, scales: { y: { beginAtZero: true } },
               plugins: { tooltip: { callbacks: { label: c => `${c.dataset.label}: ${fmt(c.raw)}` } } } },
  });
}

// Pasadas alternas del radar ven zonas distintas (órbitas ascendente y descendente): la serie diaria salta
// entre 0 y el máximo. Se grafica el máximo de cada semana (lunes a domingo), que sí se puede leer.
function inicioSemana(fecha) {
  const d = new Date(fecha + "T12:00:00");
  d.setDate(d.getDate() - ((d.getDay() + 6) % 7));
  return d.getTime();
}

function actualizarSerie() {
  const deps = estado.departamento === "TODOS" ? DEPARTAMENTOS : [estado.departamento];
  graficoSerie.data.datasets = deps.map(d => {
    const semanas = new Map();
    datos.serie.filter(r => String(r.evento) === estado.evento && r.NOMBDEP === d).forEach(r => {
      const s = inicioSemana(r.fecha_peru), previo = semanas.get(s);
      if (!previo || r.anomalo_km2 > previo.y) semanas.set(s, { x: s, y: r.anomalo_km2, obs: r.pct_observado, fecha: r.fecha_peru });
    });
    return { label: nombreDep(d), borderColor: COLOR_DEP[d], backgroundColor: COLOR_DEP[d], pointRadius: 2.5, borderWidth: 2,
             tension: 0.25, data: [...semanas.values()].sort((a, b) => a.x - b.x) };
  });
  graficoSerie.update();
}

function actualizarIndeci() {
  const k = estado.indeci;
  const valor = (ev, d) => (datos.indeci.departamento.find(r => String(r.evento) === ev && r.departamento === d) || {})[k];
  const atenuar = (c, d) => estado.departamento === "TODOS" || estado.departamento === d ? c : c + "40";
  graficoIndeci.data.datasets = [
    { label: "2017", data: DEPARTAMENTOS.map(d => valor("2017", d)), backgroundColor: DEPARTAMENTOS.map(d => atenuar("#0b6e99", d)) },
    { label: "2023", data: DEPARTAMENTOS.map(d => valor("2023", d)), backgroundColor: DEPARTAMENTOS.map(d => atenuar("#e07a1f", d)) },
  ];
  graficoIndeci.update();
}

// ---------- Mapa 3D ----------
let mapa3d;
const ESRI = ["https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"];
const ATRIB_ESRI = "Imágenes © Esri, Maxar, Earthstar Geographics · Edificios © Microsoft (ODbL)";
const CAPAS_ZONA = {
  "ems-inundacion": { filtro: ["all", ["==", ["get", "fuente"], "Copernicus EMS 2017"], ["==", ["get", "tipo"], "inundacion"]], color: "#3b82f6" },
  "ems-huaico": { filtro: ["all", ["==", ["get", "fuente"], "Copernicus EMS 2017"], ["==", ["get", "tipo"], "huaico"]], color: "#a16207" },
  "gfm-2017": { filtro: ["==", ["get", "fuente"], "GFM 2017"], color: "#22d3ee" },
  "gfm-2023": { filtro: ["==", ["get", "fuente"], "GFM 2023"], color: "#d946ef" },
};

function iniciarMapa3D() {
  mapa3d = new maplibregl.Map({ container: "mapa3d", style: estiloBase(ESRI, ATRIB_ESRI), center: CENTRO_ZONA.piura,
                                zoom: 14, pitch: 58, bearing: -25, maxPitch: 75 });
  mapa3d.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), "top-right");
  mapa3d.on("load", () => {
    mapa3d.addSource("zonas", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
    mapa3d.addSource("edificios", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
    Object.entries(CAPAS_ZONA).forEach(([id, c]) => mapa3d.addLayer({ id, type: "fill", source: "zonas", filter: c.filtro,
      paint: { "fill-color": c.color, "fill-opacity": 0.35 } }));
    mapa3d.addLayer({ id: "edificios-3d", type: "fill-extrusion", source: "edificios", paint: {
      "fill-extrusion-color": colorEdificio(), "fill-extrusion-height": alturaEdificio(),
      "fill-extrusion-base": 0, "fill-extrusion-opacity": 0.92 } });
    mapa3d.on("click", "edificios-3d", e => {
      const p = e.features[0].properties;
      new maplibregl.Popup().setLngLat(e.lngLat).setHTML(`<b>Edificio</b><br>
        Copernicus 2017: ${p.ems2017_huaico ? "zona de huaico" : p.ems2017_inundacion ? "zona inundada" : "fuera de zonas delimitadas"}
        ${p.ems2017_grado ? `<br>Daño de su manzana: <b>${p.ems2017_grado}</b>` : ""}
        <br>Radar 2017: ${p.gfm2017 ? "agua detectada" : "sin agua"} · Radar 2023: ${p.gfm2023 ? "agua detectada" : "sin agua"}`).addTo(mapa3d);
    });
    pintarLeyenda3D();
    cargarZona("piura");
  });
}

// Categoría según el evento elegido: el daño de manzana manda sobre la zona, y la delimitación manual sobre el radar.
function categoriaExpr() {
  if (estado.evento === "2023") return ["case", ["boolean", ["get", "gfm2023"], false], "gfm2023", "ninguna"];
  return ["case",
    ["!=", ["get", "ems2017_grado"], ""], ["get", "ems2017_grado"],
    ["boolean", ["get", "ems2017_huaico"], false], "huaico",
    ["boolean", ["get", "ems2017_inundacion"], false], "inundacion",
    ["boolean", ["get", "gfm2017"], false], "gfm2017",
    "ninguna"];
}
function colorEdificio() { return ["match", categoriaExpr(), ...CATEGORIAS.flatMap(c => [c.id, c.color]), "#d4d4d8"]; }
function alturaEdificio() { return ["match", categoriaExpr(), "ninguna", 4, 14]; }

async function cargarZona(zona) {
  if (!datos.zonas[zona]) {
    const [edif, zonas] = await Promise.all([cargarJSON(`data/edificios_${zona}.geojson`), cargarJSON(`data/zonas_${zona}.geojson`)]);
    datos.zonas[zona] = { edif, zonas };
  }
  mapa3d.getSource("edificios").setData(datos.zonas[zona].edif);
  mapa3d.getSource("zonas").setData(datos.zonas[zona].zonas);
  mapa3d.flyTo({ center: CENTRO_ZONA[zona], zoom: 14, pitch: 58, bearing: -25, duration: 1200 });
  actualizar3D();
}

function actualizar3D() {
  if (!mapa3d || !mapa3d.getLayer("edificios-3d")) return;
  mapa3d.setPaintProperty("edificios-3d", "fill-extrusion-color", colorEdificio());
  mapa3d.setPaintProperty("edificios-3d", "fill-extrusion-height", alturaEdificio());
  const r = (datos.resumen.edificios || []).find(x => x.zona === estado.zona);
  if (!r) return;
  document.getElementById("conteo-3d").innerHTML = `
    <div class="kpi"><div class="valor">${fmt(r.afectado_2017)}</div><div class="nombre">2017: en zona inundada, de huaico o en manzana dañada</div>
      <div class="comparacion">Copernicus: ${fmt(r.ems2017_inundacion)} inundación · ${fmt(r.ems2017_huaico)} huaico · ${fmt(r.ems2017_manzana_danada)} manzana dañada · radar: ${fmt(r.gfm2017)}</div></div>
    <div class="kpi" style="margin-top:10px"><div class="valor">${fmt(r.afectado_2023)}</div><div class="nombre">2023: en zona inundada según el radar</div>
      <div class="comparacion">En 2023 no hubo mapeo manual de Copernicus en esta zona.</div></div>
    <p class="nota">De ${fmt(r.edificios)} edificios en la zona.</p>`;
  actualizarCapas3D();
}

function actualizarCapas3D() {
  if (!mapa3d || !mapa3d.getLayer("edificios-3d")) return;
  document.querySelectorAll(".capas input").forEach(cb =>
    mapa3d.setLayoutProperty(cb.dataset.capa, "visibility", cb.checked ? "visible" : "none"));
}

function pintarLeyenda3D() {
  document.getElementById("leyenda-3d").innerHTML = "<b>Color del edificio</b>" +
    CATEGORIAS.map(c => `<div class="item"><span class="muestra" style="background:${c.color}"></span>${c.nombre}</div>`).join("");
}

// ---------- Hallazgos ----------
function pintarHallazgos() {
  const h = (datos.resumen.hallazgos || []);
  document.getElementById("hallazgos").innerHTML = h.map(x => `<div class="hallazgo"><h3>${x.titulo}</h3><p>${x.texto}</p></div>`).join("");
}

iniciar().catch(err => {
  document.querySelector("main").insertAdjacentHTML("afterbegin", `<p class="bloque">Error al cargar los datos: ${err.message}</p>`);
  console.error(err);
});
