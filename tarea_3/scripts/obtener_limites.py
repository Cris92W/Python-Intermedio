"""Límites distritales de los 5 departamentos del estudio (Piura, Lambayeque, La Libertad, Áncash y Lima).

    .venv/Scripts/python.exe scripts/obtener_limites.py

Fuente: límite distrital INEI 2020 (1874 distritos), redistribuido por GeoGPS Perú y publicado
en el dataset del curso en Hugging Face (aquiro1994/ds-python-up, _data/LIMITE_DISTRITAL_2020_INEI.zip).
Lima es el departamento 15 (Lima Metropolitana y Lima Provincias); el Callao (07) queda fuera.

Escribe:
- datos/procesados/distritos_estudio.gpkg: un polígono por distrito con UBIGEO, nombres y área en km².
- datos/procesados/departamentos_estudio.geojson: los 5 departamentos disueltos y simplificados
  (para el área de búsqueda de imágenes y para la web).
"""
from pathlib import Path

import geopandas as gpd
import requests

BASE = Path(__file__).resolve().parent.parent
ORIG = BASE / "datos" / "originales" / "limites_inei"
PROC = BASE / "datos" / "procesados"
URL = ("https://huggingface.co/datasets/aquiro1994/ds-python-up/resolve/main/"
       "_data/LIMITE_DISTRITAL_2020_INEI.zip")
ZIP = ORIG / "LIMITE_DISTRITAL_2020_INEI.zip"

DEPARTAMENTOS = {"02": "ÁNCASH", "13": "LA LIBERTAD", "14": "LAMBAYEQUE", "15": "LIMA", "20": "PIURA"}
# Albers equal-area de Sudamérica: las áreas no se calculan en EPSG:4326.
CRS_AREA = "ESRI:102033"


def descargar():
    if ZIP.exists():
        return
    ORIG.mkdir(parents=True, exist_ok=True)
    r = requests.get(URL, timeout=300,
                     headers={"User-Agent": "tarea3-unmsm (https://github.com/Cris92W/Python-Intermedio)"})
    r.raise_for_status()
    ZIP.write_bytes(r.content)


def main():
    descargar()
    distritos = gpd.read_file(f"zip://{ZIP.as_posix()}")
    distritos = distritos[distritos["CCDD"].isin(DEPARTAMENTOS)].copy()
    distritos = distritos[["UBIGEO", "CCDD", "NOMBDEP", "NOMBPROV", "NOMBDIST", "geometry"]]
    distritos["NOMBDEP"] = distritos["CCDD"].map(DEPARTAMENTOS)
    distritos["area_km2"] = distritos.to_crs(CRS_AREA).area / 1e6
    distritos = distritos.sort_values("UBIGEO").reset_index(drop=True)

    PROC.mkdir(parents=True, exist_ok=True)
    distritos.to_file(PROC / "distritos_estudio.gpkg", layer="distritos", driver="GPKG")

    departamentos = distritos.dissolve(by=["CCDD", "NOMBDEP"], as_index=False, aggfunc={"area_km2": "sum"})
    departamentos["n_distritos"] = distritos.groupby("CCDD").size().reindex(departamentos["CCDD"]).values
    departamentos["geometry"] = departamentos.geometry.simplify(0.002, preserve_topology=True)
    departamentos.to_file(PROC / "departamentos_estudio.geojson", driver="GeoJSON")

    print(departamentos[["CCDD", "NOMBDEP", "n_distritos", "area_km2"]].round(0).to_string(index=False))
    print(f"Total: {len(distritos)} distritos, {distritos['area_km2'].sum():,.0f} km²")


if __name__ == "__main__":
    main()
