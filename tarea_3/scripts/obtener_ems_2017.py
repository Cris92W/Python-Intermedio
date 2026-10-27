"""Mapas oficiales de Copernicus EMS para las inundaciones de 2017 en Perú (activación EMSR199).

    .venv/Scripts/python.exe scripts/obtener_ems_2017.py

Copernicus EMS (servicio de mapeo rápido de emergencias de la UE) se activó el 22 de marzo de 2017 a
pedido de DG ECHO. Sus analistas delimitaron a mano el área inundada (DELINEATION) y el grado de daño
en edificios y vías (GRADING) sobre imágenes de alta resolución. Son la referencia para validar GFM.

Baja los paquetes vectoriales de cada área (AOI) a datos/originales/copernicus_ems_2017/, salvo
Iquitos, que está fuera del estudio. Página de la activación:
https://mapping.emergency.copernicus.eu/activations/EMSR199/
"""
import re
import time
from pathlib import Path

import requests

BASE = Path(__file__).resolve().parent.parent
DESTINO = BASE / "datos" / "originales" / "copernicus_ems_2017"
PAGINA = "https://mapping.emergency.copernicus.eu/activations/EMSR199/"
FUERA_DEL_ESTUDIO = ("09IQUITOS",)
CABECERAS = {"User-Agent": "tarea3-unmsm (https://github.com/Cris92W/Python-Intermedio)"}


def main():
    html = requests.get(PAGINA, headers=CABECERAS, timeout=60).text
    urls = sorted(set(re.findall(r"https://[^\"']+/EMSR199_[^\"']+_vector\.zip", html)))
    urls = [u for u in urls if not any(f in u for f in FUERA_DEL_ESTUDIO)]
    DESTINO.mkdir(parents=True, exist_ok=True)

    for url in urls:
        archivo = DESTINO / url.rsplit("/", 1)[1]
        if not archivo.exists():
            r = requests.get(url, headers=CABECERAS, timeout=300)
            r.raise_for_status()
            archivo.write_bytes(r.content)
            time.sleep(1)
        print(f"{archivo.name}  {archivo.stat().st_size / 1e6:.1f} MB")
    print(f"{len(urls)} paquetes en {DESTINO}")


if __name__ == "__main__":
    main()
