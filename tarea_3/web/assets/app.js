/* Piura en los Niños Costeros de 2017 y 2023: story map por capítulos y explorador.
   Datos en data/ (los genera scripts/analizar_datos.py y compañía). Mapas con MapLibre GL; gráficos en SVG propio. */
(function () {
  'use strict';
  const REDUCE = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const MOBILE = window.matchMedia('(max-width: 899px)');
  const EVENTOS = ['2017', '2023'];
  const NNBSP = ' ';
  const MESES = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'];
  const PIURA_B = [-81.36, -6.40, -79.18, -4.05];
  const NORTE_B = [-82.6, -9.6, -76.2, -2.9];
  const CIUDAD_B = [-80.74, -5.30, -80.58, -5.14];
  const CIUDADES = [['Piura', -80.632, -5.194], ['Sullana', -80.685, -4.904], ['Talara', -81.272, -4.577], ['Paita', -81.114, -5.089],
    ['Sechura', -80.822, -5.557], ['Chulucanas', -80.162, -5.093], ['Huancabamba', -79.451, -5.239], ['Ayabaca', -79.715, -4.639]];
  const W1 = '#a6e8ff', W2 = '#54c4f5', W3 = '#208ce6', W4 = '#1852c4';
  const E17N = '#f2a03d', E23N = '#6cc3d8', HU = '#e07a3a', HU2 = '#b08a5a';
  // Límites: línea clara sobre un halo oscuro, para que se lean sobre la imagen satelital
  const HALO = '#05061a';
  const GRADOS = [['leve', 'Daño leve', '#f2d16b'], ['moderado', 'Daño moderado', '#ee9a3a'], ['grave', 'Daño grave', '#d6453d'], ['destruido', 'Destruido', '#8a2246']];
  const ESRI = s => `https://server.arcgisonline.com/ArcGIS/rest/services/${s}/MapServer/tile/{z}/{y}/{x}`;

  /* ---------- Formatos ---------- */
  function fmt(n, d = 0) {
    const s = Math.abs(n).toFixed(d).split('.');
    const i = s[0].length > 3 ? s[0].replace(/\B(?=(\d{3})+(?!\d))/g, NNBSP) : s[0];
    return (n < 0 && +s.join('') !== 0 ? '−' : '') + i + (s[1] ? ',' + s[1] : '');
  }
  const fecha = (s, anio = true) => { const [y, m, d] = s.split('-'); return `${+d} ${MESES[+m - 1]}${anio ? ' ' + y : ''}`; };
  const MINUS = new Set(['de', 'del', 'la', 'las', 'el', 'los', 'y']);
  const ARREGLOS = { COLAN: 'Colán', 'EL TALLAN': 'El Tallán', FRIAS: 'Frías', JILILI: 'Jililí', 'LA UNION': 'La Unión', 'BELLAVISTA DE LA UNION': 'Bellavista de la Unión',
    'LOS ORGANOS': 'Los Órganos', MANCORA: 'Máncora', MORROPON: 'Morropón', 'MORROPÓN': 'Morropón', 'VEINTISEIS DE OCTUBRE': 'Veintiséis de Octubre' };
  const nombre = s => ARREGLOS[s] || s.toLowerCase().split(' ').map((w, i) => i && MINUS.has(w) ? w : w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
  const niceMax = v => { if (!(v > 0)) return 1; const p = 10 ** Math.floor(Math.log10(v)), n = v / p; return (n <= 1 ? 1 : n <= 2 ? 2 : n <= 2.5 ? 2.5 : n <= 5 ? 5 : 10) * p; };
  const ease = t => t < .5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
  const $ = id => document.getElementById(id);
  const get = p => fetch(p).then(r => { if (!r.ok) throw new Error(`${p}: ${r.status}`); return r.json(); });
  const dig = (o, path) => path.split('.').reduce((a, k) => (a == null ? a : a[k]), o);

  /* ---------- Tooltip de gráficos y animación de barras ---------- */
  const ctip = document.createElement('div');
  ctip.className = 'ctip'; ctip.hidden = true; document.body.appendChild(ctip);
  document.addEventListener('pointermove', e => {
    const t = e.target.closest && e.target.closest('[data-tip]');
    if (!t) { ctip.hidden = true; return; }
    ctip.innerHTML = t.dataset.tip; ctip.hidden = false;
    const r = ctip.getBoundingClientRect();
    let x = e.clientX + 14, y = e.clientY + 14;
    if (x + r.width > innerWidth - 8) x = e.clientX - r.width - 14;
    if (y + r.height > innerHeight - 8) y = e.clientY - r.height - 14;
    ctip.style.left = x + 'px'; ctip.style.top = y + 'px';
  });
  window.addEventListener('scroll', () => { ctip.hidden = true; }, { passive: true });
  const animar = el => { el.classList.remove('in'); void el.offsetWidth; el.classList.add('in'); };
  const animIO = 'IntersectionObserver' in window && !REDUCE
    ? new IntersectionObserver(es => es.forEach(e => { if (e.isIntersecting) { animIO.unobserve(e.target); animar(e.target); } }), { threshold: .25 }) : null;
  const observarAnim = () => document.querySelectorAll('.anim:not(.obs)').forEach(el => { el.classList.add('obs'); if (animIO) animIO.observe(el); else el.classList.add('in'); });

  /* ---------- Desplazamiento: pasos activos, capítulo y barra de avance ---------- */
  const stories = [];
  const registerStory = (el, onStep) => { const s = { el, steps: [...el.querySelectorAll('.step')], cur: 0, onStep }; s.steps.forEach((st, i) => st.classList.toggle('on', i === 0)); onStep(0); stories.push(s); queueScroll(); return s; };
  const chapLinks = [...document.querySelectorAll('.chap-nav a')], chapNow = $('chap-now'), progEl = $('prog');
  const CHAPS = [['inicio', 'Portada'], ['cap1', 'I · Contexto'], ['cap2', 'II · El agua'], ['cap3', 'III · Validación'], ['cap4', 'IV · Huaicos'],
    ['cap5', 'V · Viviendas'], ['cap6', 'VI · Explorar'], ['cap7', 'VII · Síntesis']].map(([id, l]) => ({ el: $(id), id, l }));
  let lastChap = '', scrollQueued = false;
  function onScroll() {
    scrollQueued = false;
    const vh = window.innerHeight, line = vh * (MOBILE.matches ? .72 : .5);
    stories.forEach(s => {
      const r = s.el.getBoundingClientRect();
      if (r.bottom < -vh || r.top > vh * 2) return;
      let a = 0; s.steps.forEach((st, i) => { if (st.getBoundingClientRect().top < line) a = i; });
      if (a !== s.cur) { s.cur = a; s.steps.forEach((st, i) => st.classList.toggle('on', i === a)); s.onStep(a); }
    });
    const max = document.documentElement.scrollHeight - vh;
    progEl.style.transform = `scaleX(${max > 0 ? Math.min(1, window.scrollY / max) : 0})`;
    let ch = CHAPS[0]; CHAPS.forEach(c => { if (c.el && c.el.getBoundingClientRect().top < vh * .55) ch = c; });
    if (ch.id !== lastChap) { lastChap = ch.id; chapLinks.forEach(a => a.classList.toggle('on', a.dataset.ch === ch.id)); chapNow.textContent = ch.l; }
  }
  function queueScroll() { if (!scrollQueued) { scrollQueued = true; requestAnimationFrame(onScroll); } }
  window.addEventListener('scroll', queueScroll, { passive: true });
  window.addEventListener('resize', queueScroll);

  // Contador animado del escenario
  function counter(el) {
    const b = el.querySelector('b'), sm = el.querySelector('small');
    let cur = null, raf = 0;
    const show = (v, c) => { b.innerHTML = fmt(v, c.d || 0) + (c.u ? `<span class="u">${c.u}</span>` : ''); };
    return c => {
      sm.textContent = c.l; cancelAnimationFrame(raf);
      if (c.s != null) { b.innerHTML = c.s; cur = null; return; }
      if (cur == null || REDUCE) { show(c.v, c); cur = c.v; return; }
      const from = cur, to = c.v, t0 = performance.now();
      const tick = now => { const t = Math.min(1, (now - t0) / 900); show(from + (to - from) * ease(t), c); if (t < 1) raf = requestAnimationFrame(tick); };
      cur = to; raf = requestAnimationFrame(tick);
    };
  }

  /* ---------- Series del radar ---------- */
  let SERIE = null;
  const T0 = { 2017: Date.UTC(2016, 11, 1), 2023: Date.UTC(2022, 11, 1) };
  const diaTemporada = (ev, f) => (Date.parse(f + 'T00:00:00Z') - T0[ev]) / 864e5;
  // Suma por fecha de los distritos pedidos (null si el radar no vio ninguno ese día)
  function totales(ev, ubis) {
    const S = SERIE[ev];
    return S.fechas.map((f, j) => {
      let s = 0, vio = false;
      for (const u of ubis) { const v = (S.distritos[u] || [])[j]; if (v != null) { s += v; vio = true; } }
      return { f, v: vio ? s : null };
    });
  }
  // Máximo semanal: cada pasada del radar ve solo una parte del territorio
  function semanal(ev, ubis) {
    const sem = new Map();
    totales(ev, ubis).forEach(({ f, v }) => {
      if (v == null) return;
      const d = new Date(f + 'T00:00:00Z'), lunes = new Date(d - ((d.getUTCDay() + 6) % 7) * 864e5).toISOString().slice(0, 10);
      const c = sem.get(lunes);
      if (!c || v > c.v) sem.set(lunes, { f, v });
    });
    return [...sem.values()].sort((a, b) => a.f < b.f ? -1 : 1);
  }
  const picoDe = (ev, ubis) => totales(ev, ubis).reduce((m, p) => (p.v != null && (!m || p.v > m.v) ? p : m), null);

  // Gráfico de líneas 2017 frente a 2023 en el eje de la temporada (1 dic -> 30 jun)
  const MES_T = [[0, 'dic'], [31, 'ene'], [62, 'feb'], [90, 'mar'], [121, 'abr'], [151, 'may'], [182, 'jun'], [212, '']];
  function graficoSemanal(el, ubis, etiqueta) {
    const W = 660, H = 260, M = { l: 46, r: 16, t: 18, b: 30 };
    const ser = EVENTOS.map(ev => ({ ev, pts: semanal(ev, ubis) }));
    const ymax = niceMax(Math.max(0.5, ...ser.flatMap(s => s.pts.map(p => p.v))));
    const X = d => M.l + d / 212 * (W - M.l - M.r), Y = v => H - M.b - v / ymax * (H - M.t - M.b);
    let s = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Superficie con agua anómala por semana en ${etiqueta}, 2017 y 2023">`;
    for (let k = 0; k <= 4; k++) { const v = ymax * k / 4, y = Y(v); s += `<line class="c-grid" x1="${M.l}" x2="${W - M.r}" y1="${y}" y2="${y}"/><text class="c-ax" x="${M.l - 8}" y="${y + 4}" text-anchor="end">${fmt(v, v < 10 && v % 1 ? 1 : 0)}</text>`; }
    MES_T.forEach(([d, m], i) => { if (!m) return; const x0 = X(d), x1 = X(MES_T[i + 1][0]); s += `<line class="c-base" x1="${x0}" x2="${x0}" y1="${H - M.b}" y2="${H - M.b + 5}"/><text class="c-ax" x="${(x0 + x1) / 2}" y="${H - 9}" text-anchor="middle">${m}</text>`; });
    s += `<line class="c-base" x1="${M.l}" x2="${W - M.r}" y1="${H - M.b}" y2="${H - M.b}"/>`;
    ser.forEach(({ ev, pts }) => {
      if (!pts.length) return;
      const xy = pts.map(p => [X(diaTemporada(ev, p.f)), Y(p.v)]);
      const lin = xy.map((p, i) => (i ? 'L' : 'M') + p[0].toFixed(1) + ',' + p[1].toFixed(1)).join('');
      s += `<path class="c-a${ev.slice(2)}" d="${lin}L${xy[xy.length - 1][0].toFixed(1)},${H - M.b}L${xy[0][0].toFixed(1)},${H - M.b}Z"/><path class="c-l${ev.slice(2)}" d="${lin}"/>`;
      const top = pts.reduce((m, p) => p.v > m.v ? p : m, pts[0]);
      pts.forEach((p, i) => { s += `<g data-tip="<b>${fecha(p.f)}</b><br>${fmt(p.v, 1)} km² con agua anómala<br><span>máximo de esa semana</span>"><circle class="c-hit" cx="${xy[i][0]}" cy="${xy[i][1]}" r="9"/><circle class="c-dot${ev.slice(2)}" cx="${xy[i][0]}" cy="${xy[i][1]}" r="${p === top ? 4.5 : 2.6}"/></g>`; });
      if (top.v > 0) { const [x, y] = xy[pts.indexOf(top)]; s += `<text class="c-val" x="${Math.min(x, W - M.r - 4)}" y="${Math.max(y - 10, M.t + 10)}" text-anchor="${x > W - 120 ? 'end' : 'middle'}">${fecha(top.f, false)}: ${fmt(top.v, top.v < 10 ? 1 : 0)} km²</text>`; }
    });
    el.innerHTML = s + '</svg>';
  }

  /* ---------- Mapas base ---------- */
  function estilo(fondo, extra = {}) {
    const sources = {
      imagen: { type: 'raster', tiles: [ESRI('World_Imagery')], tileSize: 256, maxzoom: 18, attribution: 'Imágenes © Esri, Maxar, Earthstar Geographics' },
      oscuro: { type: 'raster', tiles: [ESRI('Canvas/World_Dark_Gray_Base')], tileSize: 256, maxzoom: 16, attribution: 'Mapa base © Esri, HERE, Garmin, © colaboradores de OpenStreetMap' },
    };
    const capa = fondo === 'oscuro'
      ? { id: 'fondo', type: 'raster', source: 'oscuro' }
      : { id: 'fondo', type: 'raster', source: 'imagen', paint: { 'raster-brightness-max': .62, 'raster-saturation': -.3, 'raster-contrast': .06 } };
    return { version: 8, sources: { [fondo]: sources[fondo], ...extra }, layers: [{ id: 'noche', type: 'background', paint: { 'background-color': '#10122a' } }, capa], transition: { duration: 650, delay: 0 } };
  }
  function nuevoMapa(el, fondo, opciones = {}) {
    try {
      return new maplibregl.Map({ container: el, style: estilo(fondo, opciones.fuentes), bounds: opciones.bounds || PIURA_B, interactive: !!opciones.interactivo,
        attributionControl: { compact: true }, fadeDuration: 0, maxPitch: 75, cooperativeGestures: !!opciones.interactivo, dragRotate: !!opciones.interactivo, ...opciones.mapa });
    } catch (e) {
      el.innerHTML = '<div class="gl-msg">Este navegador no puede mostrar mapas WebGL. El texto y los cuadros siguen disponibles.</div>';
      return null;
    }
  }
  const PROP = { raster: ['raster-opacity'], fill: ['fill-opacity'], line: ['line-opacity'], circle: ['circle-opacity', 'circle-stroke-opacity'], 'fill-extrusion': ['fill-extrusion-opacity'] };
  // Capas que siguen a otra con su misma opacidad (por un factor): los halos y el contorno de Piura sobre las provincias
  const COMPANERAS = { 'prov-l': [['prov-c', .55], ['dep-c', .7], ['dep-l', 1]], 'peru-l': [['peru-c', .45]] };
  // Opacidad de cada capa del paso; las que no figuran se apagan
  function aplicarCapas(map, ids, capas) {
    ids.forEach(id => {
      const o = capas[id] || 0;
      [[id, 1], ...(COMPANERAS[id] || [])].forEach(([cid, k]) => {
        const l = map.getLayer(cid); if (!l) return;
        PROP[l.type].forEach(p => map.setPaintProperty(cid, p, o * k));
        map.setLayoutProperty(cid, 'visibility', o > 0 ? 'visible' : 'none');
      });
    });
  }
  // Provincias y, encima, el contorno del departamento, cada una con su halo (fuentes 'prov' y 'dep')
  function capasLimites(map, opac = 0) {
    const union = { 'line-join': 'round', 'line-cap': 'round' };
    map.addLayer({ id: 'prov-c', type: 'line', source: 'prov', layout: union, paint: { 'line-color': HALO, 'line-width': 3.4, 'line-blur': 1, 'line-opacity': opac * .55 } });
    map.addLayer({ id: 'prov-l', type: 'line', source: 'prov', layout: union, paint: { 'line-color': '#e3e5f4', 'line-width': 1.15, 'line-opacity': opac } });
    map.addLayer({ id: 'dep-c', type: 'line', source: 'dep', layout: union, paint: { 'line-color': HALO, 'line-width': ['interpolate', ['linear'], ['zoom'], 5, 4.5, 9, 7], 'line-blur': 1.5, 'line-opacity': opac * .7 } });
    map.addLayer({ id: 'dep-l', type: 'line', source: 'dep', layout: union, paint: { 'line-color': '#ffffff', 'line-width': ['interpolate', ['linear'], ['zoom'], 5, 1.8, 9, 2.8], 'line-opacity': opac } });
  }
  function margenEscenario(map) {
    const st = map.getContainer().closest('.stage'), fr = st.querySelector('.frame').getBoundingClientRect(), r = st.getBoundingClientRect();
    return { top: Math.max(20, fr.top - r.top + 86), left: Math.max(20, fr.left - r.left), right: Math.max(20, r.right - fr.right), bottom: Math.max(20, r.bottom - fr.bottom + 40) };
  }
  function irA(map, b, { pitch = 0, bearing = 0, dz = 0 } = {}) {
    const cam = map.cameraForBounds([[b[0], b[1]], [b[2], b[3]]], { padding: margenEscenario(map) });
    if (!cam) return;
    map.flyTo({ center: cam.center, zoom: cam.zoom + dz, pitch, bearing, duration: REDUCE ? 0 : 2000, essential: true });
  }
  function rotulo(map, html, lngLat, cls) {
    const el = document.createElement('div'); el.className = 'lbl ' + cls; el.innerHTML = html;
    return new maplibregl.Marker({ element: el, anchor: cls === 'ev' ? 'left' : 'center', offset: cls === 'ev' ? [13, 0] : [0, 0] }).setLngLat(lngLat).addTo(map);
  }
  const mostrar = (marcas, si) => marcas.forEach(m => { m.getElement().style.display = si ? '' : 'none'; });
  const bboxDe = feats => {
    const b = [180, 90, -180, -90];
    const rec = c => { if (typeof c[0] === 'number') { b[0] = Math.min(b[0], c[0]); b[1] = Math.min(b[1], c[1]); b[2] = Math.max(b[2], c[0]); b[3] = Math.max(b[3], c[1]); } else c.forEach(rec); };
    feats.forEach(f => rec(f.geometry.coordinates));
    return b;
  };
  const leyendaAgua = (titulo) => `<b>${titulo}</b><span><i class="ramp" style="background:linear-gradient(90deg,${W1},${W2},${W3},${W4})"></i>de 2 a 16 fechas o más</span>`;

  /* ---------- Arranque ---------- */
  Promise.all(['data/resumen.json', 'data/distritos.geojson', 'data/provincias.geojson', 'data/peru.geojson', 'data/serie.json', 'data/indeci.json',
    'data/agua.json', 'data/huaicos_ingemmet.geojson', 'data/huaicos_eventos.geojson', 'data/ems_2017.geojson'].map(get))
    .then(([R, DIST, PROV, PERU, serie, INDECI, AGUA, FLUJOS, EVENTOS_H, EMS]) => {
      SERIE = serie;
      // Contorno de Piura: sale de los mismos distritos que las provincias, así que calza con ellas
      const DEP = { type: 'FeatureCollection', features: PERU.features.filter(f => f.properties.CCDD === '20') };
      const D = { R, DIST, PROV, PERU, DEP, INDECI, AGUA, FLUJOS, EVENTOS_H, EMS };
      ligarCifras(R);
      const pasos = [lamina, historiaA, notasI, historiaB, notasII, historiaC, explorador, sintesis, pasadas];
      pasos.forEach(f => { try { f(D); } catch (e) { console.error(f.name, e); } });
      observarAnim(); queueScroll();
    })
    .catch(e => { console.error(e); document.querySelectorAll('.stage .gl, #mapa-x').forEach(el => { el.innerHTML = '<div class="gl-msg">No se pudieron cargar los datos.</div>'; }); });

  // Cifras del texto: <span data-v="eventos.2017.inund_anom_km2" data-d="0">, data-f="fecha" para fechas
  function ligarCifras(R) {
    document.querySelectorAll('[data-v]').forEach(el => {
      const v = dig(R, el.dataset.v); if (v == null) return;
      el.textContent = el.dataset.f === 'fecha' ? fecha(v, el.dataset.a !== '0') : fmt(+v, +(el.dataset.d || 0));
    });
  }

  /* ---------- Ficha técnica: fechas en que el radar vio Piura ---------- */
  function pasadas(D) {
    const el = $('pasadas'); if (!el) return;
    const ubis = D.DIST.features.map(f => f.properties.UBIGEO);
    // El ancho del dibujo es el de su caja, así el texto queda a tamaño real; en el celular, margen izquierdo más angosto
    const W = Math.max(300, Math.round(el.clientWidth)), FILA = 82, M = { l: W < 500 ? 62 : 96, r: 12, t: 8, b: 24 }, H = M.t + FILA * EVENTOS.length + M.b;
    const X = d => M.l + d / 212 * (W - M.l - M.r);
    let s = `<svg viewBox="0 0 ${W} ${H}" width="${W}" height="${H}">`;
    MES_T.forEach(([d, m], i) => {
      const x = X(d); s += `<line class="p-mes" x1="${x}" x2="${x}" y1="${M.t}" y2="${H - M.b}"/>`;
      if (m) s += `<text class="p-ax" x="${(x + X(MES_T[i + 1][0])) / 2}" y="${H - 7}" text-anchor="middle">${m}</text>`;
    });
    let k = 0;
    EVENTOS.forEach((ev, fila) => {
      const y0 = M.t + fila * FILA, base = y0 + FILA - 14, alto = FILA - 34, col = ev === '2017' ? E17N : E23N;
      const tot = totales(ev, ubis), obs = SERIE[ev].observado_pct;
      s += `<text class="p-ev" x="0" y="${y0 + 30}" fill="${col}">${ev}</text><text class="p-n" x="0" y="${y0 + 48}">${tot.length} fechas</text>`;
      s += `<line class="p-base" x1="${M.l}" x2="${W - M.r}" y1="${base}" y2="${base}"/>`;
      tot.forEach(({ f, v }, i) => {
        const x = X(diaTemporada(ev, f)).toFixed(1), h = Math.max(3, alto * obs[i] / 100);
        const tip = `<b>${fecha(f)}</b><br>Cubrió el ${fmt(obs[i])} % de Piura` + (v != null ? ` · ${fmt(v, 1)} km² de agua anómala` : '');
        s += `<line class="p-t" x1="${x}" x2="${x}" y1="${base}" y2="${(base - h).toFixed(1)}" stroke="${col}" stroke-opacity="${obs[i] >= 90 ? 1 : .45}" style="--i:${k++}"/>`;
        s += `<rect class="p-hit" x="${x - 4}" y="${base - alto - 6}" width="8" height="${alto + 8}" data-tip="${tip.replace(/"/g, '&quot;')}"/>`;
      });
      const pico = picoDe(ev, ubis);
      if (pico) {
        const x = X(diaTemporada(ev, pico.f)), der = x > W - 150;
        s += `<circle cx="${x}" cy="${base - alto - 8}" r="3.5" fill="#fff"/><text class="p-pico" x="${der ? x - 8 : x + 8}" y="${base - alto - 4}" text-anchor="${der ? 'end' : 'start'}">Pico: ${fecha(pico.f, false)} · ${fmt(pico.v)} km²</text>`;
      }
    });
    el.innerHTML = s + '</svg>';
    if (!el.dataset.oye) {
      el.dataset.oye = '1'; let w = el.clientWidth, t;
      window.addEventListener('resize', () => { clearTimeout(t); t = setTimeout(() => { if (Math.abs(el.clientWidth - w) > 40) { w = el.clientWidth; pasadas(D); } }, 250); });
    }
  }

  /* ---------- Lámina de portada (SVG en Mercator) ---------- */
  function lamina(D) {
    const svg = $('lamina'), loc = $('localizador'); if (!svg) return;
    const merc = ([lon, lat]) => [(lon + 180) / 360, (1 - Math.log(Math.tan(Math.PI / 4 + lat * Math.PI / 360)) / Math.PI) / 2];
    // Caja de la lámina: la misma de scripts/lamina_base.py, que recorta la imagen de fondo
    // Con margen de mar al oeste: ahí van el mapa de ubicación (abajo) y la escala (arriba), sin tapar Piura
    const B = [-82.25, -6.50, -79.05, -3.96], p0 = merc([B[0], B[3]]), p1 = merc([B[2], B[1]]);
    const VW = 600, VH = Math.round(VW * (p1[1] - p0[1]) / (p1[0] - p0[0]));
    const P = c => { const m = merc(c); return [(m[0] - p0[0]) / (p1[0] - p0[0]) * VW, (m[1] - p0[1]) / (p1[1] - p0[1]) * VH]; };
    const ruta = (geom, f = P) => (geom.type === 'Polygon' ? [geom.coordinates] : geom.coordinates).map(pol => pol.map(r => 'M' + r.map(c => f(c).map(v => v.toFixed(1)).join(',')).join('L') + 'Z').join('')).join('');
    const [ax, ay] = P(D.AGUA.esquinas[0]), [bx, by] = P(D.AGUA.esquinas[2]);
    // Fondo: Sentinel-2 sin nubes de 2016 (EOX), recortado a esta misma caja por scripts/lamina_base.py
    let s = `<defs><filter id="engrosar"><feMorphology operator="dilate" radius="1.1"/></filter></defs>`;
    s += `<image href="data/lamina.jpg" x="0" y="0" width="${VW}" height="${VH}" preserveAspectRatio="none"/>`;
    // Penumbra fuera de Piura, para que el departamento resalte sobre la imagen
    const piura = D.DEP.features.map(f => ruta(f.geometry)).join('');
    s += `<path d="M0 0H${VW}V${VH}H0Z${piura}" fill="rgba(7, 8, 22, .58)" fill-rule="evenodd"/>`;
    // Cuadrícula cada 0,5° (como la cuadrícula UTM de la lámina de Chichas)
    [-6, -5.5, -5, -4.5, -4].forEach(lat => { const y = P([B[0], lat])[1].toFixed(1); s += `<line x1="0" x2="${VW}" y1="${y}" y2="${y}" stroke="rgba(255, 255, 255, .13)" stroke-width=".7"/>`; });
    [-82, -81.5, -81, -80.5, -80, -79.5].forEach(lon => { const x = P([lon, B[1]])[0].toFixed(1); s += `<line x1="${x}" x2="${x}" y1="0" y2="${VH}" stroke="rgba(255, 255, 255, .13)" stroke-width=".7"/>`; });
    s += D.PERU.features.filter(f => f.properties.CCDD !== '20').map(f => `<path d="${ruta(f.geometry)}" fill="none" stroke="rgba(227, 229, 244, .38)" stroke-width=".7" stroke-linejoin="round"/>`).join('');
    s += `<image id="lamina-agua" href="data/agua_2017_calido.png" x="${ax}" y="${ay}" width="${bx - ax}" height="${by - ay}" preserveAspectRatio="none" filter="url(#engrosar)"/>`;
    s += D.PROV.features.map(f => `<path d="${ruta(f.geometry)}" fill="none" stroke="rgba(227, 229, 244,.6)" stroke-width=".9" stroke-linejoin="round"/>`).join('');
    s += D.DEP.features.map(f => { const d = ruta(f.geometry); return `<path d="${d}" fill="none" stroke="${HALO}" stroke-opacity=".8" stroke-width="4.4" stroke-linejoin="round"/><path d="${d}" fill="none" stroke="#fff" stroke-width="1.9" stroke-linejoin="round"/>`; }).join('');
    CIUDADES.forEach(([n, lon, lat]) => { const [x, y] = P([lon, lat]), izq = x > VW - 95; s += `<circle cx="${x}" cy="${y}" r="3" fill="#fff" stroke="#10122a" stroke-width="1.5"/><text x="${izq ? x - 6 : x + 6}" y="${y - 5}" text-anchor="${izq ? 'end' : 'start'}" font-size="12" font-weight="600" fill="#fff" stroke="#0a0c1b" stroke-width="3" paint-order="stroke">${n}</text>`; });
    [-6, -5.5, -5, -4.5].forEach(lat => { const y = P([B[0], lat])[1]; s += `<line x1="0" x2="6" y1="${y}" y2="${y}" stroke="#9ca1c4"/><text x="9" y="${y + 3.5}" font-size="9.5" fill="#9ca1c4" font-family="IBM Plex Mono, monospace">${fmt(-lat, 1)}° S</text>`; });
    [-81, -80.5, -80, -79.5].forEach(lon => { const x = P([lon, B[1]])[0]; s += `<line x1="${x}" x2="${x}" y1="${VH}" y2="${VH - 6}" stroke="#9ca1c4"/><text x="${x}" y="${VH - 9}" font-size="9.5" fill="#9ca1c4" text-anchor="middle" font-family="IBM Plex Mono, monospace">${fmt(-lon, 1)}° O</text>`; });
    // Escala de 50 km a la latitud media, arriba a la izquierda sobre el mar
    const km = 50, x0 = 60, yb = 44, dx = P([B[0] + km / (111.32 * Math.cos(5.2 * Math.PI / 180)), -5.2])[0] - P([B[0], -5.2])[0];
    s += `<rect x="${x0 - 8}" y="${yb - 20}" width="${dx + 50}" height="30" fill="rgba(7, 8, 22, .78)"/><rect x="${x0}" y="${yb}" width="${dx / 2}" height="5" fill="#fff"/><rect x="${x0 + dx / 2}" y="${yb}" width="${dx / 2}" height="5" fill="none" stroke="#fff"/>`;
    s += `<text x="${x0}" y="${yb - 5}" font-size="10" fill="#fff" text-anchor="middle" font-family="IBM Plex Mono, monospace">0</text><text x="${x0 + dx / 2}" y="${yb - 5}" font-size="10" fill="#fff" text-anchor="middle" font-family="IBM Plex Mono, monospace">25</text><text x="${x0 + dx + 6}" y="${yb - 5}" font-size="10" fill="#fff" font-family="IBM Plex Mono, monospace">50 km</text>`;
    svg.setAttribute('viewBox', `0 0 ${VW} ${VH}`); svg.innerHTML = s;

    // Ubicación en el Perú
    const todo = bboxDe(D.PERU.features), q0 = merc([todo[0], todo[3]]), q1 = merc([todo[2], todo[1]]);
    const LW = 120, LH = Math.round(LW * (q1[1] - q0[1]) / (q1[0] - q0[0]));
    const Q = c => { const m = merc(c); return [(m[0] - q0[0]) / (q1[0] - q0[0]) * (LW - 8) + 4, (m[1] - q0[1]) / (q1[1] - q0[1]) * (LH - 8) + 4]; };
    loc.setAttribute('viewBox', `0 0 ${LW} ${LH}`);
    loc.innerHTML = D.PERU.features.map(f => `<path d="${ruta(f.geometry, Q)}" fill="${f.properties.CCDD === '20' ? '#ff7a2f' : '#25284a'}" stroke="#10122a" stroke-width=".5"/>`).join('');

    document.querySelectorAll('#lamina-ev button').forEach(b => b.addEventListener('click', () => {
      document.querySelectorAll('#lamina-ev button').forEach(x => x.setAttribute('aria-pressed', String(x === b)));
      $('lamina-agua').setAttribute('href', `data/agua_${b.dataset.v}_calido.png`);
      $('lamina-cap-ev').textContent = b.dataset.v === '2017' ? 'diciembre de 2016 a mayo de 2017' : 'enero a junio de 2023';
    }));
  }

  /* ---------- Capítulos I y II: contexto y agua ---------- */
  function historiaA(D) {
    const root = $('stA'); const map = nuevoMapa(root.querySelector('.gl'), 'imagen', { bounds: NORTE_B, fuentes: {
      peru: { type: 'geojson', data: D.PERU }, prov: { type: 'geojson', data: D.PROV }, dep: { type: 'geojson', data: D.DEP }, ems: { type: 'geojson', data: D.EMS },
      a2017: { type: 'image', url: 'data/agua_2017.png', coordinates: D.AGUA.esquinas }, a2023: { type: 'image', url: 'data/agua_2023.png', coordinates: D.AGUA.esquinas },
      a2022: { type: 'image', url: 'data/agua_2022.png', coordinates: D.AGUA.esquinas } } });
    const cnt = counter(root.querySelector('.counter')), leg = root.querySelector('.legend'), tl = root.querySelector('.tl');
    const R = D.R, E = R.eventos;
    const sechura = D.DIST.features.find(f => f.properties.NOMBDIST === 'SECHURA');
    const sechuraKm = sechura ? sechura.properties.inund_anom_km2_2017 : 0;
    const dam = ev => (D.INDECI.find(r => String(r.evento) === ev) || {}).damnificados || 0;
    const mb = (filas, max) => '<div class="mbars">' + filas.map(([l, v, c, t]) => `<div class="mb"><span>${l}</span><span class="t"><i style="width:${(v / max * 100).toFixed(1)}%;background:${c}"></i></span><span class="v">${t}</span></div>`).join('') + '</div>';
    const indeci = $('stA-indeci');
    if (indeci) {
      const f = k => EVENTOS.map(ev => (D.INDECI.find(r => String(r.evento) === ev) || {})[k] || 0);
      const [d17, d23] = f('damnificados'), [v17, v23] = f('viviendas_destruidas');
      indeci.innerHTML = mb([['Damnificados 2017', d17, E17N, fmt(d17)], ['Damnificados 2023', d23, E23N, fmt(d23)]], Math.max(d17, d23)) +
        mb([['Viv. destruidas 2017', v17, E17N, fmt(v17)], ['Viv. destruidas 2023', v23, E23N, fmt(v23)]], Math.max(v17, v23));
    }
    const IDS = ['peru-f', 'peru-l', 'prov-l', 'a2022', 'a2017', 'a2023', 'ems-f', 'ems-l'];
    const PASOS = [
      { b: NORTE_B, capas: { 'peru-f': .55, 'peru-l': .7, 'prov-l': .9 }, c: { v: R.area_km2, u: 'km²', l: `Departamento de Piura · ${R.distritos} distritos` }, rot: 'prov' },
      { b: CIUDAD_B, capas: { 'prov-l': .6, 'ems-f': .5, 'ems-l': .9 }, c: { v: 3800, u: 'm³/s', l: 'Caudal máximo del río Piura, 27 mar 2017' }, rot: 'ciudad',
        ley: `<b>Copernicus EMS, mar–abr 2017</b><span><i style="background:rgba(255,255,255,.55);border:1px solid #fff"></i>Inundación delimitada a mano</span>` },
      { b: PIURA_B, capas: { 'prov-l': .9 }, c: { s: '16 mar 2023', l: 'ENFEN declara la alerta de Niño Costero (ciclón Yaku)' }, rot: 'ciudad' },
      { b: PIURA_B, capas: { 'prov-l': .9 }, c: { v: dam('2017'), l: 'damnificados en Piura en 2017 según INDECI' }, rot: 'prov' },
      { b: PIURA_B, capas: { 'prov-l': .9, a2022: .95 }, c: { v: E['2022'].agua_habitual_km2, u: 'km²', l: 'con agua habitual en ene–jun 2022, un año sin Niño' }, rot: 'prov',
        ley: `<b>Agua habitual (referencia)</b><span><i style="background:#e2e8ec"></i>Con agua en 2 o más fechas de 2022</span>` },
      { b: PIURA_B, capas: { 'prov-l': .9, a2017: 1 }, c: { v: E['2017'].inund_anom_km2, u: 'km²', l: 'con agua anómala, dic 2016 – may 2017' }, rot: 'ciudad', tl: '2017', ley: leyendaAgua('Fechas con agua, 2017') },
      { b: sechura ? bboxDe([sechura]) : PIURA_B, capas: { 'prov-l': .9, a2017: 1 }, c: { v: sechuraKm, u: 'km²', l: 'con agua anómala en el distrito de Sechura, 2017' }, rot: 'ciudad', tl: '2017', ley: leyendaAgua('Fechas con agua, 2017') },
      { b: PIURA_B, capas: { 'prov-l': .9, a2023: 1 }, c: { v: E['2023'].inund_anom_km2, u: 'km²', l: 'con agua anómala, ene – jun 2023' }, rot: 'ciudad', tl: '2023', ley: leyendaAgua('Fechas con agua, 2023') },
    ];
    let marcas = { prov: [], ciudad: [] }, listo = false, pendiente = 0;
    // Mini serie del máximo semanal de todo Piura, con la fecha del paso
    const todos = D.DIST.features.map(f => f.properties.UBIGEO);
    function linea(ev) {
      const W = 316, H = 86, pts = semanal(ev, todos), otros = semanal(ev === '2017' ? '2023' : '2017', todos);
      const ymax = niceMax(Math.max(...pts.map(p => p.v), ...otros.map(p => p.v)));
      const X = d => 4 + d / 212 * (W - 8), Y = v => H - 14 - v / ymax * (H - 24);
      const path = (e, ps) => ps.map((p, i) => (i ? 'L' : 'M') + X(diaTemporada(e, p.f)).toFixed(1) + ',' + Y(p.v).toFixed(1)).join('');
      const otro = ev === '2017' ? '2023' : '2017', top = pts.reduce((m, p) => p.v > m.v ? p : m, pts[0]);
      let s = `<svg viewBox="0 0 ${W} ${H}"><line x1="4" x2="${W - 4}" y1="${H - 14}" y2="${H - 14}" stroke="#2a2e52"/>`;
      MES_T.forEach(([d, m]) => { if (m) s += `<text x="${X(d + 15)}" y="${H - 2}" font-size="9" fill="#9ca1c4" text-anchor="middle">${m}</text>`; });
      s += `<path d="${path(otro, otros)}" fill="none" stroke="${otro === '2017' ? E17N : E23N}" stroke-opacity=".35" stroke-width="1.5"/>`;
      s += `<path d="${path(ev, pts)}" fill="none" stroke="${ev === '2017' ? E17N : E23N}" stroke-width="2.2"/>`;
      s += `<circle cx="${X(diaTemporada(ev, top.f))}" cy="${Y(top.v)}" r="3.5" fill="#fff"/><text x="${Math.min(X(diaTemporada(ev, top.f)) + 6, W - 70)}" y="${Math.max(Y(top.v) - 4, 10)}" font-size="10" fill="#fff">${fecha(top.f, false)} · ${fmt(top.v)} km²</text>`;
      return `<div class="tl-h">Máximo semanal en Piura · <span style="color:${ev === '2017' ? E17N : E23N}">${ev}</span> frente a ${otro}</div>` + s + '</svg>';
    }
    function paso(i) {
      const p = PASOS[i]; if (!p) return;
      cnt(p.c); leg.innerHTML = p.ley || '';
      if (p.tl) { tl.hidden = false; tl.innerHTML = linea(p.tl); } else tl.hidden = true;
      if (!map) return;
      if (!listo) { pendiente = i; return; }
      aplicarCapas(map, IDS, p.capas); mostrar(marcas.prov, p.rot === 'prov'); mostrar(marcas.ciudad, p.rot === 'ciudad');
      irA(map, p.b);
    }
    if (map) map.on('load', () => {
      map.addLayer({ id: 'peru-f', type: 'fill', source: 'peru', paint: { 'fill-color': ['case', ['==', ['get', 'CCDD'], '20'], W2, '#10122a'], 'fill-opacity': 0 } });
      map.addLayer({ id: 'peru-c', type: 'line', source: 'peru', layout: { 'line-join': 'round' }, paint: { 'line-color': HALO, 'line-width': 2.6, 'line-blur': 1, 'line-opacity': 0 } });
      map.addLayer({ id: 'peru-l', type: 'line', source: 'peru', layout: { 'line-join': 'round' }, paint: { 'line-color': '#e3e5f4', 'line-width': .8, 'line-opacity': 0 } });
      ['a2022', 'a2017', 'a2023'].forEach(id => map.addLayer({ id, type: 'raster', source: id, paint: { 'raster-opacity': 0, 'raster-resampling': 'nearest' } }));
      map.addLayer({ id: 'ems-f', type: 'fill', source: 'ems', filter: ['==', ['get', 'tipo'], 'inundacion'], paint: { 'fill-color': '#ffffff', 'fill-opacity': 0 } });
      map.addLayer({ id: 'ems-l', type: 'line', source: 'ems', filter: ['==', ['get', 'tipo'], 'inundacion'], paint: { 'line-color': '#ffffff', 'line-width': .8, 'line-opacity': 0 } });
      capasLimites(map);
      marcas.prov = D.PROV.features.map(f => rotulo(map, nombre(f.properties.NOMBPROV), [f.properties.lab_x, f.properties.lab_y], 'prov'));
      marcas.ciudad = CIUDADES.map(([n, lon, lat]) => rotulo(map, n, [lon, lat], 'city'));
      listo = true; paso(pendiente);
    });
    registerStory($('stA-sec'), paso);
  }

  /* ---------- Notas I: daños oficiales y agua semana a semana ---------- */
  function notasI(D) {
    const R = D.R;
    // Cuadro 1: INDECI 2017 frente a 2023
    const fila = ev => D.INDECI.find(r => String(r.evento) === ev) || {};
    const a = fila('2017'), b = fila('2023');
    const IND = [['damnificados', 'Damnificados', 'personas'], ['afectados', 'Afectados', 'personas'], ['fallecidos', 'Fallecidos', 'personas'],
      ['viviendas_destruidas', 'Viviendas destruidas', 'viviendas'], ['viviendas_afectadas', 'Viviendas afectadas', 'viviendas'],
      ['cultivo_perdido_ha', 'Cultivos perdidos', 'ha'], ['cultivo_afectado_ha', 'Cultivos afectados', 'ha']];
    $('t-indeci').querySelector('tbody').innerHTML = IND.map(([k, l, u], i) => {
      const x = a[k], y = b[k], r = x && y != null ? y / x * 100 : null;
      return `<tr><td><b>${l}</b><span class="sub">${u}</span></td><td class="n">${x != null ? fmt(x) : '—'}</td><td class="n">${y != null ? fmt(y) : '—'}</td>` +
        `<td>${r != null ? `<div class="db"><span class="tr"><i class="gx" style="width:${Math.min(100, r).toFixed(1)}%;background:var(--e23);--i:${i}"></i></span><span class="v">${fmt(r, 0)} %</span></div>` : '—'}</td></tr>`;
    }).join('');
    // Gráfico 1: máximo semanal en todo Piura
    graficoSemanal($('g-semanal'), D.DIST.features.map(f => f.properties.UBIGEO), 'Piura');
    // Gráfico 2: provincias, 2017 frente a 2023
    const pp = {};
    R.por_provincia.forEach(r => { (pp[r.NOMBPROV] = pp[r.NOMBPROV] || {})[r.evento] = r.inund_anom_km2; });
    const orden = Object.entries(pp).sort((x, y) => ((y[1]['2017'] || 0) + (y[1]['2023'] || 0)) - ((x[1]['2017'] || 0) + (x[1]['2023'] || 0)));
    const max = Math.max(...orden.flatMap(([, v]) => EVENTOS.map(e => v[e] || 0)));
    $('g-prov').innerHTML = orden.map(([p, v], i) => `<div class="stk"><div class="stk-l"><b>${nombre(p)}</b></div><div class="pair">` +
      EVENTOS.map(e => `<div class="db" data-tip="<b>${nombre(p)}, ${e}</b><br>${fmt(v[e] || 0, 1)} km² con agua anómala"><span class="tr"><i class="gx e${e.slice(2)}" style="width:${((v[e] || 0) / max * 100).toFixed(1)}%;--i:${i}"></i></span><span class="v">${fmt(v[e] || 0, (v[e] || 0) < 10 ? 1 : 0)}</span></div>`).join('') +
      `</div><div></div></div>`).join('');
    // Cuadro 2: distritos con más agua
    function top(ev) {
      const filas = R.top_distritos[ev], mx = filas[0] ? filas[0].inund_anom_km2 : 1;
      $('t-top').querySelector('tbody').innerHTML = filas.map((r, i) => `<tr><td class="n">${i + 1}</td><td><b>${nombre(r.NOMBDIST)}</b><span class="sub">${nombre(r.NOMBPROV)}</span></td>` +
        `<td><div class="db"><span class="tr"><i class="gx" style="width:${(r.inund_anom_km2 / mx * 100).toFixed(1)}%;background:var(--e${ev.slice(2)});--i:${i}"></i></span><span class="v">${fmt(r.inund_anom_km2, 1)}</span></div></td>` +
        `<td class="n">${r.fecha_max ? fecha(r.fecha_max, false) : '—'}</td><td class="n">${fmt(r.agua_habitual_km2, 1)}</td></tr>`).join('');
      animar($('f-top'));
    }
    document.querySelectorAll('#top-ev button').forEach(btn => btn.addEventListener('click', () => {
      document.querySelectorAll('#top-ev button').forEach(x => x.setAttribute('aria-pressed', String(x === btn))); top(btn.dataset.v);
    }));
    top('2017');
  }

  /* ---------- Capítulos III y IV: validación y huaicos ---------- */
  const AOI = { '10PIURA': 'Bajo Piura', '11PARACHIQUE': 'Parachique (Sechura)', '14SALINAS': 'Salinas (Sechura)', '12PIURANORTH': 'Piura norte', '19LOSEJIDOS': 'Los Ejidos',
    '15PIURAEAST': 'Ciudad de Piura, este', '16PIURAWEST': 'Ciudad de Piura, oeste', '08SULLANA': 'Sullana' };
  function historiaB(D) {
    const root = $('stB'); const map = nuevoMapa(root.querySelector('.gl'), 'imagen', { fuentes: {
      ems: { type: 'geojson', data: D.EMS }, prov: { type: 'geojson', data: D.PROV }, dep: { type: 'geojson', data: D.DEP },
      a2017: { type: 'image', url: 'data/agua_2017.png', coordinates: D.AGUA.esquinas },
      flujos: { type: 'geojson', data: D.FLUJOS }, eventos: { type: 'geojson', data: D.EVENTOS_H },
      dem: { type: 'raster-dem', tiles: ['https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png'], encoding: 'terrarium', tileSize: 256, maxzoom: 13,
        attribution: 'Relieve: Terrain Tiles (Mapzen, AWS Open Data)' } } });
    const cnt = counter(root.querySelector('.counter')), leg = root.querySelector('.legend');
    const R = D.R, V = R.validacion, H = R.huaicos, Ed = R.edificios;
    const val = n => (V.find(r => r.aoi === n) || {}).deteccion_2fechas_pct || 0;
    const emsKm = R.ems_inundado_km2;
    const aoi10 = D.EMS.features.filter(f => f.properties.aoi === '10PIURA' && f.properties.tipo === 'aoi');
    const ev = e => D.EVENTOS_H.features.filter(f => f.properties.evento === e);
    const canchaque = D.EVENTOS_H.features.find(f => f.properties.distrito === 'CANCHAQUE');
    const cc = canchaque ? canchaque.geometry.coordinates : [-79.60, -5.37];
    const mb = (filas, max) => '<div class="mbars">' + filas.map(([l, v, c, t]) => `<div class="mb"><span>${l}</span><span class="t"><i style="width:${(v / max * 100).toFixed(1)}%;background:${c}"></i></span><span class="v">${t}</span></div>`).join('') + '</div>';
    const det = $('stB-det');
    if (det) det.innerHTML = mb(V.filter(r => r.ems_inundado_km2 >= 1).map(r => [AOI[r.aoi] || r.aoi, r.deteccion_2fechas_pct, W2, fmt(r.deteccion_2fechas_pct, 0) + ' %']), 100);
    const porProv = {};
    H.por_provincia_tipo.forEach(r => { if (r.tipo === 'Flujo de detritos' || r.tipo === 'Flujo de lodo') porProv[r.provincia] = (porProv[r.provincia] || 0) + r.n; });
    const provOrden = Object.entries(porProv).sort((a, b) => b[1] - a[1]);
    const hp = $('stB-prov');
    if (hp) hp.innerHTML = mb(provOrden.map(([p, n]) => [nombre(p), n, HU, fmt(n)]), provOrden[0][1]);
    const vistos = H.con_agua_radar['2017'];
    const leyH = `<b>Inventario de INGEMMET</b><span><i class="dot" style="background:${HU}"></i>Flujo de detritos o de lodo (huaico)</span><span><i class="dot" style="background:${HU2}"></i>Avalancha o flujo de tierra</span>`;
    const leyE = `<b>Huaicos documentados</b><span><i class="dot" style="background:${E17N};box-shadow:0 0 0 2px #fff"></i>2017</span><span><i class="dot" style="background:${E23N};box-shadow:0 0 0 2px #fff"></i>2023</span>`;
    const leyEms = `<b>Inundación 2017</b><span><i style="background:rgba(255,255,255,.55);border:1px solid #fff"></i>Copernicus EMS (a mano)</span><span><i class="line" style="background:#a8c2ff"></i>Área mapeada (AOI)</span>`;
    const leyV = leyEms + `<span><i style="background:${W2}"></i>Radar GFM (agua anómala)</span>`;
    const IDS = ['prov-l', 'ems-f', 'ems-l', 'aoi-l', 'a2017', 'flujos', 'eventos'];
    const PASOS = [
      { b: aoi10.length ? bboxDe(aoi10) : PIURA_B, capas: { 'ems-f': .5, 'ems-l': .9, 'aoi-l': .8 }, c: { v: emsKm, u: 'km²', l: 'de inundación delimitados por Copernicus EMS en Piura, 2017' }, ley: leyEms },
      { b: aoi10.length ? bboxDe(aoi10) : PIURA_B, capas: { 'ems-f': .45, 'ems-l': .9, 'aoi-l': .8, a2017: 1 }, c: { v: val('10PIURA'), u: '%', l: 'de la inundación del Bajo Piura que también vio el radar' }, ley: leyV },
      { b: CIUDAD_B, capas: { 'ems-f': .45, 'ems-l': .9, a2017: 1 }, c: { s: `${fmt(Ed.gfm2017)} <span class="u">de ${fmt(Ed.afectado_2017)}</span>`, l: 'edificios en zona afectada que el radar marcó con agua' }, ley: leyV },
      { b: PIURA_B, capas: { 'prov-l': .8, flujos: .95 }, c: { v: H.huaicos, l: 'huaicos inventariados por INGEMMET en Piura' }, ley: leyH, rot: 'prov' },
      { b: PIURA_B, capas: { 'prov-l': .8, flujos: .95 }, c: { v: provOrden.slice(0, 3).reduce((s, x) => s + x[1], 0), l: `en ${provOrden.slice(0, 3).map(x => nombre(x[0])).join(', ')}` }, ley: leyH, rot: 'prov' },
      { b: bboxDe(ev('2017')), capas: { 'prov-l': .8, flujos: .5, eventos: 1 }, c: { v: ev('2017').length, l: 'huaicos y quebradas activadas documentados en 2017' }, ley: leyE, rot: '2017', dz: -.4 },
      { b: [cc[0] - .07, cc[1] - .06, cc[0] + .07, cc[1] + .06], capas: { flujos: .9, eventos: 1 }, c: { s: '15 mar · 5 abr', l: 'la quebrada El Limón baja dos veces sobre Canchaque, 2023' }, ley: leyE, rot: '2023', pitch: 62, bearing: -35, terreno: true },
      { b: PIURA_B, capas: { 'prov-l': .8, flujos: .95, a2017: 1 }, c: { s: `${fmt(vistos.puntos)} <span class="u">de ${fmt(vistos.de)}</span>`, l: 'puntos de huaico con agua del radar a menos de 160 m en 2017' }, ley: leyH + `<span><i style="background:${W2}"></i>Radar GFM 2017</span>`, rot: 'prov' },
    ];
    let marcas = { prov: [], '2017': [], '2023': [] }, listo = false, pendiente = 0;
    function paso(i) {
      const p = PASOS[i]; if (!p) return;
      cnt(p.c); leg.innerHTML = p.ley || '';
      if (!map) return;
      if (!listo) { pendiente = i; return; }
      aplicarCapas(map, IDS, p.capas);
      mostrar(marcas.prov, p.rot === 'prov'); mostrar(marcas['2017'], p.rot === '2017'); mostrar(marcas['2023'], p.rot === '2023');
      map.setTerrain(p.terreno ? { source: 'dem', exaggeration: 1.3 } : null);
      irA(map, p.b, { pitch: p.pitch || 0, bearing: p.bearing || 0, dz: p.dz || 0 });
    }
    if (map) map.on('load', () => {
      map.addLayer({ id: 'a2017', type: 'raster', source: 'a2017', paint: { 'raster-opacity': 0, 'raster-resampling': 'nearest' } });
      map.addLayer({ id: 'ems-f', type: 'fill', source: 'ems', filter: ['==', ['get', 'tipo'], 'inundacion'], paint: { 'fill-color': '#ffffff', 'fill-opacity': 0 } });
      map.addLayer({ id: 'ems-l', type: 'line', source: 'ems', filter: ['==', ['get', 'tipo'], 'inundacion'], paint: { 'line-color': '#ffffff', 'line-width': .8, 'line-opacity': 0 } });
      map.addLayer({ id: 'aoi-l', type: 'line', source: 'ems', filter: ['==', ['get', 'tipo'], 'aoi'], paint: { 'line-color': '#a8c2ff', 'line-width': 1.4, 'line-dasharray': [3, 2], 'line-opacity': 0 } });
      capasLimites(map);
      map.addLayer({ id: 'flujos', type: 'circle', source: 'flujos', paint: { 'circle-color': ['case', ['get', 'huaico'], HU, HU2], 'circle-radius': ['interpolate', ['linear'], ['zoom'], 7, 2.6, 12, 6],
        'circle-stroke-color': '#10122a', 'circle-stroke-width': .8, 'circle-opacity': 0, 'circle-stroke-opacity': 0 } });
      map.addLayer({ id: 'eventos', type: 'circle', source: 'eventos', paint: { 'circle-color': ['match', ['get', 'evento'], '2017', E17N, E23N], 'circle-radius': 7,
        'circle-stroke-color': '#ffffff', 'circle-stroke-width': 2, 'circle-opacity': 0, 'circle-stroke-opacity': 0 } });
      marcas.prov = D.PROV.features.map(f => rotulo(map, nombre(f.properties.NOMBPROV), [f.properties.lab_x, f.properties.lab_y], 'prov'));
      const vistos = new Set();
      D.EVENTOS_H.features.forEach(f => {
        const p = f.properties, k = p.evento + p.lugar; if (vistos.has(k)) return; vistos.add(k);
        const fechas = D.EVENTOS_H.features.filter(g => g.properties.evento === p.evento && g.properties.lugar === p.lugar).map(g => g.properties.fecha_texto).join(' y ');
        marcas[p.evento].push(rotulo(map, `${p.lugar}<small>${fechas} · ${nombre(p.distrito)}</small>`, f.geometry.coordinates, 'ev'));
      });
      listo = true; paso(pendiente);
    });
    registerStory($('stB-sec'), paso);
  }

  /* ---------- Notas II: validación y huaicos ---------- */
  function notasII(D) {
    const V = D.R.validacion;
    $('t-val').querySelector('tbody').innerHTML = V.map((r, i) => `<tr><td><b>${AOI[r.aoi] || r.aoi}</b><span class="sub">${r.aoi}</span></td><td class="n">${fmt(r.ems_inundado_km2, 1)}</td>` +
      `<td><div class="db"><span class="tr"><i class="gx" style="width:${r.deteccion_2fechas_pct.toFixed(1)}%;--i:${i}"></i></span><span class="v">${fmt(r.deteccion_2fechas_pct, 1)} %</span></div></td>` +
      `<td class="n">${r.gfm_fuera_ems_pct != null ? fmt(r.gfm_fuera_ems_pct, 0) + ' %' : '—'}</td></tr>`).join('');
    $('t-huaicos').querySelector('tbody').innerHTML = D.EVENTOS_H.features.map(f => f.properties).sort((a, b) => a.fecha < b.fecha ? -1 : 1).map(p =>
      `<tr><td><span class="chip e${p.evento.slice(2)}">${p.evento}</span></td><td class="n">${p.fecha_texto}</td><td><b>${p.lugar}</b><span class="sub">${nombre(p.distrito)}, ${nombre(p.provincia)}</span></td>` +
      `<td class="wrap-ok">${p.descripcion}<span class="sub">${p.tipo} · ubicación: ${p.ubicacion.charAt(0).toLowerCase() + p.ubicacion.slice(1)}</span></td><td class="wrap-ok"><a href="${p.url}" target="_blank" rel="noopener">${p.fuente}</a></td></tr>`).join('');
    // Gráfico 3: inventario de INGEMMET por provincia y tipo
    const TIPOS = [['Flujo de detritos', 'var(--hu)'], ['Flujo de lodo', '#8a4b2a'], ['Avalancha de rocas', 'var(--muted)'], ['Otros', 'var(--rule)']];
    const pp = {};
    D.R.huaicos.por_provincia_tipo.forEach(r => { const t = TIPOS.some(x => x[0] === r.tipo) ? r.tipo : 'Otros'; (pp[r.provincia] = pp[r.provincia] || {})[t] = ((pp[r.provincia] || {})[t] || 0) + r.n; });
    const orden = Object.entries(pp).map(([p, v]) => [p, v, Object.values(v).reduce((s, n) => s + n, 0)]).sort((a, b) => b[2] - a[2]);
    const max = orden[0][2];
    $('g-ingemmet').innerHTML = `<div class="stk-leg">${TIPOS.map(([t, c]) => `<span><i class="swt" style="background:${c}"></i>${t}</span>`).join('')}</div>` +
      orden.map(([p, v, tot], i) => `<div class="stk"><div class="stk-l"><b>${nombre(p)}</b></div><div class="stk-t gx" style="width:${(tot / max * 100).toFixed(1)}%;--i:${i}">` +
        TIPOS.filter(([t]) => v[t]).map(([t, c]) => `<i style="flex:${v[t]};background:${c}" data-tip="<b>${nombre(p)}</b><br>${t}: ${fmt(v[t])}"></i>`).join('') +
        `</div><div class="stk-v">${fmt(tot)}</div></div>`).join('');
  }

  /* ---------- Capítulo V: viviendas en 3D ---------- */
  function historiaC(D) {
    const root = $('stC'); const map = nuevoMapa(root.querySelector('.gl'), 'imagen', { bounds: CIUDAD_B, fuentes: {
      edif: { type: 'geojson', data: { type: 'FeatureCollection', features: [] } }, ems: { type: 'geojson', data: D.EMS } } });
    const cnt = counter(root.querySelector('.counter')), leg = root.querySelector('.legend');
    const Ed = D.R.edificios;
    const CAT = ['case', ['!=', ['get', 'ems2017_grado'], ''], ['get', 'ems2017_grado'], ['boolean', ['get', 'ems2017_inundacion'], false], 'inundacion',
      ['any', ['boolean', ['get', 'gfm2017'], false], ['boolean', ['get', 'gfm2023'], false]], 'radar', 'ninguna'];
    const COLOR = { inundacion: W2, radar: '#ffffff', ...Object.fromEntries(GRADOS.map(g => [g[0], g[2]])) };
    const color = cats => ['match', CAT, ...Object.entries(COLOR).flatMap(([k, c]) => [k, cats.includes(k) ? c : '#3b3f63']), '#3b3f63'];
    const alto = cats => ['match', CAT, cats.length ? cats : ['__'], 24, 2.5];
    const todas = Object.keys(COLOR), grados = GRADOS.map(g => g[0]);
    const leyCat = cats => '<b>Edificios (Microsoft) según la fuente</b>' + [['inundacion', 'En zona inundada (Copernicus)'], ...GRADOS.map(g => [g[0], 'Manzana: ' + g[1].toLowerCase()]), ['radar', 'Con agua del radar (GFM)'], ['ninguna', 'Sin afectación registrada']]
      .filter(([k]) => k === 'ninguna' || cats.includes(k)).map(([k, l]) => `<span><i style="background:${k === 'ninguna' ? '#3b3f63' : COLOR[k]}"></i>${l}</span>`).join('');
    let feats = [];
    const cat = p => p.ems2017_grado || (p.ems2017_inundacion ? 'inundacion' : (p.gfm2017 || p.gfm2023) ? 'radar' : 'ninguna');
    // Cámaras fijas: los afectados están en la ciudad (y el radar, también en el Bajo Piura)
    const PASOS = [
      { cats: todas, c: { v: Ed.afectado_2017, l: 'edificios en zona inundada o en manzana dañada, 2017' }, cam: [-80.645, -5.180, 13.3, 55, -20] },
      { cats: ['inundacion'], c: { v: Ed.ems2017_inundacion, l: 'edificios dentro de la inundación delimitada por Copernicus' }, cam: [-80.650, -5.178, 13.6, 58, 15] },
      { cats: grados, c: { v: Ed.ems2017_manzana_danada, l: 'edificios en manzanas con daño (Copernicus EMS)' }, cam: [-80.636, -5.200, 14.2, 60, -40] },
      { cats: ['radar'], c: { v: Ed.gfm2017 + Ed.gfm2023, l: `edificios con agua según el radar (${fmt(Ed.gfm2017)} en 2017 y ${fmt(Ed.gfm2023)} en 2023)` }, cam: [-80.660, -5.255, 11.9, 50, 0] },
    ];
    let listo = false, cargado = false, pendiente = 0;
    function paso(i) {
      const p = PASOS[i]; if (!p) return;
      cnt(p.c); leg.innerHTML = leyCat(p.cats);
      if (!map) return;
      pendiente = i;
      if (!listo || !cargado) return;
      map.setPaintProperty('edif', 'fill-extrusion-color', color(p.cats));
      map.setPaintProperty('edif', 'fill-extrusion-height', alto(p.cats));
      const [lon, lat, z, pitch, bearing] = p.cam;
      map.flyTo({ center: [lon, lat], zoom: z - (MOBILE.matches ? .9 : 0), pitch, bearing, padding: margenEscenario(map), duration: REDUCE ? 0 : 2000, essential: true });
    }
    function cargar() {
      get('data/edificios_piura.geojson').then(g => {
        feats = g.features; map.getSource('edif').setData(g); cargado = true; paso(pendiente);
        const n = {}; feats.forEach(f => { const c = cat(f.properties); n[c] = (n[c] || 0) + 1; });
        const total = Object.entries(n).filter(([k]) => k !== 'ninguna').reduce((s, [, v]) => s + v, 0) || 1;
        const t = $('t-edif');
        if (t) t.querySelector('tbody').innerHTML = [['inundacion', 'En zona inundada (Copernicus EMS)'], ...GRADOS.map(g => [g[0], `En manzana con ${g[1].toLowerCase()}`]), ['radar', 'Solo con agua del radar (GFM)']]
          .map(([k, l], i) => `<tr><td><i class="swt" style="background:${COLOR[k]};box-shadow:inset 0 0 0 1px var(--rule)"></i>${l}</td><td class="n">${fmt(n[k] || 0)}</td>` +
            `<td><div class="db"><span class="tr"><i class="gx" style="width:${((n[k] || 0) / total * 100).toFixed(1)}%;--i:${i}"></i></span><span class="v">${fmt((n[k] || 0) / total * 100, 1)} %</span></div></td></tr>`).join('') +
          `<tr><td><b>Total en zonas afectadas (2017 o 2023)</b></td><td class="n"><b>${fmt(total)}</b></td><td></td></tr>`;
        observarAnim();
      }).catch(e => console.error('edificios', e));
    }
    if (map) map.on('load', () => {
      map.addLayer({ id: 'ems-l', type: 'line', source: 'ems', filter: ['==', ['get', 'tipo'], 'inundacion'], paint: { 'line-color': '#ffffff', 'line-width': 1, 'line-opacity': .55 } });
      map.addLayer({ id: 'edif', type: 'fill-extrusion', source: 'edif', paint: { 'fill-extrusion-color': color(todas), 'fill-extrusion-height': alto(todas), 'fill-extrusion-opacity': .92 } });
      listo = true;
      const io = new IntersectionObserver(es => { if (es[0].isIntersecting && !cargado) { io.disconnect(); cargar(); } }, { rootMargin: '150% 0px' });
      io.observe($('stC-sec'));
    });
    registerStory($('stC-sec'), paso);
  }

  /* ---------- Capítulo VI: explorador ---------- */
  const INDICADORES = {
    inund_anom_km2: { l: 'Inundación anómala', u: 'km²', cortes: [.1, 1, 5, 20, 50], d: 1 },
    inund_max_km2: { l: 'Máximo anómalo en un día', u: 'km²', cortes: [.1, 1, 5, 20, 50], d: 1 },
    pct_anom: { l: '% del distrito con agua anómala', u: '%', cortes: [.1, .5, 2, 5, 15], d: 1 },
    inund_union_km2: { l: 'Toda el agua detectada', u: 'km²', cortes: [.1, 1, 5, 20, 50], d: 1 },
    fechas_con_agua: { l: 'Fechas con agua', u: 'fechas', cortes: [1, 3, 6, 12, 24], d: 0 },
  };
  const RAMPA = ['#1e2241', '#0f3a55', '#13618a', '#1f8bc0', '#4fb3e0', '#a6e8ff'];
  function explorador(D) {
    const st = { ev: '2017', prov: 'TODAS', ind: 'inund_anom_km2', dist: null };
    const F = D.DIST.features, porUbi = Object.fromEntries(F.map(f => [f.properties.UBIGEO, f]));
    const lista = F.map(f => f.properties).sort((a, b) => a.NOMBDIST < b.NOMBDIST ? -1 : 1);
    const etiqueta = p => `${nombre(p.NOMBDIST)} (${nombre(p.NOMBPROV)})`;
    $('x-dl').innerHTML = lista.map(p => `<option value="${etiqueta(p)}">`).join('');
    const sel = $('x-prov');
    sel.innerHTML = '<option value="TODAS">Todo Piura</option>' + [...new Set(lista.map(p => p.NOMBPROV))].sort().map(p => `<option value="${p}">${nombre(p)}</option>`).join('');
    const map = nuevoMapa($('mapa-x'), 'oscuro', { interactivo: true, fuentes: {
      dist: { type: 'geojson', data: D.DIST, promoteId: 'UBIGEO' }, prov: { type: 'geojson', data: D.PROV }, dep: { type: 'geojson', data: D.DEP },
      agua: { type: 'image', url: 'data/agua_2017.png', coordinates: D.AGUA.esquinas }, ems: { type: 'geojson', data: D.EMS },
      flujos: { type: 'geojson', data: D.FLUJOS }, eventos: { type: 'geojson', data: D.EVENTOS_H } } });
    const valor = (p, ind = st.ind, ev = st.ev) => +p[`${ind}_${ev}`] || 0;
    const enSel = p => st.prov === 'TODAS' || p.NOMBPROV === st.prov;
    const colorExpr = () => { const c = INDICADORES[st.ind].cortes; return ['step', ['to-number', ['get', `${st.ind}_${st.ev}`], 0], RAMPA[0], ...c.flatMap((v, i) => [v, RAMPA[i + 1]])]; };
    function leyenda() {
      const I = INDICADORES[st.ind], c = I.cortes;
      $('x-ley').innerHTML = `<div class="ramp">${RAMPA.map(r => `<i style="background:${r}"></i>`).join('')}</div><div class="ramp-l"><span>0</span>${c.map(v => `<span>${fmt(v, v < 1 ? 1 : 0)}</span>`).join('')}</div><p class="small">${I.l} (${I.u}), ${st.ev}</p>`;
    }
    function kpis() {
      const props = st.dist ? [porUbi[st.dist].properties] : F.map(f => f.properties).filter(enSel);
      const ubis = props.map(p => p.UBIGEO), area = props.reduce((s, p) => s + p.area_km2, 0);
      const suma = ev => props.reduce((s, p) => s + valor(p, 'inund_anom_km2', ev), 0);
      const otro = st.ev === '2017' ? '2023' : '2017';
      const pico = picoDe(st.ev, ubis), con = props.filter(p => valor(p, 'inund_anom_km2') >= .1).length;
      const lugar = st.dist ? nombre(porUbi[st.dist].properties.NOMBDIST) : st.prov === 'TODAS' ? 'Piura' : 'la provincia de ' + nombre(st.prov);
      $('x-lugar').textContent = lugar; $('x-lugar2').textContent = lugar; $('x-lugar3').textContent = lugar;
      $('x-kpis').innerHTML = [
        ['Inundación anómala', fmt(suma(st.ev), 1), 'km²', `${otro}: ${fmt(suma(otro), 1)} km²`],
        ['Distritos con agua', fmt(con), `de ${props.length}`, 'con 0,1 km² o más de agua anómala'],
        ['Máximo en un día', pico ? fmt(pico.v, 1) : '0', 'km²', pico && pico.v > 0 ? `el ${fecha(pico.f)}` : 'sin agua anómala'],
        ['Territorio con agua', fmt(area ? suma(st.ev) / area * 100 : 0, 2), '%', `de ${fmt(area)} km²`],
      ].map(([k, v, u, c]) => `<div><div class="k">${k} · ${st.ev}</div><div class="big">${v}<small>${u}</small></div><span class="cmp">${c}</span></div>`).join('');
      graficoSemanal($('x-graf'), ubis, lugar);
      // Ranking de la selección (la provincia, o la del distrito elegido)
      const base = F.map(f => f.properties).filter(p => st.dist ? p.NOMBPROV === porUbi[st.dist].properties.NOMBPROV : enSel(p));
      const filas = base.map(p => [p, valor(p)]).filter(x => x[1] > 0).sort((a, b) => b[1] - a[1]).slice(0, 10);
      const I = INDICADORES[st.ind], mx = filas.length ? filas[0][1] : 1;
      $('x-rank').innerHTML = filas.length ? filas.map(([p, v], i) => `<li data-u="${p.UBIGEO}" class="${p.UBIGEO === st.dist ? 'on' : ''}"><span class="i">${i + 1}</span><span class="nm">${nombre(p.NOMBDIST)}</span><span class="v">${fmt(v, I.d)}</span></li>`).join('')
        : '<li><span></span><span class="nm">Ningún distrito con agua anómala</span><span></span></li>';
      $('x-top').querySelector('tbody').innerHTML = filas.map(([p], i) => `<tr><td class="n">${i + 1}</td><td><b>${nombre(p.NOMBDIST)}</b><span class="sub">${nombre(p.NOMBPROV)}</span></td><td><div class="pair">` +
        EVENTOS.map(e => `<div class="db"><span class="tr"><i class="gx e${e.slice(2)}" style="width:${(valor(p, st.ind, e) / Math.max(mx, ...filas.map(x => valor(x[0], st.ind, e === '2017' ? '2023' : '2017'))) * 100).toFixed(1)}%;--i:${i}"></i></span><span class="v">${fmt(valor(p, st.ind, e), I.d)}</span></div>`).join('') + '</div></td></tr>').join('');
      $('x-top-u').textContent = `${I.l} (${I.u}) en 2017 y 2023`;
      animar($('f-xtop'));
    }
    function pintar() {
      if (!map || !map.getLayer('dist-f')) return;
      map.setPaintProperty('dist-f', 'fill-color', colorExpr());
      map.setPaintProperty('dist-f', 'fill-opacity', st.prov === 'TODAS' ? .82 : ['case', ['==', ['get', 'NOMBPROV'], st.prov], .86, .18]);
      map.setFilter('sel-l', ['==', ['get', 'UBIGEO'], st.dist || '']);
      map.getSource('agua').updateImage({ url: `data/agua_${st.ev}.png`, coordinates: D.AGUA.esquinas });
    }
    function encuadrar() {
      if (!map) return;
      const f = st.dist ? [porUbi[st.dist]] : st.prov === 'TODAS' ? null : F.filter(x => x.properties.NOMBPROV === st.prov);
      const b = f ? bboxDe(f) : PIURA_B;
      map.fitBounds([[b[0], b[1]], [b[2], b[3]]], { padding: 40, duration: REDUCE ? 0 : 900, maxZoom: 11.5 });
    }
    function todo(enc) { leyenda(); kpis(); pintar(); if (enc) encuadrar(); }
    function elegir(u) { st.dist = u; if (u) { $('x-buscar').value = etiqueta(porUbi[u].properties); } todo(true); }
    document.querySelectorAll('#x-ev button').forEach(b => b.addEventListener('click', () => {
      document.querySelectorAll('#x-ev button').forEach(x => x.setAttribute('aria-pressed', String(x === b))); st.ev = b.dataset.v; todo(false);
    }));
    sel.addEventListener('change', () => { st.prov = sel.value; st.dist = null; $('x-buscar').value = ''; todo(true); });
    $('x-ind').addEventListener('change', e => { st.ind = e.target.value; todo(false); });
    $('x-buscar').addEventListener('change', e => {
      const t = e.target.value.trim().toLowerCase(); if (!t) { elegir(null); return; }
      const p = lista.find(x => etiqueta(x).toLowerCase() === t) || lista.find(x => nombre(x.NOMBDIST).toLowerCase().startsWith(t));
      if (p) { st.prov = 'TODAS'; sel.value = 'TODAS'; elegir(p.UBIGEO); }
    });
    $('x-limpiar').addEventListener('click', () => { st.dist = null; st.prov = 'TODAS'; sel.value = 'TODAS'; $('x-buscar').value = ''; todo(true); });
    $('x-rank').addEventListener('click', e => { const li = e.target.closest('li[data-u]'); if (li) elegir(li.dataset.u); });
    const CAPAS = { 'L-agua': ['agua'], 'L-ems': ['ems-f', 'ems-l'], 'L-flujos': ['flujos'], 'L-eventos': ['eventos'] };
    Object.entries(CAPAS).forEach(([id, ls]) => $(id).addEventListener('change', e => { if (map) ls.forEach(l => map.getLayer(l) && map.setLayoutProperty(l, 'visibility', e.target.checked ? 'visible' : 'none')); }));
    if (map) {
      map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), 'top-right');
      map.on('load', () => {
        const vis = id => $(id).checked ? 'visible' : 'none';
        map.addLayer({ id: 'dist-f', type: 'fill', source: 'dist', paint: { 'fill-color': colorExpr(), 'fill-opacity': .82 } });
        map.addLayer({ id: 'agua', type: 'raster', source: 'agua', layout: { visibility: vis('L-agua') }, paint: { 'raster-opacity': .95, 'raster-resampling': 'nearest' } });
        map.addLayer({ id: 'dist-l', type: 'line', source: 'dist', paint: { 'line-color': '#10122a', 'line-width': .6 } });
        capasLimites(map, .85);
        map.addLayer({ id: 'ems-f', type: 'fill', source: 'ems', filter: ['==', ['get', 'tipo'], 'inundacion'], layout: { visibility: vis('L-ems') }, paint: { 'fill-color': '#ffffff', 'fill-opacity': .4 } });
        map.addLayer({ id: 'ems-l', type: 'line', source: 'ems', filter: ['==', ['get', 'tipo'], 'inundacion'], layout: { visibility: vis('L-ems') }, paint: { 'line-color': '#ffffff', 'line-width': .7 } });
        map.addLayer({ id: 'flujos', type: 'circle', source: 'flujos', layout: { visibility: vis('L-flujos') }, paint: { 'circle-color': ['case', ['get', 'huaico'], HU, HU2], 'circle-radius': ['interpolate', ['linear'], ['zoom'], 7, 2.5, 12, 6], 'circle-stroke-color': '#10122a', 'circle-stroke-width': .8 } });
        map.addLayer({ id: 'eventos', type: 'circle', source: 'eventos', layout: { visibility: vis('L-eventos') }, paint: { 'circle-color': ['match', ['get', 'evento'], '2017', E17N, E23N], 'circle-radius': 6.5, 'circle-stroke-color': '#fff', 'circle-stroke-width': 2 } });
        map.addLayer({ id: 'sel-l', type: 'line', source: 'dist', filter: ['==', ['get', 'UBIGEO'], ''], paint: { 'line-color': '#ffffff', 'line-width': 2.6 } });
        const ro = $('x-readout');
        const texto = p => { const I = INDICADORES[st.ind]; return `<b>${nombre(p.NOMBDIST)}</b> · ${nombre(p.NOMBPROV)}<br>${I.l}, ${st.ev}: <b>${fmt(valor(p), I.d)} ${I.u}</b><span>2017: ${fmt(valor(p, st.ind, '2017'), I.d)} · 2023: ${fmt(valor(p, st.ind, '2023'), I.d)} · máximo el ${p['fecha_max_' + st.ev] ? fecha(p['fecha_max_' + st.ev]) : '—'}</span>`; };
        map.on('mousemove', 'dist-f', e => { map.getCanvas().style.cursor = 'pointer'; ro.innerHTML = texto(e.features[0].properties); });
        map.on('mouseleave', 'dist-f', () => { map.getCanvas().style.cursor = ''; ro.innerHTML = st.dist ? texto(porUbi[st.dist].properties) : ''; });
        map.on('click', e => {
          const h = map.queryRenderedFeatures(e.point, { layers: ['eventos', 'flujos'].filter(l => map.getLayoutProperty(l, 'visibility') !== 'none') });
          if (h.length) {
            const p = h[0].properties;
            new maplibregl.Popup({ closeButton: true, maxWidth: '280px' }).setLngLat(e.lngLat).setHTML(h[0].layer.id === 'eventos'
              ? `<b>${p.lugar}</b><br>${p.fecha_texto} · ${p.tipo}<br>${p.descripcion}<br><a href="${p.url}" target="_blank" rel="noopener">${p.fuente}</a>`
              : `<b>${p.tipo}</b><br>${p.sector || ''}<br>${nombre(p.distrito || '')}, ${nombre(p.provincia || '')}${p.anio ? ' · inventario ' + p.anio : ''}<br><span>INGEMMET</span>`).addTo(map);
            return;
          }
          const d = map.queryRenderedFeatures(e.point, { layers: ['dist-f'] });
          if (d.length) elegir(d[0].properties.UBIGEO === st.dist ? null : d[0].properties.UBIGEO);
        });
        pintar();
      });
    }
    todo(false);
  }

  /* ---------- Capítulo VII: síntesis ---------- */
  function sintesis(D) {
    const H = D.R.hallazgos || [];
    $('hallazgos').innerHTML = H.map(h => `<div class="find"><div class="big">${h.cifra}<small>${h.unidad || ''}</small></div><h3>${h.titulo}</h3><p>${h.texto}</p></div>`).join('');
  }
})();
