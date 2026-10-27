"""Indicadores por distrito y provincia de Piura, y datos para la web (Parte 1 de la Tarea 3).

    .venv/Scripts/python.exe scripts/analizar_datos.py

Requiere haber corrido obtener_limites.py, inventario_gfm.py, procesar_gfm.py, edificios_afectados.py,
validar_gfm_ems.py y obtener_huaicos.py.

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

Escribe datos/procesados/indicadores_distrito.csv y, en web/data/: distritos.geojson, serie.json,
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
RADIO_HUAICO_M = 160  # dos píxeles de 80 m alrededor de cada punto de INGEMMET
COBERTURA_MIN = 0.9  # "última fecha": la última pasada que vio al menos el 90 % de Piura


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


def huaicos_con_agua(evento):
    """Puntos de huaico de INGEMMET con agua anómala del radar a menos de RADIO_HUAICO_M."""
    puntos = gpd.read_file(WEB / "huaicos_ingemmet.geojson")
    puntos = puntos[puntos["huaico"]]
    vistos = np.zeros(len(puntos), dtype=bool)
    for tif in sorted((PROC / "gfm_80m").glob(f"{evento}_*.tif")):
        with rasterio.open(tif) as ds, \
                rasterio.open(tif.parent / tif.name.replace(evento, REFERENCIA, 1)) as ref:
            agua = (ds.read(1) >= 2) & (ref.read(1) == 0)
            zonas = puntos.to_crs(ds.crs).buffer(RADIO_HUAICO_M)
            marca = rasterize(((g, i + 1) for i, g in enumerate(zonas)), out_shape=agua.shape,
                              transform=ds.transform, fill=0, dtype="uint16", all_touched=True)
        vistos[np.unique(marca[agua & (marca > 0)]) - 1] = True
    return int(vistos.sum()), len(puntos)


def main():
    distritos = gpd.read_file(PROC / "distritos_estudio.gpkg")
    centros = distritos.to_crs("EPSG:32717").centroid.to_crs(4326)
    distritos["factor_equi7"] = factor_equi7(centros.x.values, centros.y.values)

    serie = pd.read_csv(PROC / "gfm_distrito_fecha.csv", dtype={"UBIGEO": str, "evento": str})
    serie = serie.merge(distritos[["UBIGEO", "NOMBPROV", "factor_equi7"]], on="UBIGEO")
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
    ind = ind.merge(distritos[["UBIGEO", "NOMBPROV", "NOMBDIST", "area_km2"]], on="UBIGEO")
    ind["pct_max"] = 100 * ind["inund_max_km2"] / ind["area_km2"]
    ind["pct_anom"] = 100 * ind["inund_anom_km2"] / ind["area_km2"]
    ind.to_csv(PROC / "indicadores_distrito.csv", index=False, encoding="utf-8")

    # Web: distritos con indicadores en columnas por evento
    ancho = ind.pivot(index="UBIGEO", columns="evento",
                      values=["inund_anom_km2", "inund_max_km2", "inund_union_km2", "pct_max", "pct_anom",
                              "fecha_max", "fechas_con_agua"])
    ancho.columns = [f"{v}_{e}" for v, e in ancho.columns]
    web = distritos[["UBIGEO", "NOMBPROV", "NOMBDIST", "area_km2", "geometry"]].merge(
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
    # Geometría simplificada como cobertura en obtener_limites.py: la misma de provincias y del contorno de Piura
    simple = gpd.read_file(PROC / "distritos_web.gpkg").set_index("UBIGEO").geometry
    web["geometry"] = simple.reindex(web["UBIGEO"]).values
    WEB.mkdir(parents=True, exist_ok=True)
    web.to_file(WEB / "distritos.geojson", driver="GeoJSON", COORDINATE_PRECISION=5)

    # Serie por fecha: km² anómalos de cada distrito (null si el radar no lo vio ese día) y % de Piura observado
    area_total = distritos["area_km2"].sum()
    serie_web, total = {}, []
    for evento, g in serie.groupby("evento"):
        fechas = sorted(g["fecha_peru"].unique())
        tabla = g.pivot_table(index="UBIGEO", columns="fecha_peru", values="anomalo_km2", aggfunc="sum")
        tabla = tabla.reindex(columns=fechas).round(2)
        obs = g.groupby("fecha_peru")["observado_km2"].sum().reindex(fechas)
        serie_web[evento] = {
            "fechas": fechas,
            "observado_pct": (100 * obs / area_total).round(1).tolist(),
            "distritos": {u: [None if pd.isna(v) else v for v in fila] for u, fila in tabla.iterrows()},
        }
        dia = g.groupby("fecha_peru", as_index=False)[["anomalo_km2", "observado_km2"]].sum()
        dia["evento"] = evento
        total.append(dia)
    (WEB / "serie.json").write_text(json.dumps(serie_web, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    total = pd.concat(total, ignore_index=True)

    indeci = pd.read_csv(PROC / "indeci_danos_departamento.csv", dtype={"evento": str})
    indeci = indeci[indeci["departamento"] == "PIURA"]
    (WEB / "indeci.json").write_text(json.dumps(registros(indeci), ensure_ascii=False, allow_nan=False),
                                     encoding="utf-8")

    inv = pd.read_csv(PROC / "gfm_inventario.csv", dtype={"evento": str})
    por_prov = (ind.groupby(["evento", "NOMBPROV"])
                .agg(inund_anom_km2=("inund_anom_km2", "sum"), inund_union_km2=("inund_union_km2", "sum"),
                     agua_habitual_km2=("agua_habitual_km2", "sum"),
                     distritos_con_agua=("inund_anom_km2", lambda s: int((s >= UMBRAL_KM2).sum())))
                .round(2).reset_index())
    resumen_evento = {}
    for evento in EVENTOS:
        d = ind[ind["evento"] == evento]
        t = total[total["evento"] == evento]
        pico = t.loc[t["anomalo_km2"].idxmax()]
        completas = t[t["observado_km2"] >= COBERTURA_MIN * area_total]
        ultimo = completas.sort_values("fecha_peru").iloc[-1]
        resumen_evento[evento] = {
            "escenas": int((inv["evento"] == evento).sum()), "fechas": int(inv.loc[inv["evento"] == evento,
                                                                                  "fecha_peru"].nunique()),
            "inund_anom_km2": round(d["inund_anom_km2"].sum(), 1),
            "inund_union_km2": round(d["inund_union_km2"].sum(), 1),
            "distritos_con_agua": int((d["inund_anom_km2"] >= UMBRAL_KM2).sum()),
            "pico_fecha": pico["fecha_peru"], "pico_km2": round(float(pico["anomalo_km2"]), 1),
            "ultima_fecha": ultimo["fecha_peru"], "ultima_km2": round(float(ultimo["anomalo_km2"]), 1),
        }
    resumen_evento[REFERENCIA] = {
        "escenas": int((inv["evento"] == REFERENCIA).sum()),
        "fechas": int(inv.loc[inv["evento"] == REFERENCIA, "fecha_peru"].nunique()),
        "agua_habitual_km2": round(float(agua_habitual.sum()), 1),
    }

    flujos = gpd.read_file(WEB / "huaicos_ingemmet.geojson")
    ems = gpd.read_file(WEB / "ems_2017.geojson")
    ems_km2 = ems[ems["tipo"] == "inundacion"].to_crs("EPSG:32717").union_all().area / 1e6  # AOIs unidas, sin doble conteo
    vistos = {e: huaicos_con_agua(e) for e in EVENTOS}
    resumen = {
        "area_km2": round(area_total, 1), "distritos": len(distritos),
        "eventos": resumen_evento,
        "por_provincia": registros(por_prov),
        "top_distritos": {e: registros(ind[ind["evento"] == e].nlargest(10, "inund_anom_km2")
                                       [["NOMBPROV", "NOMBDIST", "inund_anom_km2", "inund_union_km2",
                                         "agua_habitual_km2", "fecha_max"]].round(2)) for e in EVENTOS},
        "edificios": registros(pd.read_csv(PROC / "edificios_piura.csv"))[0],
        "validacion": registros(pd.read_csv(PROC / "validacion_gfm_ems.csv")),
        "ems_inundado_km2": round(ems_km2, 1),
        "indeci": {r["evento"]: r for r in registros(indeci)},
        "huaicos": {
            "flujos": len(flujos), "huaicos": int(flujos["huaico"].sum()),
            "por_provincia_tipo": registros(flujos.groupby(["provincia", "tipo"]).size()
                                            .rename("n").reset_index()),
            "con_agua_radar": {e: {"puntos": v[0], "de": v[1]} for e, v in vistos.items()},
        },
    }
    hallazgos = PROC / "hallazgos.json"  # redactados a mano con las cifras de esta salida
    if hallazgos.exists():
        resumen["hallazgos"] = json.loads(hallazgos.read_text(encoding="utf-8"))
    (WEB / "resumen.json").write_text(json.dumps(resumen, ensure_ascii=False, indent=1, allow_nan=False),
                                      encoding="utf-8")

    print(json.dumps(resumen_evento, ensure_ascii=False, indent=1))
    print(por_prov.to_string(index=False))
    print("Huaicos de INGEMMET con agua del radar cerca:", vistos)
    for e in EVENTOS:
        print(f"\nTop distritos {e} (inundación anómala):")
        print(ind[ind["evento"] == e].nlargest(10, "inund_anom_km2")
              [["NOMBPROV", "NOMBDIST", "inund_anom_km2", "inund_union_km2", "agua_habitual_km2", "fecha_max",
                "fechas_con_agua"]].round(2).to_string(index=False))


if __name__ == "__main__":
    main()
