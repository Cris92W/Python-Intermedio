"""Arma el reel de la Tarea 3: 1080 × 1920, 30 fps, 60 s, con mapas y gráficos animados al ritmo de la narración.

Uso (desde tarea_3/reel, con el entorno de PRACTICA_2, que tiene Pillow e imageio-ffmpeg):
    ../../PRACTICA_2/.venv/Scripts/python video.py              # reel.mp4, reel.srt y portada.png
    ../../PRACTICA_2/.venv/Scripts/python video.py 3.5 20 41    # solo cuadros sueltos en salidas/muestras/, para revisar
    ../../PRACTICA_2/.venv/Scripts/python video.py portada      # solo la portada
Requiere salidas/reel.wav y salidas/tiempos.json (voz.py), recursos/base.jpg (preparar.py),
recursos/dash_*.png (capturas.py), recursos/floating_cities.mp3 y los datos del dashboard en ../web/data.
"""
import json
import math
import re
import subprocess
import sys
import time
from datetime import date
from functools import lru_cache
from pathlib import Path

import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

sys.stdout.reconfigure(encoding="utf-8")

AQUI = Path(__file__).resolve().parent
SAL, REC, DATOS = AQUI / "salidas", AQUI / "recursos", AQUI.parent / "web" / "data"
W, H, FPS, DURACION = 1080, 1920, 30, 60.0
FUNDIDO = 0.35                 # transición entre escenas, en segundos
CREDITOS = 3.2                 # mínimo de créditos finales con la música sola
MAX_VELOCIDAD = 1.07           # si la narración no cabe, se acelera hasta un 7 % (sin cambiar el tono)
MARGEN = 64
Y_CIFRA, Y_VIS, H_VIS, Y_SUB = 168, 452, 1000, 1585   # zonas: cifra, visual (mapa o gráfico) y subtítulos
URL = "cris92w.github.io/Python-Intermedio/tarea_3/web"

# Paleta del dashboard (Ciclón Yaku)
NOCHE, NOCHE2, LINEA = (16, 18, 42), (24, 27, 56), (42, 46, 82)
TINTA, TENUE, ACENTO, ORO = (227, 229, 244), (156, 161, 196), (168, 194, 255), (255, 209, 102)
E17, E23, HUAICO, HALO = (242, 160, 61), (108, 195, 216), (224, 122, 58), (5, 6, 26)
CIUDADES = [("Piura", -80.632, -5.194), ("Sullana", -80.685, -4.904), ("Talara", -81.272, -4.577), ("Paita", -81.114, -5.089),
            ("Sechura", -80.822, -5.557), ("Chulucanas", -80.162, -5.093), ("Huancabamba", -79.451, -5.239), ("Ayabaca", -79.715, -4.639)]
MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "set", "oct", "nov", "dic"]


# ---------- Tipografía (las del dashboard, variables) ----------
def variable(archivo, tam, **ejes):
    f = ImageFont.truetype(str(REC / "fuentes" / archivo), tam)
    f.set_variation_by_axes([ejes.get(a["name"].decode().lower().split()[0], a["default"]) for a in f.get_variation_axes()])
    return f


@lru_cache(maxsize=None)
def archivo(tam, peso=800, ancho=104):
    return variable("Archivo.ttf", tam, weight=peso, width=ancho)


@lru_cache(maxsize=None)
def mono(tam):
    return ImageFont.truetype(str(REC / "fuentes" / "IBMPlexMono-Medium.ttf"), tam)


F_KICK, F_ETIQ, F_CRED, F_SUB = mono(25), archivo(40, 500, 100), mono(23), archivo(62, 650, 100)
F_TAG, F_CIUDAD, F_EJE = mono(24), archivo(31, 650, 100), mono(22)


# ---------- Utilidades ----------
def acotar(u):
    return max(0.0, min(1.0, u))


def suave(u):
    u = acotar(u)
    return u * u * (3 - 2 * u)


def salida(u):
    u = acotar(u)
    return 1 - (1 - u) ** 3


def entero(v):
    """Redondeo comercial (254,5 -> 255), igual que en el dashboard; Python redondea las mitades al par."""
    return int(math.floor(v + 0.5))


def miles(n):
    return f"{entero(n):,}".replace(",", " ")


def limpiar(w):
    return re.sub(r"[^\wáéíóúñü²]", "", w.lower())


def envolver(texto, f, ancho):
    lineas, linea = [], ""
    for p in texto.split():
        prueba = (linea + " " + p).strip()
        if linea and f.getlength(prueba) > ancho:
            lineas.append(linea)
            linea = p
        else:
            linea = prueba
    return lineas + ([linea] if linea else [])


def ajustar(texto, tam_max, peso=800, ancho=W - 2 * MARGEN):
    tam = tam_max
    while tam > 40 and archivo(tam, peso).getlength(texto) > ancho:
        tam -= 4
    return archivo(tam, peso)


def pastilla(d, xy, texto, f, fondo, color, pad=(16, 9)):
    x, y = xy
    an = f.getlength(texto)
    asc, desc = f.getmetrics()
    d.rounded_rectangle([x, y, x + an + 2 * pad[0], y + asc + desc + 2 * pad[1]], radius=999, fill=fondo)
    d.text((x + pad[0], y + pad[1]), texto, font=f, fill=color)
    return x + an + 2 * pad[0]


def mezclar(a, b, u):
    return tuple(round(x + (y - x) * u) for x, y in zip(a, b))


# ---------- Mapa: mosaico de Esri en Web Mercator, como las capas de agua del dashboard ----------
BASE = json.loads((REC / "base.json").read_text(encoding="utf-8"))
ASPECTO = W / H_VIS


def px(lon, lat):
    """Píxel del mosaico de un punto (Web Mercator, zoom del mosaico)."""
    n = 2 ** BASE["z"]
    y = (1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2 * n
    return ((lon + 180) / 360 * n - BASE["x0"]) * 256, (y - BASE["y0"]) * 256


def anillos(geom):
    return [r for pol in ([geom["coordinates"]] if geom["type"] == "Polygon" else geom["coordinates"]) for r in pol]


def caja(lon0, lat0, lon1, lat1, margen=0.08):
    """Cámara (centro x, centro y, ancho en píxeles del mosaico) que encuadra una caja geográfica."""
    (xa, ya), (xb, yb) = px(lon0, lat1), px(lon1, lat0)
    w, h = (xb - xa) * (1 + margen), (yb - ya) * (1 + margen)
    w = max(w, h * ASPECTO)
    return ((xa + xb) / 2, (ya + yb) / 2, w)


def camara(c0, c1, u):
    u = suave(u)
    return (c0[0] + (c1[0] - c0[0]) * u, c0[1] + (c1[1] - c0[1]) * u, c0[2] * (c1[2] / c0[2]) ** u)


def a_pantalla(cam, lon, lat):
    x, y = px(lon, lat)
    cx, cy, w = cam
    s = W / w
    return (x - cx) * s + W / 2, (y - cy) * s + H_VIS / 2 + Y_VIS


PIURA_CAM = caja(-81.36, -6.40, -79.18, -4.05)
SECHURA_CAM = caja(-81.15, -6.15, -80.45, -5.30, 0.0)


class Mapas:
    """Composiciones del mapa a la resolución del mosaico: fondo oscurecido, agua del radar y límites con halo."""

    def __init__(self):
        base = Image.open(REC / "base.jpg").convert("RGB")
        base = ImageEnhance.Brightness(ImageEnhance.Color(base).enhance(0.65)).enhance(0.62)
        self.base = Image.blend(base, Image.new("RGB", base.size, NOCHE), 0.2)
        prov = json.loads((DATOS / "provincias.geojson").read_text(encoding="utf-8"))["features"]
        peru = json.loads((DATOS / "peru.geojson").read_text(encoding="utf-8"))["features"]
        lim = Image.new("RGBA", self.base.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(lim)
        for f in peru:
            if f["properties"]["CCDD"] != "20":
                for r in anillos(f["geometry"]):
                    d.line([px(*c) for c in r], fill=(*TENUE, 110), width=2, joint="curve")
        for f in prov:
            for r in anillos(f["geometry"]):
                pts = [px(*c) for c in r]
                d.line(pts, fill=(*HALO, 150), width=7, joint="curve")
                d.line(pts, fill=(*TINTA, 215), width=2, joint="curve")
        self.piura = [[px(*c) for c in r] for f in peru if f["properties"]["CCDD"] == "20" for r in anillos(f["geometry"])]
        for pts in self.piura:
            d.line(pts, fill=(*HALO, 190), width=12, joint="curve")
            d.line(pts, fill=(255, 255, 255, 255), width=4, joint="curve")
        self.lim = lim
        # Sechura resaltado: el resto del mapa en penumbra y su borde en dorado
        sech = next(f for f in prov if f["properties"]["NOMBPROV"] == "SECHURA")
        sombra = Image.new("RGBA", self.base.size, (*NOCHE, 150))
        hueco = Image.new("L", self.base.size, 255)
        for r in anillos(sech["geometry"]):
            ImageDraw.Draw(hueco).polygon([px(*c) for c in r], fill=0)
        sombra.putalpha(Image.eval(hueco, lambda v: 150 if v else 0))
        borde = Image.new("RGBA", self.base.size, (0, 0, 0, 0))
        for r in anillos(sech["geometry"]):
            ImageDraw.Draw(borde).line([px(*c) for c in r], fill=(*ORO, 255), width=7, joint="curve")
        esq = json.loads((DATOS / "agua.json").read_text(encoding="utf-8"))["esquinas"]
        (x0, y0), (x1, y1) = px(*esq[0]), px(*esq[2])
        self.agua = {}
        for ev in ("2017", "2023"):
            im = Image.open(DATOS / f"agua_{ev}.png").convert("RGBA").filter(ImageFilter.MaxFilter(3))
            capa = Image.new("RGBA", self.base.size, (0, 0, 0, 0))
            capa.alpha_composite(im.resize((round(x1 - x0), round(y1 - y0)), Image.BILINEAR), (round(x0), round(y0)))
            self.agua[ev] = capa
        self.comp = {"vacio": self.componer()}
        for ev in ("2017", "2023"):
            self.comp[ev] = self.componer(self.agua[ev])
        self.comp["sechura"] = self.componer(self.agua["2023"], [sombra, borde])
        self.comp["oscuro"] = Image.blend(self.comp["vacio"], Image.new("RGB", self.base.size, NOCHE), 0.35)

    def componer(self, agua=None, extra=()):
        im = self.base.convert("RGBA")
        if agua is not None:
            im.alpha_composite(agua)
        for e in extra:
            im.alpha_composite(e)
        im.alpha_composite(self.lim)
        return im.convert("RGB")

    def vista(self, clave, cam):
        cx, cy, w = cam
        h = w / ASPECTO
        return self.comp[clave].resize((W, H_VIS), Image.BILINEAR, box=(cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2))

    def fundido(self, a, b, u, cam):
        if u <= 0:
            return self.vista(a, cam)
        if u >= 1:
            return self.vista(b, cam)
        return Image.blend(self.vista(a, cam), self.vista(b, cam), u)


def rotular(d, cam, nombres, alfa=1.0):
    for n, lon, lat in CIUDADES:
        if n not in nombres:
            continue
        x, y = a_pantalla(cam, lon, lat)
        if not (Y_VIS + 20 < y < Y_VIS + H_VIS - 20 and 20 < x < W - 20):
            continue
        c = mezclar(NOCHE, (255, 255, 255), alfa)
        d.ellipse([x - 7, y - 7, x + 7, y + 7], fill=c, outline=HALO, width=3)
        izq = x + 14 + F_CIUDAD.getlength(n) > W - 24   # si no cabe a la derecha, el rótulo va a la izquierda
        d.text((x - 14 if izq else x + 14, y - 22), n, font=F_CIUDAD, fill=c, stroke_width=4, stroke_fill=HALO,
               anchor="ra" if izq else "la")


# ---------- Datos ----------
def datos():
    R = json.loads((DATOS / "resumen.json").read_text(encoding="utf-8"))
    S = json.loads((DATOS / "serie.json").read_text(encoding="utf-8"))
    serie = {}
    for ev, s in S.items():
        filas = []
        for j, f in enumerate(s["fechas"]):
            vals = [v[j] for v in s["distritos"].values() if v[j] is not None]
            filas.append((f, s["observado_pct"][j], sum(vals) if vals else None))
        serie[ev] = filas
    huaicos = [f["geometry"]["coordinates"] for f in json.loads((DATOS / "huaicos_ingemmet.geojson").read_text(encoding="utf-8"))["features"]
               if f["properties"].get("huaico")]
    huaicos.sort(key=lambda c: (round(c[1] * 4), c[0]))   # aparecen de norte a sur
    return R, serie, huaicos


def dia_temporada(ev, f):
    """Días desde el 1 de diciembre anterior al evento (eje común: dic → jun)."""
    y, m, d = (int(v) for v in f.split("-"))
    return (date(y, m, d) - date(int(ev) - 1, 12, 1)).days


# ---------- Escenas ----------
class Escena:
    def __init__(self, k, guion, tiempos, cortes, mapas, R, serie, huaicos):
        self.k, self.e = k, guion
        self.palabras = tiempos["escenas"][k]["palabras"]
        self.t0, self.t1 = cortes[k], cortes[k + 1]
        self.voz0, self.voz1 = tiempos["escenas"][k]["inicio"], tiempos["escenas"][k]["fin"]
        self.mapas, self.R, self.serie, self.huaicos = mapas, R, serie, huaicos

    def cuando(self, palabra, n=1):
        """Inicio de la n-ésima aparición de una palabra en la narración de la escena."""
        clave = limpiar(palabra)
        hits = [p["i"] for p in self.palabras if limpiar(p["w"]) == clave]
        return hits[n - 1] if len(hits) >= n else self.voz0

    def render(self, t):
        img = Image.new("RGB", (W, H), NOCHE)
        d = ImageDraw.Draw(img, "RGBA")
        getattr(self, "e_" + self.e["id"])(img, d, t)
        return img

    # Cifra grande y su etiqueta, con entrada suave
    def cifra(self, d, texto, etiqueta, u=1.0, color=(255, 255, 255), tam=150):
        if u <= 0:
            return
        f = ajustar(texto, tam)
        dy = (1 - salida(u)) * 30
        d.text((MARGEN, Y_CIFRA + dy), texto, font=f, fill=mezclar(NOCHE, color, salida(u)))
        y = Y_CIFRA + f.getmetrics()[0] + 26 + dy
        for linea in envolver(etiqueta, F_ETIQ, W - 2 * MARGEN)[:2]:
            d.text((MARGEN, y), linea, font=F_ETIQ, fill=mezclar(NOCHE, ACENTO, salida(u)))
            y += 50

    def anio(self, d, ev, u=1.0):
        if u > 0:
            col = mezclar(NOCHE2, E17 if ev == "2017" else E23, salida(u))
            pastilla(d, (W - MARGEN - 120, Y_VIS + 28), ev, archivo(38, 800), NOCHE2, col, pad=(18, 8))

    # 1. Gancho: el desierto de Sechura con agua, 2017 y luego 2023
    def e_gancho(self, img, d, t):
        cam = camara(PIURA_CAM, SECHURA_CAM, (t - self.t0 - 0.5) / (self.voz1 - self.t0))
        t17, t23 = self.cuando("llenó"), self.cuando("2023")
        u23 = (t - t23 + 0.2) / 0.6
        vis = self.mapas.fundido("vacio", "2017", (t - t17 + 0.3) / 0.9, cam) if u23 <= 0 else self.mapas.fundido("2017", "2023", u23, cam)
        img.paste(vis, (0, Y_VIS))
        rotular(d, cam, {"Sechura", "Piura", "Paita"})
        self.anio(d, "2023" if u23 > 0.5 else "2017", (t - t17) / 0.5)
        tq = self.cuando("cuánta")
        if t < tq - 0.2:
            self.cifra(d, "Piura bajo el agua", "Dos Niños costeros medidos desde el espacio", (t - self.t0) / 0.6)
        else:
            self.cifra(d, "¿Cuánta agua?", "¿Y cuánto tiempo se quedó?", (t - tq + 0.2) / 0.5, ORO)

    # 2. Método: las pasadas del radar sobre Piura
    def e_metodo(self, img, d, t):
        t92, tsin = self.cuando("92"), self.cuando("sin")
        lienzo = Image.new("RGB", (W * 2, H_VIS * 2), NOCHE)
        g = ImageDraw.Draw(lienzo, "RGBA")
        L, R_, top, PASO, ALTO = 250, W * 2 - 80, 120, 820, 660
        X = lambda dd: L + dd / 212 * (R_ - L)
        for i, m in enumerate(["dic", "ene", "feb", "mar", "abr", "may", "jun"]):
            a = [0, 31, 62, 90, 121, 151, 182, 212][i]
            g.line([(X(a), top), (X(a), top + 2 * PASO)], fill=LINEA, width=2)
            g.text(((X(a) + X([0, 31, 62, 90, 121, 151, 182, 212][i + 1])) / 2, top + 2 * PASO + 30), m, font=mono(44), fill=TENUE, anchor="mt")
        prog = acotar((t - (self.voz0 + 0.3)) / max(t92 + 1.2 - self.voz0 - 0.3, 1))
        total = 0
        for fila, ev in enumerate(("2017", "2023")):
            col = E17 if ev == "2017" else E23
            base = top + fila * PASO + PASO - 40
            g.text((50, base - ALTO), ev, font=archivo(88, 800), fill=col)
            g.line([(L, base), (R_, base)], fill=(*TENUE, 140), width=3)
            vistos = 0
            for f, obs, km in self.serie[ev]:
                x = X(dia_temporada(ev, f))
                u = acotar((prog * (R_ - L) - (x - L)) / 60)
                if u <= 0:
                    continue
                vistos += 1
                alto = ALTO * obs / 100 * salida(u)
                g.line([(x, base), (x, base - max(alto, 10))], fill=(*col, 255 if obs >= 90 else 120), width=8)
            total += vistos
            g.text((50, base - ALTO + 110), f"{vistos} fechas", font=mono(42), fill=TENUE)
        if 0 < prog < 1:
            xs = L + prog * (R_ - L)
            g.line([(xs, top), (xs, top + 2 * PASO)], fill=(*ACENTO, 200), width=4)
        img.paste(lienzo.resize((W, H_VIS), Image.LANCZOS), (0, Y_VIS))
        u = (t - tsin + 0.1) / 0.5
        if u > 0:
            texto = f"Se descuenta el agua habitual de 2022: {self.R['eventos']['2022']['agua_habitual_km2']:.0f} km²"
            pastilla(d, (MARGEN, Y_VIS + H_VIS - 70), texto, mono(26), mezclar(NOCHE, NOCHE2, salida(u)), mezclar(NOCHE, ORO, salida(u)))
        n = round(92 * salida((t - t92 + 0.1) / 1.0))
        self.cifra(d, f"{n} pasadas" if t >= t92 - 0.1 else "Radar Sentinel-1", "Fechas en que el radar vio Piura: 43 en 2017 y 49 en 2023"
                   if t >= t92 - 0.1 else "Ve el agua aunque haya nubes", (t - self.t0) / 0.6)

    # 3. Cuánta agua: 304 km² en 2017, 255 en 2023, casi tres cuartas partes en Sechura
    def e_cuanta(self, img, d, t):
        t304, t255, tcasi = self.cuando("304"), self.cuando("255"), self.cuando("casi")
        cam = camara(PIURA_CAM, caja(-81.3, -6.3, -79.5, -4.3, 0.04), (t - self.t0) / (self.t1 - self.t0))
        if t < t255 - 0.2:
            vis = self.mapas.vista("2017", cam)
        elif t < tcasi - 0.2:
            vis = self.mapas.fundido("2017", "2023", (t - t255 + 0.2) / 0.6, cam)
        else:
            vis = self.mapas.fundido("2023", "sechura", (t - tcasi + 0.2) / 0.6, cam)
        img.paste(vis, (0, Y_VIS))
        rotular(d, cam, {"Piura", "Sullana", "Paita", "Talara", "Sechura", "Chulucanas"})
        self.anio(d, "2023" if t >= t255 - 0.2 else "2017")
        E = self.R["eventos"]
        if t < t255 - 0.2:
            v = E["2017"]["inund_anom_km2"] * salida((t - t304 + 0.1) / 1.1)
            self.cifra(d, f"{entero(v)} km²", "Agua anómala en 2017", (t - self.t0) / 0.5, E17)
        elif t < tcasi - 0.2:
            v = E["2017"]["inund_anom_km2"] + (E["2023"]["inund_anom_km2"] - E["2017"]["inund_anom_km2"]) * salida((t - t255 + 0.2) / 0.9)
            self.cifra(d, f"{entero(v)} km²", "Agua anómala en 2023", 1.0, E23)
        else:
            pp = {(r["evento"], r["NOMBPROV"]): r["inund_anom_km2"] for r in self.R["por_provincia"]}
            p17 = 100 * pp[("2017", "SECHURA")] / E["2017"]["inund_anom_km2"]
            p23 = 100 * pp[("2023", "SECHURA")] / E["2023"]["inund_anom_km2"]
            self.cifra(d, f"{entero(p17)} % y {entero(p23)} %", "Del agua anómala de 2017 y de 2023 cayó en la provincia de Sechura", (t - tcasi + 0.2) / 0.5, ORO)

    # 4. Cuánto tiempo: la curva de 2023 se queda arriba hasta junio
    def e_tiempo(self, img, d, t):
        tini, tmax, t165 = self.cuando("tardó"), self.cuando("máximo"), self.cuando("165")
        lienzo = Image.new("RGB", (W * 2, H_VIS * 2), NOCHE)
        g = ImageDraw.Draw(lienzo, "RGBA")
        L, R_, top, bot = 190, W * 2 - 90, 130, H_VIS * 2 - 150
        X = lambda dd: L + dd / 212 * (R_ - L)
        Y = lambda v: bot - v / 250 * (bot - top)
        for v in (0, 100, 200):
            g.line([(L, Y(v)), (R_, Y(v))], fill=LINEA, width=2)
            g.text((L - 24, Y(v)), str(v), font=mono(40), fill=TENUE, anchor="rm")
        g.text((L - 24, top - 70), "km²", font=mono(40), fill=TENUE, anchor="lm")
        for i, m in enumerate(["dic", "ene", "feb", "mar", "abr", "may", "jun"]):
            a, b = [0, 31, 62, 90, 121, 151, 182, 212][i:i + 2]
            g.text(((X(a) + X(b)) / 2, bot + 40), m, font=mono(42), fill=TENUE, anchor="mt")
        puntos = {ev: [(X(dia_temporada(ev, f)), Y(km), f, km) for f, obs, km in self.serie[ev] if obs >= 90 and km is not None]
                  for ev in ("2017", "2023")}
        u17 = salida((t - self.t0 - 0.2) / 1.2)
        u23 = acotar((t - tini) / max(t165 - tini, 1))   # la curva llega al 26 de junio cuando la voz dice «165»

        def trazo(pts, u, col, ancho):
            if u <= 0 or len(pts) < 2:
                return None
            xfin = pts[0][0] + (pts[-1][0] - pts[0][0]) * u
            linea = [p[:2] for p in pts if p[0] <= xfin]
            sig = next((p for p in pts if p[0] > xfin), None)
            if sig and linea:
                a = linea[-1]
                f = (xfin - a[0]) / (sig[0] - a[0])
                linea.append((xfin, a[1] + (sig[1] - a[1]) * f))
            if len(linea) >= 2:
                g.line(linea, fill=col, width=ancho, joint="curve")
            return linea[-1] if linea else None

        trazo(puntos["2017"], u17, (*E17, 150), 7)
        punta = trazo(puntos["2023"], u23, E23, 10)
        for j, (ev, col) in enumerate((("2017", (*E17, 150)), ("2023", E23))):
            yl = top + 20 + j * 76
            g.line([(L + 30, yl), (L + 110, yl)], fill=col, width=10)
            g.text((L + 130, yl), ev, font=archivo(54, 800), fill=col[:3], anchor="lm")
        if punta:
            g.ellipse([punta[0] - 14, punta[1] - 14, punta[0] + 14, punta[1] + 14], fill=E23)
        um = (t - tmax) / 0.4
        if um > 0:
            x, y = X(dia_temporada("2023", "2023-05-09")), Y(227.6)
            g.ellipse([x - 16, y - 16, x + 16, y + 16], fill=(255, 255, 255))
            g.text((x - 26, y - 34), "9 may · 228", font=archivo(46, 700), fill=mezclar(NOCHE, (255, 255, 255), salida(um)), anchor="rb")
        uf = (t - t165 + 0.2) / 0.4
        if uf > 0:
            x, y = X(dia_temporada("2023", "2023-06-26")), Y(164.8)
            r = 18 + 30 * ((t - t165) % 1.2) / 1.2
            g.ellipse([x - r, y - r, x + r, y + r], outline=(*ORO, round(255 * (1 - ((t - t165) % 1.2) / 1.2))), width=6)
            g.ellipse([x - 16, y - 16, x + 16, y + 16], fill=ORO)
            x2, y2 = X(dia_temporada("2017", "2017-05-31")), Y(43.6)
            g.text((x2 + 4, y2 + 30), "31 may 2017: 44", font=archivo(40, 600), fill=(*E17, round(220 * salida(uf))), anchor="mt")
        img.paste(lienzo.resize((W, H_VIS), Image.LANCZOS), (0, Y_VIS))
        if t < tmax - 0.15:
            self.cifra(d, "Más tiempo", "En 2023 el agua tardó más en irse", (t - self.t0) / 0.5)
        elif t < t165 - 0.2:
            self.cifra(d, "228 km²", "Máximo de 2023: 9 de mayo", 1.0, E23)
        else:
            v = 228 + (164.8 - 228) * salida((t - t165 + 0.2) / 0.8)
            self.cifra(d, f"{entero(v)} km²", "Aún con agua el 26 de junio de 2023", 1.0, ORO)

    # 5. Daño y límites: INDECI, y lo que el radar no ve (ciudad y huaicos)
    def e_dano(self, img, d, t):
        tbaj, tpero, tciu, thua = self.cuando("damnificados"), self.cuando("pero"), self.cuando("ciudades"), self.cuando("huaicos")
        I = self.R["indeci"]
        ub = (t - tpero + 0.25) / 0.5
        if ub < 1:
            lienzo = Image.new("RGB", (W * 2, H_VIS * 2), NOCHE)
            g = ImageDraw.Draw(lienzo, "RGBA")
            crec = salida((t - tbaj + 0.2) / 1.2)
            y = 180
            for nombre, clave in (("Damnificados", "damnificados"), ("Viviendas destruidas", "viviendas_destruidas")):
                g.text((MARGEN * 2, y), nombre, font=archivo(64, 700), fill=TINTA)
                y += 110
                mx = max(I["2017"][clave], I["2023"][clave])
                for ev, col in (("2017", E17), ("2023", E23)):
                    v = I[ev][clave]
                    largo = (W * 2 - 2 * MARGEN * 2 - 330) * v / mx * crec
                    g.text((MARGEN * 2, y + 6), ev, font=mono(46), fill=TENUE)
                    g.rounded_rectangle([MARGEN * 2 + 150, y, MARGEN * 2 + 150 + max(largo, 6), y + 74], radius=10, fill=col)
                    g.text((MARGEN * 2 + 172 + largo, y + 37), miles(v * crec), font=archivo(56, 700), fill=TINTA, anchor="lm")
                    y += 104
                y += 90
            g.text((MARGEN * 2, y), "INDECI · 2017: ene–may, Niño Costero", font=mono(36), fill=TENUE)
            g.text((MARGEN * 2, y + 52), "2023: ene–jun, todas las emergencias", font=mono(36), fill=TENUE)
            panel = lienzo.resize((W, H_VIS), Image.LANCZOS)
        if ub > 0:
            cam = camara(PIURA_CAM, caja(-80.95, -5.6, -79.3, -4.4, 0.05), (t - tpero) / (self.t1 - tpero))
            mapa = self.mapas.vista("oscuro", cam)
            img.paste(mapa if ub >= 1 else Image.blend(panel, mapa, ub), (0, Y_VIS))
            ul = ImageDraw.Draw(img, "RGBA")
            for j, (lon, lat) in enumerate(self.huaicos):
                u = (t - (thua - 0.4) - j * 0.004) / 0.25
                if u <= 0:
                    continue
                x, y = a_pantalla(cam, lon, lat)
                r = 6 * salida(u) + (4 * (1 - u) if u < 1 else 0)
                if Y_VIS < y < Y_VIS + H_VIS:
                    ul.ellipse([x - r, y - r, x + r, y + r], fill=(*HUAICO, 235), outline=HALO, width=2)
            uc = (t - tciu + 0.2) / 0.4
            if uc > 0:
                x, y = a_pantalla(cam, -80.632, -5.194)
                r = 26 + 40 * ((t - tciu) % 1.4) / 1.4
                ul.ellipse([x - r, y - r, x + r, y + r], outline=(*ORO, round(255 * (1 - ((t - tciu) % 1.4) / 1.4))), width=5)
                ul.ellipse([x - 22, y - 22, x + 22, y + 22], outline=ORO, width=5)
            rotular(ul, cam, {"Piura", "Chulucanas", "Huancabamba", "Ayabaca"}, salida(ub))
        else:
            img.paste(panel, (0, Y_VIS))
        if t < tciu - 0.2:
            v = -67 * salida((t - tbaj + 0.2) / 1.2)
            self.cifra(d, f"−{entero(abs(v))} %" if entero(abs(v)) else "0 %", "Damnificados en Piura, 2023 frente a 2017", (t - self.t0) / 0.5, E23)
        elif t < thua - 0.2:
            e = self.R["edificios"]
            self.cifra(d, f"{e['gfm2017']} de {miles(e['afectado_2017'])}", "Edificios afectados en 2017 que el radar vio con agua (ciudad de Piura y Bajo Piura)", 1.0, ORO)
        else:
            h = self.R["huaicos"]
            self.cifra(d, f"0 de {h['huaicos']}", "Huaicos de INGEMMET con agua del radar", 1.0, HUAICO)

    # 6. Cierre: el dashboard en un celular
    def e_cierre(self, img, d, t):
        ph, pw = H_VIS - 30, round((H_VIS - 30) * 9 / 16)
        vistas = pantallas(pw, ph)
        x0, y0 = (W - pw) // 2, Y_VIS + 10
        d.rounded_rectangle([x0 - 14, y0 - 14, x0 + pw + 14, y0 + ph + 14], radius=56, fill=(8, 9, 22), outline=(107, 116, 184), width=4)
        tramo = max((self.t1 - self.t0 - 0.4) / len(vistas), 0.8)
        k = min(int((t - self.t0) / tramo), len(vistas) - 1)
        u = ((t - self.t0) - k * tramo) / 0.45
        pant = vistas[k]
        if k > 0 and u < 1:
            dy = round(ph * salida(u))
            pant = Image.new("RGB", (pw, ph))
            pant.paste(vistas[k - 1].crop((0, dy, pw, ph)), (0, 0))
            pant.paste(vistas[k].crop((0, 0, pw, dy)), (0, ph - dy))
        mask = Image.new("L", (pw, ph), 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, pw - 1, ph - 1], radius=44, fill=255)
        img.paste(pant, (x0, y0), mask)
        self.cifra(d, "Piura bajo el agua", URL, (t - self.t0) / 0.5)


@lru_cache(maxsize=None)
def pantallas(pw, ph):
    """Capturas del dashboard publicado, a la medida de la pantalla del celular."""
    return [Image.open(REC / f"dash_{n}.png").convert("RGB").resize((pw, ph), Image.LANCZOS)
            for n in ("portada", "agua", "explorar")]


FRASE = ("Los desastres naturales pasan,", "los datos quedan.")


def tarjeta_final(img, d, tf):
    """Cierre con la música sola: primero la frase final; después, escalonados, el título, el autor y los créditos
    (aviso de voz con IA, fuentes, imágenes y música). `tf` son los segundos desde que terminó la narración."""
    d.rectangle([0, Y_VIS - 300, W, H], fill=NOCHE)
    u = salida(tf / 0.7)
    f = ajustar(FRASE[0], 72)
    y = 196
    d.text((MARGEN, y), FRASE[0], font=f, fill=mezclar(NOCHE, (255, 255, 255), u))
    y += f.getmetrics()[0] + 24
    d.text((MARGEN, y), FRASE[1], font=f, fill=mezclar(NOCHE, ORO, u))
    y += f.getmetrics()[0] + 50
    resto = lambda k=0: salida((tf - 1.2 - k * 0.12) / 0.6)   # el resto entra 1,2 s después de la frase
    d.line([(MARGEN, y), (MARGEN + 140, y)], fill=mezclar(NOCHE, ACENTO, resto()), width=4)
    y += 46
    d.text((MARGEN, y), "Piura bajo el agua", font=archivo(80, 800), fill=mezclar(NOCHE, (255, 255, 255), resto()))
    y += 100
    d.text((MARGEN, y), "Dos Niños costeros medidos desde el espacio", font=archivo(38, 500, 100), fill=mezclar(NOCHE, ACENTO, resto()))
    y += 70
    d.text((MARGEN, y), "Cristian Wong P.", font=archivo(72, 800), fill=mezclar(NOCHE, ORO, resto(1)))
    y += 120
    bloques = [("Voz", "Generada con IA (Qwen3-TTS) a partir de una grabación de mi propia voz"),
               ("Datos", "Copernicus GFM (Sentinel-1), Copernicus EMS, INDECI, INGEMMET e INEI"),
               ("Imágenes", "Esri World Imagery (Esri, Maxar, Earthstar Geographics) y capturas del dashboard"),
               ("Música", "«Floating Cities», Kevin MacLeod (incompetech.com), licencia CC BY 4.0"),
               ("Dashboard", URL)]
    for k, (titulo, txt) in enumerate(bloques):
        uu = resto(k + 2)
        d.text((MARGEN, y), titulo.upper(), font=F_KICK, fill=mezclar(NOCHE, ACENTO, uu))
        y += 38
        for linea in envolver(txt, archivo(34, 500, 100), W - 2 * MARGEN):
            d.text((MARGEN, y), linea, font=archivo(34, 500, 100), fill=mezclar(NOCHE, TINTA, uu))
            y += 43
        y += 24
    d.text((MARGEN, 1812), "Diplomado de Ciencia de Datos con Python · Tarea 3", font=F_CRED, fill=mezclar(NOCHE, TENUE, resto()))


# ---------- Capas comunes ----------
def marco_comun(img, t, escenas, activa, final):
    d = ImageDraw.Draw(img, "RGBA")
    # Fundidos del visual hacia la noche, arriba y abajo
    for y, sube in ((Y_VIS, True), (Y_VIS + H_VIS - 90, False)):
        for j in range(90):
            a = round(220 * ((90 - j) / 90 if sube else j / 90) ** 2)
            d.line([(0, y + j), (W, y + j)], fill=(*NOCHE, a))
    d.rectangle([0, 0, W, 140], fill=NOCHE)
    d.text((MARGEN, 52), "PIURA BAJO EL AGUA", font=F_KICK, fill=ACENTO)
    d.text((W - MARGEN, 52), "NIÑO COSTERO 2017 · 2023", font=F_KICK, fill=TENUE, anchor="ra")
    hueco, x = 8, MARGEN
    ancho = (W - 2 * MARGEN - hueco * (len(escenas) - 1)) / len(escenas)
    for k, e in enumerate(escenas):
        u = 1.0 if final else acotar((t - e.t0) / (e.t1 - e.t0))
        d.rounded_rectangle([x, 104, x + ancho, 110], radius=3, fill=LINEA)
        if u > 0:
            d.rounded_rectangle([x, 104, x + max(ancho * u, 6), 110], radius=3, fill=ACENTO if k == activa or final else (*ACENTO, 150))
        x += ancho + hueco
    # Aviso de voz con IA (siempre visible) y crédito de la escena
    pastilla(d, (MARGEN, 1745), "VOZ GENERADA CON IA", F_TAG, (*NOCHE2, 255), ORO)
    if not final:
        y = 1808
        for linea in envolver(escenas[activa].e["credito"], F_CRED, W - 2 * MARGEN)[:2]:
            d.text((MARGEN, y), linea, font=F_CRED, fill=TENUE)
            y += 32


def unir_miles(palabras):
    """Junta «90» y «000» en una sola palabra de subtítulo («90 000»)."""
    out = []
    for p in palabras:
        if out and re.fullmatch(r"\d{3}[.,:;]?", p["w"]) and re.fullmatch(r"\d{1,3}", out[-1]["w"]):
            out[-1] = {"w": out[-1]["w"] + " " + p["w"], "i": out[-1]["i"], "f": p["f"]}
        else:
            out.append(dict(p))
    return out


def bloques(palabras):
    """Subtítulos de hasta 4 palabras o 24 caracteres, cortando en la puntuación."""
    out, actual = [], []
    for p in palabras:
        actual.append(p)
        texto = " ".join(q["w"] for q in actual)
        if len(actual) >= 4 or len(texto) >= 24 or re.search(r"[.,;:!?]$", p["w"]):
            out.append(actual)
            actual = []
    return out + ([actual] if actual else [])


def dibujar_subtitulo(img, bloque, t):
    d = ImageDraw.Draw(img)
    lineas, linea = [], []
    for p in bloque:
        if linea and F_SUB.getlength(" ".join(q["w"] for q in linea + [p])) > W - 2 * MARGEN:
            lineas.append(linea)
            linea = []
        linea.append(p)
    lineas.append(linea)
    alto = 80
    y = Y_SUB - alto * len(lineas) / 2
    esp = F_SUB.getlength(" ")
    for linea in lineas:
        x = (W - F_SUB.getlength(" ".join(p["w"] for p in linea))) / 2
        for k, p in enumerate(linea):
            fin = linea[k + 1]["i"] if k + 1 < len(linea) else p["f"] + 0.25
            suena = p["i"] <= t < max(fin, p["f"])
            d.text((x, y), p["w"], font=F_SUB, fill=ORO if suena else (255, 255, 255), stroke_width=7, stroke_fill=HALO)
            x += F_SUB.getlength(p["w"]) + esp
        y += alto


# ---------- Audio ----------
def lufs(ff, entrada, filtro=None, dur=None):
    cmd = [ff, "-hide_banner", "-nostats", "-i", str(entrada)]
    if dur:
        cmd += ["-t", str(dur)]
    cmd += ["-af", (filtro + "," if filtro else "") + "loudnorm=print_format=json", "-f", "null", "-"]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return float(json.loads(r.stderr[r.stderr.rindex("{"):r.stderr.rindex("}") + 1])["input_i"])


def filtro_audio(ff, fin_voz, velocidad):
    """Voz a −14 LUFS (compresión, ganancia exacta y limitador) y música de fondo 16 dB por debajo; en los créditos
    la música sube a −18 LUFS. La música entra y sale con fundidos. La voz se acelera si hace falta (atempo)."""
    previo = "acompressor=threshold=-24dB:ratio=4:attack=2:release=80,alimiter=limit=0.35:attack=1:release=50:level=false"
    voz = f"atempo={velocidad:.4f},{previo},volume={-14 - lufs(ff, SAL / 'reel.wav', previo):.2f}dB"
    musica = lufs(ff, REC / "floating_cities.mp3", dur=DURACION)
    g1, g2 = 10 ** ((-30 - musica) / 20), 10 ** ((-18 - musica) / 20)
    return (f"[1:a]{voz},apad=whole_dur={DURACION}[v];"
            f"[2:a]atrim=0:{DURACION},asetpts=PTS-STARTPTS,"
            f"volume='{g1:.4f}+({g2:.4f}-{g1:.4f})*clip((t-{fin_voz:.2f})/1.5,0,1)':eval=frame,"
            f"afade=t=in:d=1.2,afade=t=out:st={DURACION - 2:.2f}:d=2[m];"
            "[v][m]amix=inputs=2:normalize=0:duration=first,alimiter=limit=0.84:attack=1:release=50:level=false[a]")


def srt_tiempo(s):
    ms = round(s * 1000)
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def portada(escenas):
    """Portada para LinkedIn: Sechura resaltado, con el título."""
    k = 2
    img = escenas[k].render(escenas[k].t1 - 0.1)
    marco_comun(img, escenas[k].t1 - 0.1, escenas, k, False)
    d = ImageDraw.Draw(img, "RGBA")
    d.rectangle([0, 140, W, Y_VIS + 20], fill=NOCHE)
    titulo = ajustar("Piura bajo el agua", 118)
    d.text((MARGEN, 175), "Piura bajo el agua", font=titulo, fill=(255, 255, 255))
    d.text((MARGEN, 175 + titulo.getmetrics()[0] + 34), "Dos Niños costeros medidos desde el espacio", font=F_ETIQ, fill=ACENTO)
    d.rectangle([0, Y_VIS + H_VIS - 10, W, 1740], fill=NOCHE)
    d.text((MARGEN, 1520), "Cristian Wong P.", font=archivo(70, 800), fill=ORO)
    d.text((MARGEN, 1612), "Radar Sentinel-1 · 2017 y 2023", font=F_ETIQ, fill=TINTA)
    img.save(AQUI / "portada.png")


def main():
    t_ini = time.time()
    guion = json.loads((AQUI / "guion.json").read_text(encoding="utf-8"))
    tiempos = json.loads((SAL / "tiempos.json").read_text(encoding="utf-8"))
    # Si la narración no deja al menos CREDITOS segundos al final, se acelera lo justo y se escalan todos los tiempos
    velocidad = max(1.0, (tiempos["escenas"][-1]["fin"] + 0.6) / (DURACION - CREDITOS))
    if velocidad > MAX_VELOCIDAD:
        sys.exit(f"La narración dura {tiempos['escenas'][-1]['fin']:.1f} s: acorta guion.json (no cabe ni acelerando un 7 %).")
    for e in tiempos["escenas"]:
        e["inicio"], e["fin"] = e["inicio"] / velocidad, e["fin"] / velocidad
        e["palabras"] = unir_miles([{**p, "i": p["i"] / velocidad, "f": p["f"] / velocidad} for p in e["palabras"]])
    esc_t = tiempos["escenas"]
    fin_voz = esc_t[-1]["fin"] + 0.6
    cortes = [0.0] + [(esc_t[k - 1]["fin"] + esc_t[k]["inicio"]) / 2 for k in range(1, len(esc_t))] + [fin_voz]
    R, serie, huaicos = datos()
    mapas = Mapas()
    escenas = [Escena(k, e, tiempos, cortes, mapas, R, serie, huaicos) for k, e in enumerate(guion)]
    print(f"Narración: {esc_t[-1]['fin']:.1f} s (velocidad ×{velocidad:.3f}) · créditos desde {fin_voz:.1f} s · preparación {time.time() - t_ini:.0f} s")

    subs = []
    for esc in esc_t:
        bl = bloques(esc["palabras"])
        for j, b in enumerate(bl):
            fin = bl[j + 1][0]["i"] if j + 1 < len(bl) else b[-1]["f"] + 0.35
            subs.append((b[0]["i"], fin, b))

    def cuadro(t):
        if t >= fin_voz:
            img = escenas[-1].render(fin_voz - 0.01)
            d = ImageDraw.Draw(img, "RGBA")
            marco_comun(img, t, escenas, len(escenas) - 1, True)
            tarjeta_final(img, d, t - fin_voz)
            pastilla(d, (MARGEN, 1745), "VOZ GENERADA CON IA", F_TAG, (*NOCHE2, 255), ORO)
            return img
        k = max(j for j, e in enumerate(escenas) if e.t0 - FUNDIDO / 2 <= t or j == 0)
        img = escenas[k].render(t)
        if k > 0 and t < escenas[k].t0 + FUNDIDO / 2:
            img = Image.blend(escenas[k - 1].render(t), img, (t - escenas[k].t0 + FUNDIDO / 2) / FUNDIDO)
        marco_comun(img, t, escenas, k, False)
        activo = next((s for s in subs if s[0] <= t < s[1]), None)
        if activo:
            dibujar_subtitulo(img, activo[2], t)
        return img

    if sys.argv[1:] == ["portada"]:
        portada(escenas)
        print("portada.png lista")
        return
    if len(sys.argv) > 1:   # solo muestras
        (SAL / "muestras").mkdir(exist_ok=True)
        for v in sys.argv[1:]:
            cuadro(float(v)).save(SAL / "muestras" / f"t{float(v):05.1f}.png")
        print("muestras listas")
        return

    with open(AQUI / "reel.srt", "w", encoding="utf-8") as f:
        for n, (i, fin, b) in enumerate(subs, 1):
            f.write(f"{n}\n{srt_tiempo(i)} --> {srt_tiempo(fin)}\n{' '.join(p['w'] for p in b)}\n\n")

    ff = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [ff, "-y", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-i", str(SAL / "reel.wav"), "-i", str(REC / "floating_cities.mp3"),
           "-filter_complex", filtro_audio(ff, fin_voz, velocidad), "-map", "0:v", "-map", "[a]",
           "-ar", "48000", "-c:a", "aac", "-b:a", "128k",
           # Tope de 1,1 Mb/s: el video queda bajo 10 MB, el límite de GitHub y cómodo para LinkedIn
           "-c:v", "libx264", "-preset", "slow", "-crf", "23", "-maxrate", "1100k", "-bufsize", "2200k", "-pix_fmt", "yuv420p",
           "-movflags", "+faststart", "-t", str(DURACION), str(AQUI / "reel.mp4")]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for n in range(round(DURACION * FPS)):
        proc.stdin.write(cuadro(n / FPS).tobytes())
        if n % 300 == 0:
            print(f"  {n / FPS:4.1f} s de {DURACION:.0f}", flush=True)
    proc.stdin.close()
    if proc.wait() != 0:
        sys.exit("ffmpeg falló")

    portada(escenas)
    mb = (AQUI / "reel.mp4").stat().st_size / 1e6
    print(f"reel.mp4: {DURACION:.0f} s, {mb:.1f} MB · reel.srt: {len(subs)} subtítulos · portada.png ({time.time() - t_ini:.0f} s)")


if __name__ == "__main__":
    main()
