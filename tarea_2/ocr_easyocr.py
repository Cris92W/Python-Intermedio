"""Parte 2, paso 4 (documentos): OCR alternativo, EasyOCR (CRAFT + CRNN, idioma es) en CPU, sobre los mismos 10 documentos.

Por qué EasyOCR: Tesseract necesita un instalador de Windows con permisos de administrador; EasyOCR se instala con pip
y es otra familia de modelos (detector CRAFT y reconocedor CRNN, entrenados por JaidedAI), distinta de PP-OCR.
Corre en un entorno aparte porque trae opencv-python-headless, que choca con el OpenCV de PaddleOCR.

Mismo preprocesamiento que la Parte 1: lado mayor a 2000 px como máximo. Las cajas se ordenan en renglones de arriba
abajo y, dentro de cada renglón, de izquierda a derecha. Guarda una línea JSON por documento en
datos/raw/evaluacion/ocr_easyocr.jsonl. La configuración queda fija antes de ver ninguna métrica.

Uso (desde tarea_2):
  uv run --no-project --python 3.12 --with easyocr==1.7.2 --with pandas python ocr_easyocr.py
"""
import json
import statistics
import sys
import time
from pathlib import Path

import easyocr
import numpy as np
import pandas as pd
from PIL import Image

sys.stdout.reconfigure(encoding="utf-8")

T2 = Path(__file__).resolve().parent
MUESTRA = T2 / "datos" / "raw" / "muestra_evaluacion"
DIR_MODELOS = T2 / "datos" / "raw" / "modelos" / "easyocr"
SALIDA = T2 / "datos" / "raw" / "evaluacion" / "ocr_easyocr.jsonl"
LADO_MAX = 2000
CONFIG = f"EasyOCR {easyocr.__version__} (CRAFT + CRNN latin, lang=es, CPU, lado máx. {LADO_MAX} px, orden por renglones)"


def renglones(resultado):
    """Cajas de EasyOCR -> texto en orden de lectura: un renglón por línea."""
    cajas = []
    for caja, texto, conf in resultado:
        ys = [p[1] for p in caja]
        cajas.append(((min(ys) + max(ys)) / 2, max(ys) - min(ys), min(p[0] for p in caja), texto, conf))
    if not cajas:
        return "", None
    tolerancia = statistics.median(c[1] for c in cajas) / 2
    lineas, actual, y_actual = [], [], None
    for c in sorted(cajas):
        if y_actual is not None and c[0] - y_actual > tolerancia:
            lineas.append(actual)
            actual = []
        actual.append(c)
        y_actual = statistics.mean(x[0] for x in actual)
    lineas.append(actual)
    texto = "\n".join(" ".join(c[3] for c in sorted(l, key=lambda c: c[2])) for l in lineas)
    return texto, round(statistics.mean(c[4] for c in cajas), 4)


def main():
    ids = pd.read_csv(MUESTRA / "muestra.csv", sep=";", encoding="utf-8-sig").query("modalidad == 'documento'")["id"]
    hechos = set()
    if SALIDA.exists():
        hechos = {json.loads(l)["id"] for l in SALIDA.read_text(encoding="utf-8").splitlines() if l.strip()}
    pendientes = [i for i in ids if i not in hechos]
    print(f"{len(hechos)} ya procesados, {len(pendientes)} por procesar", flush=True)
    if not pendientes:
        return

    DIR_MODELOS.mkdir(parents=True, exist_ok=True)
    lector = easyocr.Reader(["es"], gpu=False, model_storage_directory=str(DIR_MODELOS),
                            user_network_directory=str(DIR_MODELOS), verbose=False)
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    for id_ in pendientes:
        img = Image.open(MUESTRA / "documentos" / f"{id_}.jpg").convert("RGB")
        img.thumbnail((LADO_MAX, LADO_MAX))
        t0 = time.perf_counter()
        texto, conf = renglones(lector.readtext(np.array(img), detail=1, paragraph=False))
        seg = time.perf_counter() - t0
        fila = {"id": id_, "texto": texto, "confianza_media": conf, "segundos": round(seg, 1), "modelo_ocr": CONFIG}
        with SALIDA.open("a", encoding="utf-8") as f:
            f.write(json.dumps(fila, ensure_ascii=False) + "\n")
        print(f"{id_}: {len(texto)} caracteres en {seg:.0f} s", flush=True)


if __name__ == "__main__":
    main()
