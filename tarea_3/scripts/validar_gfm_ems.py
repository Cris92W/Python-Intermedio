"""¿Cuánto de la inundación que Copernicus EMS delimitó a mano en 2017 detectó el radar (GFM)?

    .venv/Scripts/python.exe scripts/validar_gfm_ems.py

Para cada área (AOI) de la activación EMSR199 dentro del estudio se comparan, sobre la grilla de 80 m
de GFM (datos/procesados/gfm_80m/2017_*.tif):
- EMS: unión de los polígonos "Flooded Area" y "Mudflow" de todas las versiones (inicial y monitoreo).
- GFM: píxeles con agua en al menos una fecha y en al menos dos fechas de dic-2016 a may-2017.

Métricas:
- deteccion_pct: % del área EMS que GFM también marcó (sensibilidad).
- gfm_fuera_pct: % del área GFM dentro del AOI que EMS no delimitó. No es necesariamente error: GFM
  cubre seis meses y EMS es una foto de pocos días; también incluye zonas que EMS no alcanzó a mapear.

Escribe datos/procesados/validacion_gfm_ems.csv.
"""
import glob
import re
import warnings
import zipfile
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import rasterize

warnings.filterwarnings("ignore", category=RuntimeWarning)
BASE = Path(__file__).resolve().parent.parent
ORIG = BASE / "datos" / "originales" / "copernicus_ems_2017"
PROC = BASE / "datos" / "procesados"


def capas_por_aoi():
    """{aoi: (polígono del AOI, polígonos de inundación/huaico)} con todas las versiones unidas."""
    aois = {}
    for zp in sorted(glob.glob(str(ORIG / "*DELINEATION*.zip")) + glob.glob(str(ORIG / "*GRADING*.zip"))):
        nombre = re.search(r"EMSR199_(\d{2}[A-Z]+)_", zp).group(1)
        nombres = zipfile.ZipFile(zp).namelist()
        aoi = [n for n in nombres if n.endswith("area_of_interest.shp")]
        crisis = [n for n in nombres if "crisis_information_poly" in n and n.endswith(".shp")]
        if not aoi or not crisis:
            continue
        a = gpd.read_file(f"zip://{zp}!{aoi[0]}").to_crs(4326)
        c = gpd.read_file(f"zip://{zp}!{crisis[0]}").to_crs(4326)
        c = c[c["interpret"].isin(["Flooded Area", "Mudflow"])]
        previo = aois.get(nombre, (None, []))
        poligono = a.union_all() if previo[0] is None else previo[0].union(a.union_all())
        aois[nombre] = (poligono, previo[1] + [c])
    return {k: (a, pd.concat(c, ignore_index=True)) for k, (a, c) in aois.items()}


def main():
    distritos = gpd.read_file(PROC / "distritos_estudio.gpkg")
    estudio = distritos.union_all()
    rasters = sorted((PROC / "gfm_80m").glob("2017_*.tif"))
    filas = []
    for nombre, (aoi, crisis) in capas_por_aoi().items():
        if not aoi.intersects(estudio) or crisis.empty:
            continue
        ems_px = gfm1 = gfm2 = inter1 = inter2 = aoi_px = 0
        for tif in rasters:
            with rasterio.open(tif) as ds:
                aoi_t = gpd.GeoSeries([aoi], crs=4326).to_crs(ds.crs).iloc[0]
                o, s, e, n = ds.bounds
                if not aoi_t.intersects(gpd.GeoSeries.from_xy([o, e], [s, n]).union_all().envelope):
                    continue
                ventana = rasterio.windows.from_bounds(*aoi_t.bounds, transform=ds.transform)
                ventana = ventana.round_offsets().round_lengths().intersection(
                    rasterio.windows.Window(0, 0, ds.width, ds.height))
                frec = ds.read(1, window=ventana)
                t = ds.window_transform(ventana)
                forma = frec.shape
                m_aoi = rasterize([(aoi_t, 1)], out_shape=forma, transform=t, dtype="uint8").astype(bool)
                m_ems = rasterize(((g, 1) for g in crisis.to_crs(ds.crs).geometry), out_shape=forma,
                                  transform=t, dtype="uint8").astype(bool) & m_aoi
                pixel = abs(t.a * t.e) / 1e6
                g1, g2 = (frec >= 1) & m_aoi, (frec >= 2) & m_aoi
                aoi_px += m_aoi.sum() * pixel
                ems_px += m_ems.sum() * pixel
                gfm1 += g1.sum() * pixel
                gfm2 += g2.sum() * pixel
                inter1 += (g1 & m_ems).sum() * pixel
                inter2 += (g2 & m_ems).sum() * pixel
        if ems_px == 0:
            continue
        dep = distritos[distritos.intersects(aoi.representative_point())]["NOMBDEP"]
        filas.append({
            "aoi": nombre, "departamento": dep.iloc[0] if len(dep) else "",
            "aoi_km2": aoi_px, "ems_inundado_km2": ems_px,
            "gfm_1fecha_km2": gfm1, "gfm_2fechas_km2": gfm2,
            "deteccion_1fecha_pct": 100 * inter1 / ems_px, "deteccion_2fechas_pct": 100 * inter2 / ems_px,
            "gfm_fuera_ems_pct": 100 * (gfm2 - inter2) / gfm2 if gfm2 else np.nan,
        })
    tabla = pd.DataFrame(filas).sort_values("ems_inundado_km2", ascending=False).round(2)
    tabla.to_csv(PROC / "validacion_gfm_ems.csv", index=False, encoding="utf-8")
    print(tabla.to_string(index=False))


if __name__ == "__main__":
    main()
