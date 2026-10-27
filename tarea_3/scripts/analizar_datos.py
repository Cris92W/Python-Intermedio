"""Indicadores por distrito y departamento, y datos para la web (Parte 1 de la Tarea 3).

    .venv/Scripts/python.exe scripts/analizar_datos.py

Requiere haber corrido obtener_limites.py, inventario_gfm.py, procesar_gfm.py y edificios_afectados.py.

Indicadores de GFM por distrito y evento:
- inund_max_km2: la mayor superficie inundada en una sola fecha, ya descontada el agua habitual
  (robusto al ruido de fechas sueltas).
- fecha_max: la fecha de ese máximo (hora de Perú).
- inund_union_km2: superficie inundada en al menos dos fechas de la ventana (unión de los mapas de 80 m;
  pedir dos fechas descarta píxeles que el radar marca una sola vez, que suelen ser errores).
- fechas_con_agua: fechas en que el distrito tuvo al menos 0,1 km² inundados.
- inund_anom_km2: como inund_union_km2, pero solo en píxeles que en la referencia (ene-jun 2022, sin Niño)
  nunca tuvieron agua. Descuenta arrozales, salinas y lagunas que se llenan todos los años. Es el
  indicador principal: la máscara de "agua habitual" de GFM se armó con datos de 2017 a 2021 y no
  basta para esta costa.
La serie por fecha también resta el agua habitual: a cada distrito se le descuenta la mediana de km²
inundados que tuvo en las fechas de 2022 (sin bajar de cero).

Corrección de área: GFM usa la proyección Equi7 (azimutal equidistante centrada en 60,5° O, 14° S), que
agranda las áreas lejos del centro en un factor c/sen(c), con c la distancia angular al centro
(un 2 % en la costa peruana). Las superficies se dividen por ese factor.

Escribe datos/procesados/indicadores_distrito.csv y, en web/data/: distritos.geojson, serie_gfm.json,
indeci.json y resumen.json.
"""
import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import rasterize

BASE = Path(__file__).resolve().parent.parent
PROC = BASE / "datos" / "procesados"
WEB = BASE / "web" / "data"
CENTRO_EQUI7 = (-60.5, -14.0)
UMBRAL_KM2 = 0.1
EVENTOS = ("2017", "2023")
REFERENCIA = "2022"


def registros(df):
    """Filas como dicts con NaN -> null (JSON válido para el navegador)."""
    return json.loads(df.to_json(orient="records", force_ascii=False))


def factor_equi7(lon, lat):
    l0, f0 = np.radians(CENTRO_EQUI7)
    lon, lat = np.radians(lon), np.radians(lat)
    c = np.arccos(np.sin(f0) * np.sin(lat) + np.cos(f0) * np.cos(lat) * np.cos(lon - l0))
    return c / np.sin(c)


def union_por_distrito(distritos, evento, minimo=2, referencia=None):
    """km² con agua en al menos `minimo` fechas, por distrito, desde los rasters de 80 m.
    Con `referencia`, solo cuenta los píxeles que en ese año nunca tuvieron agua."""
    total = np.zeros(len(distritos))
    for tif in sorted((PROC / "gfm_80m").glob(f"{evento}_*.tif")):
        with rasterio.open(tif) as ds:
            mascara = ds.read(1) >= minimo
            indices = rasterize(((g, i + 1) for i, g in enumerate(distritos.to_crs(ds.crs).geometry)),
                                out_shape=mascara.shape, transform=ds.transform, fill=0, dtype="uint16")
            pixel_km2 = abs(ds.transform.a * ds.transform.e) / 1e6
        if referencia:  # mismo tile y misma grilla en ambos años
            with rasterio.open(tif.parent / tif.name.replace(evento, referencia, 1)) as ref:
                mascara &= ref.read(1) == 0
        total += np.bincount(indices[mascara], minlength=len(distritos) + 1)[1:] * pixel_km2
    return total


def main():
    distritos = gpd.read_file(PROC / "distritos_estudio.gpkg")
    centros = distritos.to_crs("EPSG:32718").centroid.to_crs(4326)
    distritos["factor_equi7"] = factor_equi7(centros.x.values, centros.y.values)

    serie = pd.read_csv(PROC / "gfm_distrito_fecha.csv", dtype={"UBIGEO": str, "evento": str})
    serie = serie.merge(distritos[["UBIGEO", "NOMBDEP", "factor_equi7"]], on="UBIGEO")
    for col in ("inundado_km2", "observado_km2"):
        serie[col] = serie[col] / serie["factor_equi7"]
    habitual = serie[serie["evento"] == REFERENCIA].groupby("UBIGEO")["inundado_km2"].median()
    serie = serie[serie["evento"].isin(EVENTOS)].copy()
    serie["anomalo_km2"] = (serie["inundado_km2"] - serie["UBIGEO"].map(habitual).fillna(0)).clip(lower=0)

    # Indicadores por distrito y evento
    filas = []
    for evento, g in serie.groupby("evento"):
        idx = g.groupby("UBIGEO")["anomalo_km2"].idxmax()
        pico = g.loc[idx, ["UBIGEO", "anomalo_km2", "fecha_peru"]].rename(
            columns={"anomalo_km2": "inund_max_km2", "fecha_peru": "fecha_max"})
        pico["fechas_con_agua"] = pico["UBIGEO"].map(
            g[g["anomalo_km2"] >= UMBRAL_KM2].groupby("UBIGEO").size()).fillna(0).astype(int)
        pico["fechas_observado"] = pico["UBIGEO"].map(g.groupby("UBIGEO").size())
        pico["evento"] = str(evento)
        filas.append(pico)
    ind = pd.concat(filas, ignore_index=True)
    agua_habitual = union_por_distrito(distritos, REFERENCIA) / distritos["factor_equi7"].values
    for evento in EVENTOS:
        sel = ind["evento"] == evento
        for col, ref in (("inund_union_km2", None), ("inund_anom_km2", REFERENCIA)):
            valores = union_por_distrito(distritos, evento, referencia=ref) / distritos["factor_equi7"].values
            ind.loc[sel, col] = ind.loc[sel, "UBIGEO"].map(dict(zip(distritos["UBIGEO"], valores)))
    ind["agua_habitual_km2"] = ind["UBIGEO"].map(dict(zip(distritos["UBIGEO"], agua_habitual)))
    ind.loc[ind["inund_max_km2"] < UMBRAL_KM2, "fecha_max"] = ""
    ind = ind.merge(distritos[["UBIGEO", "NOMBDEP", "NOMBPROV", "NOMBDIST", "area_km2"]], on="UBIGEO")
    ind["pct_max"] = 100 * ind["inund_max_km2"] / ind["area_km2"]
    ind.to_csv(PROC / "indicadores_distrito.csv", index=False, encoding="utf-8")

    # Web: distritos con indicadores en columnas por evento
    ancho = ind.pivot(index="UBIGEO", columns="evento",
                      values=["inund_anom_km2", "inund_max_km2", "inund_union_km2", "pct_max", "fecha_max",
                              "fechas_con_agua"])
    ancho.columns = [f"{v}_{e}" for v, e in ancho.columns]
    web = distritos[["UBIGEO", "NOMBDEP", "NOMBPROV", "NOMBDIST", "area_km2", "geometry"]].merge(
        ancho.reset_index(), on="UBIGEO", how="left")
    web["agua_habitual_km2"] = web["UBIGEO"].map(dict(zip(distritos["UBIGEO"], agua_habitual)))
    # El pivote mezcla fechas y números (columnas object): se fuerzan a número para que el JSON no lleve texto.
    for c in web.columns:
        if c.startswith(("inund_", "pct_", "area_", "agua_")):
            web[c] = pd.to_numeric(web[c]).fillna(0).round(3)
        elif c.startswith("fechas_con_agua"):
            web[c] = pd.to_numeric(web[c]).fillna(0).astype(int)
        elif c.startswith("fecha_max"):
            web[c] = web[c].fillna("")
    web["geometry"] = web.to_crs("EPSG:32718").simplify(150).to_crs(4326)
    WEB.mkdir(parents=True, exist_ok=True)
    web.to_file(WEB / "distritos.geojson", driver="GeoJSON", COORDINATE_PRECISION=5)

    # Serie por departamento y fecha (solo la parte observada ese día)
    dep = (serie.groupby(["evento", "fecha_peru", "NOMBDEP"], as_index=False)
           [["inundado_km2", "anomalo_km2", "observado_km2"]].sum())
    area_dep = distritos.groupby("NOMBDEP")["area_km2"].sum()
    dep["pct_observado"] = 100 * dep["observado_km2"] / dep["NOMBDEP"].map(area_dep)
    dep = dep.round(3)
    (WEB / "serie_gfm.json").write_text(json.dumps(registros(dep), ensure_ascii=False), encoding="utf-8")

    indeci = pd.read_csv(PROC / "indeci_danos_departamento.csv")
    (WEB / "indeci.json").write_text(json.dumps({
        "departamento": json.loads(indeci.to_json(orient="records", force_ascii=False)),
        "mensual_2023": json.loads(pd.read_csv(PROC / "indeci_2023_mensual.csv").to_json(orient="records"))},
        ensure_ascii=False), encoding="utf-8")

    edificios = pd.concat([pd.read_csv(PROC / f"edificios_{z}.csv") for z in ("piura", "trujillo")])
    por_dep = (ind.groupby(["evento", "NOMBDEP"])
               .agg(inund_anom_km2=("inund_anom_km2", "sum"), inund_union_km2=("inund_union_km2", "sum"),
                    agua_habitual_km2=("agua_habitual_km2", "sum"),
                    distritos_con_agua=("inund_anom_km2", lambda s: int((s >= UMBRAL_KM2).sum())))
               .round(2).reset_index())
    pico_dep = dep.loc[dep.groupby(["evento", "NOMBDEP"])["anomalo_km2"].idxmax(),
                       ["evento", "NOMBDEP", "fecha_peru", "anomalo_km2"]]
    resumen = {
        "por_departamento": registros(por_dep),
        "pico_departamento": registros(pico_dep.rename(columns={"fecha_peru": "fecha", "anomalo_km2": "km2"})
                                       .round(2)),
        "edificios": registros(edificios),
        "validacion": registros(pd.read_csv(PROC / "validacion_gfm_ems.csv")),
        "top_distritos": {e: registros(ind[ind["evento"] == e].nlargest(10, "inund_anom_km2")
                                       [["NOMBDEP", "NOMBDIST", "inund_anom_km2", "inund_union_km2",
                                         "agua_habitual_km2", "fecha_max"]].round(2)) for e in EVENTOS},
    }
    hallazgos = PROC / "hallazgos.json"  # redactados a mano con las cifras de esta salida
    if hallazgos.exists():
        resumen["hallazgos"] = json.loads(hallazgos.read_text(encoding="utf-8"))
    (WEB / "resumen.json").write_text(json.dumps(resumen, ensure_ascii=False, indent=1, allow_nan=False),
                                      encoding="utf-8")

    print(por_dep.to_string(index=False))
    print(pico_dep.round(2).to_string(index=False))
    for e in EVENTOS:
        print(f"\nTop distritos {e} (inundación anómala):")
        print(ind[ind["evento"] == e].nlargest(10, "inund_anom_km2")
              [["NOMBDEP", "NOMBDIST", "inund_anom_km2", "inund_union_km2", "agua_habitual_km2", "fecha_max",
                "fechas_con_agua"]].round(2).to_string(index=False))


if __name__ == "__main__":
    main()
