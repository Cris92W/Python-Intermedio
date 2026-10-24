"""Paso 5 del flujo: arma reel.mp4 vertical con tu voz, subtítulos palabra por palabra y las imágenes de PRACTICA_1.

Uso (desde reel_chichas, después de voz.py):  .venv\\Scripts\\python video.py
Entradas: guion.json, salidas/reel.wav, salidas/tiempos.json y ../PRACTICA_1/salidas/web (imágenes y extra.json)
Salidas:  reel.mp4 (1080×1920, 30 fps, H.264 + AAC a −14 LUFS), reel.srt y portada.png

Pillow dibuja cada cuadro y ffmpeg (incluido en imageio-ffmpeg) lo convierte en video. Las animaciones
(cámara, focos, capas, contadores, poblados) se disparan con los tiempos de las palabras que midió Whisper.
"""
import json
import math
import re
import subprocess
import sys
import time
from functools import lru_cache
from pathlib import Path

import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.stdout.reconfigure(encoding="utf-8")

AQUI = Path(__file__).resolve().parent
SAL = AQUI / "salidas"
WEB = AQUI.parent / "PRACTICA_1" / "salidas" / "web"
W, H, FPS = 1080, 1920, 30
MARGEN = 60            # zona segura lateral; arriba y abajo van los botones de cada app
ANCHO = W - 2 * MARGEN
FUNDIDO = 0.3          # transición entre escenas, en segundos
Y_MAPA = 680           # arriba, franja oscura con las cifras; desde aquí, el mapa
ALTO_MAPA = H - Y_MAPA
Y_SUB = 1360           # centro vertical de los subtítulos
ANCHO_SUB = 900        # más angosto: a la derecha van los botones de la app
CENTRO_ZONA = (543, 573)   # en píxeles de la imagen Sentinel-2 (10 m)

# Paleta del informe: noche, tinta, celeste de laguna y fuego por fecha de detección
NOCHE, TINTA, TENUE, CELESTE = (8, 19, 28), (220, 230, 237), (160, 178, 191), (127, 208, 227)
FUEGO = {"2026-10-16": (249, 220, 92), "2026-10-17": (242, 160, 61), "2026-10-18": (224, 87, 44)}
NARANJA = (242, 160, 61)

FONTS = Path("C:/Windows/Fonts")


@lru_cache(maxsize=None)
def fuente(nombre, tam, variante=None):
    f = ImageFont.truetype(str(FONTS / nombre), tam)
    if variante:
        f.set_variation_by_name(variante)
    return f


F_KICKER = fuente("bahnschrift.ttf", 34, "SemiBold")
F_ETIQ = fuente("seguisb.ttf", 50)
F_CRED = fuente("segoeui.ttf", 28)
F_SUB = fuente("seguisb.ttf", 68)
F_TAG = fuente("seguisb.ttf", 30)
F_POB = fuente("seguisb.ttf", 34)


# Curvas de animación: u va de 0 a 1
def acotar(u):
    return min(max(u, 0.0), 1.0)


def suave(u):
    u = acotar(u)
    return u * u * (3 - 2 * u)


def salida(u):
    return 1 - (1 - acotar(u)) ** 3


def rebote(u):
    u = acotar(u)
    return 1 + 2.7 * (u - 1) ** 3 + 1.7 * (u - 1) ** 2


def miles(n):
    return f"{n:,}".replace(",", " ")


def limpiar(w):
    return re.sub(r"[^\w]", "", w.lower())


def ajustar(texto, tam_max, ancho=ANCHO):
    """Bahnschrift Bold al mayor tamaño que quepa en el ancho."""
    for tam in range(tam_max, 40, -4):
        f = fuente("bahnschrift.ttf", tam, "Bold")
        if f.getlength(texto) <= ancho:
            return f
    return f


def envolver(texto, f, ancho=ANCHO):
    lineas, linea = [], ""
    for w in texto.split():
        prueba = f"{linea} {w}".strip()
        if f.getlength(prueba) <= ancho or not linea:
            linea = prueba
        else:
            lineas.append(linea)
            linea = w
    return lineas + ([linea] if linea else [])


@lru_cache(maxsize=512)
def img_fuego(texto, tam_max):
    """Texto con el degradado amarillo-naranja-rojo del informe, como imagen RGBA."""
    f = ajustar(texto, tam_max)
    _, _, x1, y1 = f.getbbox(texto)
    mask = Image.new("L", (x1, y1), 0)
    ImageDraw.Draw(mask).text((0, 0), texto, font=f, fill=255)
    a, b, c = (np.array(FUEGO[d], float) for d in sorted(FUEGO))
    u = np.linspace(0, 1, x1)[:, None]
    fila = np.where(u < 0.6, a + (b - a) * (u / 0.6), b + (c - b) * ((u - 0.6) / 0.4))
    grad = Image.fromarray(np.repeat(fila[None].astype(np.uint8), y1, axis=0), "RGB").convert("RGBA")
    grad.putalpha(mask)
    return grad


def pegar(lienzo, img, xy, alfa=1.0):
    """Pega una imagen RGBA sobre el lienzo RGB, con transparencia extra (0–1)."""
    if alfa <= 0:
        return
    mask = img.getchannel("A")
    if alfa < 1:
        mask = mask.point(lambda v: round(v * alfa))
    lienzo.paste(img, (round(xy[0]), round(xy[1])), mask)


def pastilla(d, xy, texto, f, fondo=(0, 0, 0, 170), color=TINTA, pad=(16, 8), alfa=1.0):
    x, y = xy
    _, _, x1, y1 = d.textbbox((x + pad[0], y + pad[1]), texto, font=f)
    d.rounded_rectangle([x, y, x1 + pad[0], y1 + pad[1] + 4], radius=10, fill=fondo[:3] + (round(fondo[3] * alfa),))
    d.text((x + pad[0], y + pad[1]), texto, font=f, fill=color[:3] + (round(255 * alfa),))


def degradado(alto, desde, hasta, curva):
    capa = Image.new("RGBA", (W, alto), (0, 0, 0, 0))
    d = ImageDraw.Draw(capa)
    for y in range(alto):
        d.line([(0, y), (W, y)], fill=NOCHE + (round(255 * (desde + (hasta - desde) * (y / alto) ** curva)),))
    return capa


# Funde el borde superior del mapa con la franja oscura y oscurece abajo para los subtítulos
GRAD_ARRIBA = degradado(140, 1.0, 0.0, 0.6)
GRAD_ABAJO = degradado(H - 1180, 0.0, 0.9, 1.2)


class Escena:
    """Una escena del guion entre dos cortes; render(t) dibuja el cuadro del instante t (en segundos del reel)."""

    def __init__(self, k, e, tiempos, cortes, dur, datos):
        self.k, self.e = k, e
        self.t0 = cortes[k]
        self.t1 = cortes[k + 1] if k + 1 < len(cortes) else dur
        self.palabras = tiempos["escenas"][k]["palabras"]
        self.base = Image.open(WEB / f"rgb_{e['fondo']}.jpg").convert("RGB")

        # Capas de la práctica (cicatriz por fecha o severidad), cada una con su máscara y su momento de aparición
        self.capas = []
        for c in e.get("capas", []):
            arr = np.array(Image.open(WEB / f"{c['img']}.png").convert("RGBA").resize(self.base.size, Image.NEAREST))
            sel = arr[..., 3] > 0
            if c.get("color"):
                sel &= (arr[..., :3] == c["color"]).all(-1)
            mask = Image.fromarray(np.where(sel, arr[..., 3], 0).astype(np.uint8), "L")
            t = self.momento(c["palabra"]) if c.get("palabra") else -math.inf
            self.capas.append((Image.fromarray(arr[..., :3], "RGB"), mask, t))
        self._cache = {}

        # Focos VIIRS en orden de detección; si hay focos_desde, aparecen uno a uno en focos_dur segundos
        fs = sorted((f for f in datos["focos"] if f["d"] in e.get("focos", [])), key=lambda f: (f["d"], f["t"]))
        if "focos_desde" in e:
            ini, paso = self.momento(e["focos_desde"]), e["focos_dur"] / max(len(fs) - 1, 1)
            self.focos = [(f, ini + j * paso) for j, f in enumerate(fs)]
        else:
            self.focos = [(f, -math.inf) for f in fs]

        self.poblados = [(next(l for l in datos["osm"]["lugares"] if l["nombre"] == n), self.momento(n))
                         for n in e.get("poblados", [])]

    def momento(self, palabra):
        """Instante en que la voz dice esa palabra; sin palabra, poco después del corte."""
        if palabra is None:
            return self.t0 + 0.3
        clave = limpiar(palabra)
        return next(p["i"] for p in self.palabras if limpiar(p["w"]) == clave)

    def camara(self, t):
        cams = self.e.get("camara", [[1.0, *CENTRO_ZONA]])
        if len(cams) == 1:
            return cams[0]
        u = suave((t - self.t0) / self.e.get("camara_dur", self.t1 - self.t0))
        return [a + (b - a) * u for a, b in zip(cams[0], cams[1])]

    def imagen(self, t):
        """Imagen Sentinel-2 con las capas visibles en t (en caché por nivel de transparencia)."""
        alfas = tuple(round(salida((t - tc) / 0.5) * 20) / 20 for _, _, tc in self.capas)
        if alfas not in self._cache:
            img = self.base.copy()
            for (rgb, mask, _), a in zip(self.capas, alfas):
                if a > 0:
                    img.paste(rgb, (0, 0), mask if a >= 1 else mask.point(lambda v: round(v * a)))
            self._cache[alfas] = img
        return self._cache[alfas]

    def cifra(self, t):
        """Cifra (con contador animado) y etiqueta en t, y desde cuándo se muestra esa etiqueta."""
        c = self.e.get("contar")
        if not c:
            return self.e["cifra"], self.e["etiqueta"], self.t0
        valor, etiqueta, cambio = c["desde"], self.e["etiqueta"], self.t0
        for paso in c["pasos"]:
            tp = self.momento(paso["palabra"])
            if t < tp:
                break
            u = acotar((t - tp) / paso["dur"])
            valor += (paso["valor"] - valor) * (u if c.get("curva") == "lineal" else salida(u))
            if "etiqueta" in paso:
                etiqueta, cambio = paso["etiqueta"], tp
        return c["formato"].format(miles(round(valor))), etiqueta, cambio

    def render(self, t, barra):
        # Lienzo RGB y ImageDraw en modo RGBA: así los colores con transparencia se mezclan con lo de abajo
        lienzo = Image.new("RGB", (W, H), NOCHE)

        # Mapa con cámara en movimiento
        z, cx, cy = self.camara(t)
        img = self.imagen(t)
        s = ALTO_MAPA / img.height * z
        ws, hs = W / s, ALTO_MAPA / s
        x0 = min(max(cx - ws / 2, 0), img.width - ws)
        y0 = min(max(cy - hs / 2, 0), img.height - hs)
        lienzo.paste(img.resize((W, ALTO_MAPA), Image.BILINEAR, box=(x0, y0, x0 + ws, y0 + hs)), (0, Y_MAPA))
        pant = lambda x, y: ((x / 10 - x0) * s, (y / 10 - y0) * s + Y_MAPA)   # m desde la esquina NO -> pantalla

        d = ImageDraw.Draw(lienzo, "RGBA")
        r0 = self.e.get("radio", 8)
        for f, ta in self.focos:
            if t < ta:
                continue
            x, y = pant(f["x"], f["y"])
            if self.e.get("pulso"):
                fase = ((t - ta) % 1.4) / 1.4
                rr = r0 + 6 + 40 * fase
                d.ellipse([x - rr, y - rr, x + rr, y + rr], outline=FUEGO[f["d"]] + (round(220 * (1 - fase)),), width=4)
            r = r0 * (rebote((t - ta) / 0.35) if ta > -math.inf else 1)
            d.ellipse([x - r, y - r, x + r, y + r], fill=FUEGO[f["d"]] + (255,), outline=NOCHE + (255,), width=2)

        # Poblados: se encienden cuando la voz los nombra; etiquetas alternadas abajo y arriba para que no se tapen
        for j, (lugar, tp) in enumerate(self.poblados):
            if t < tp:
                continue
            x, y = pant(lugar["x"], lugar["y"])
            fase = ((t - tp) % 1.6) / 1.6
            rr = 18 + 46 * fase
            d.ellipse([x - rr, y - rr, x + rr, y + rr], outline=(255, 255, 255, round(230 * (1 - fase))), width=4)
            r = 14 * rebote((t - tp) / 0.35)
            d.ellipse([x - r, y - r, x + r, y + r], fill=(255, 255, 255, 255), outline=NOCHE + (255,), width=4)
            texto = f"{lugar['nombre']} · {lugar['dist_km'] * 1000:.0f} m"
            ancho = F_POB.getlength(texto) + 32
            a = salida((t - tp) / 0.4)
            px = min(max(x - ancho / 2, MARGEN), W - MARGEN - ancho)
            py = (y + 24 if j % 2 == 0 else y - 82) + 16 * (1 - a)
            pastilla(d, (px, py), texto, F_POB, fondo=(8, 19, 28, 225), color=(255, 255, 255), alfa=a)
        pegar(lienzo, GRAD_ARRIBA, (0, Y_MAPA))
        pegar(lienzo, GRAD_ABAJO, (0, 1180))

        # Franja de texto: barra de avance, cifra con contador y etiqueta que entran deslizándose
        d = ImageDraw.Draw(lienzo, "RGBA")
        n = len(barra)
        seg = (ANCHO - 8 * (n - 1)) / n
        for j, (a, b) in enumerate(barra):
            xa = MARGEN + j * (seg + 8)
            d.rounded_rectangle([xa, 196, xa + seg, 202], radius=3, fill=(255, 255, 255, 70))
            u = acotar((t - a) / (b - a))
            if u > 0:
                d.rounded_rectangle([xa, 196, xa + max(seg * u, 6), 202], radius=3, fill=NARANJA + (255,))
        d.text((MARGEN, 236), "INCENDIO DE CHICHAS · AREQUIPA · OCT 2026", font=F_KICKER, fill=CELESTE)

        tau = t - self.t0
        cifra, etiqueta, cambio = self.cifra(t)
        a = salida(tau / 0.45)
        grande = img_fuego(cifra, 170) if cifra else img_fuego("Cristian Wong P.", 120)
        pegar(lienzo, grande, (MARGEN - 4, 290 + 40 * (1 - a)), a)
        y = 290 + grande.height + 14
        a = salida((t - max(cambio, self.t0 + 0.15)) / 0.4)
        for linea in envolver(etiqueta, F_ETIQ):
            d.text((MARGEN - 30 * (1 - a), y), linea, font=F_ETIQ, fill=(255, 255, 255, round(255 * a)))
            y += 62
        capa = Image.new("RGBA", (W, 160), (0, 0, 0, 0))
        dc = ImageDraw.Draw(capa)
        yc = 0
        for linea in envolver(self.e["credito"], F_CRED):
            dc.text((MARGEN, yc), linea, font=F_CRED, fill=TENUE)
            yc += 38
        pegar(lienzo, capa, (0, y + 12), salida((tau - 0.3) / 0.5))
        pastilla(d, (MARGEN, 1500), "Voz generada con IA", F_TAG)
        return lienzo


def bloques(palabras):
    """Agrupa las palabras de una escena en subtítulos de hasta 4 palabras, cortando en la puntuación."""
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
        prueba = " ".join(q["w"] for q in linea + [p])
        if linea and F_SUB.getlength(prueba) > ANCHO_SUB:
            lineas.append(linea)
            linea = []
        linea.append(p)
    lineas.append(linea)
    alto = 86
    y = Y_SUB - alto * len(lineas) / 2
    espacio = F_SUB.getlength(" ")
    for linea in lineas:
        x = (W - F_SUB.getlength(" ".join(p["w"] for p in linea))) / 2
        for k, p in enumerate(linea):
            fin = linea[k + 1]["i"] if k + 1 < len(linea) else p["f"] + 0.25
            suena = p["i"] <= t < max(fin, p["f"])
            d.text((x, y), p["w"], font=F_SUB, fill=NARANJA if suena else (255, 255, 255),
                   stroke_width=6, stroke_fill=(0, 0, 0))
            x += F_SUB.getlength(p["w"]) + espacio
        y += alto


def filtro_volumen(ff, wav):
    """Volumen de redes (−14 LUFS) con picos bajo −1,5 dB: limitar picos, medir, subir la ganancia justa y limitar al final.
    loudnorm solo no llega: los picos de la voz topan el límite y el audio queda cerca de −16 LUFS."""
    previo = "acompressor=threshold=-24dB:ratio=4:attack=2:release=80,alimiter=limit=0.35:attack=1:release=50:level=false"
    r = subprocess.run([ff, "-hide_banner", "-nostats", "-i", str(wav),
                        "-af", f"{previo},loudnorm=print_format=json", "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    medido = float(json.loads(r.stderr[r.stderr.rindex("{"):r.stderr.rindex("}") + 1])["input_i"])
    return f"{previo},volume={-14 - medido:.2f}dB,alimiter=limit=0.84:attack=1:release=50:level=false"


def srt_tiempo(s):
    ms = round(s * 1000)
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def main():
    t0 = time.time()
    guion = json.loads((AQUI / "guion.json").read_text(encoding="utf-8"))
    tiempos = json.loads((SAL / "tiempos.json").read_text(encoding="utf-8"))
    datos = json.loads((WEB / "extra.json").read_text(encoding="utf-8"))
    dur = tiempos["duracion"]
    esc_t = tiempos["escenas"]

    # La escena k empieza a mitad del silencio que la separa de la anterior
    cortes = [0.0] + [(esc_t[k - 1]["fin"] + esc_t[k]["inicio"]) / 2 for k in range(1, len(esc_t))]
    escenas = [Escena(k, e, tiempos, cortes, dur, datos) for k, e in enumerate(guion)]
    barra = [(e.t0, e.t1) for e in escenas]

    subs = []   # (inicio, fin, palabras)
    for esc in esc_t:
        bl = bloques(esc["palabras"])
        for j, b in enumerate(bl):
            fin = bl[j + 1][0]["i"] if j + 1 < len(bl) else b[-1]["f"] + 0.35
            subs.append((b[0]["i"], fin, b))

    with open(AQUI / "reel.srt", "w", encoding="utf-8") as f:
        for n, (i, fin, b) in enumerate(subs, 1):
            f.write(f"{n}\n{srt_tiempo(i)} --> {srt_tiempo(fin)}\n{' '.join(p['w'] for p in b)}\n\n")

    ff = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [ff, "-y", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-i", str(SAL / "reel.wav"),
           "-af", filtro_volumen(ff, SAL / "reel.wav"), "-ar", "48000", "-c:a", "aac", "-b:a", "128k",
           # Tope de 1,1 Mb/s: con la cámara en movimiento, sin tope pasa de 10 MB, el límite de GitHub para videos
           "-c:v", "libx264", "-preset", "slow", "-crf", "23", "-maxrate", "1100k", "-bufsize", "2200k", "-pix_fmt", "yuv420p",
           "-movflags", "+faststart", "-shortest", str(AQUI / "reel.mp4")]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for n in range(round(dur * FPS)):
        t = n / FPS
        # Fundido centrado en cada corte
        k = max(j for j, e in enumerate(escenas) if e.t0 - FUNDIDO / 2 <= t or j == 0)
        frame = escenas[k].render(t, barra)
        if k > 0 and t < escenas[k].t0 + FUNDIDO / 2:
            previo = escenas[k - 1].render(t, barra)
            frame = Image.blend(previo, frame, (t - escenas[k].t0 + FUNDIDO / 2) / FUNDIDO)
        activo = next((s for s in subs if s[0] <= t < s[1]), None)
        if activo:
            dibujar_subtitulo(frame, activo[2], t)
        proc.stdin.write(frame.tobytes())
        if n % 300 == 0:
            print(f"  {t:4.1f} s de {dur:.1f}", flush=True)
    proc.stdin.close()
    if proc.wait() != 0:
        sys.exit("ffmpeg falló")

    # Portada: la cicatriz completa por fecha con el título del informe
    portada = escenas[2].render(escenas[2].t1 - 0.05, [(0, 1)] * len(escenas))
    d = ImageDraw.Draw(portada)
    d.rectangle([0, 1180, W, 1470], fill=NOCHE)
    y = 1205
    for linea in envolver("Tres días de fuego en la puna de Chichas", fuente("bahnschrift.ttf", 76, "Bold")):
        d.text((MARGEN, y), linea, font=fuente("bahnschrift.ttf", 76, "Bold"), fill=(255, 255, 255))
        y += 84
    d.text((MARGEN, y + 8), "Cristian Wong P. · Sentinel-2, NASA FIRMS y Python", font=F_CRED, fill=TENUE)
    portada.save(AQUI / "portada.png")

    mb = (AQUI / "reel.mp4").stat().st_size / 1e6
    print(f"reel.mp4: {dur:.1f} s, {mb:.1f} MB · reel.srt: {len(subs)} subtítulos · portada.png ({time.time() - t0:.0f} s)")


if __name__ == "__main__":
    main()
