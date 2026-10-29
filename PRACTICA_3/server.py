"""Servidor MCP del SENACE: el Registro Administrativo de Certificaciones Ambientales (RCA), consultado en línea.

    uv run pytest                                             # las pruebas del servidor
    uv run server.py                                          # el servidor, por stdio
    claude mcp add --scope project senace -- uv run server.py # conectarlo a Claude Code

El RCA es el buscador público del SENACE: cada fila es un trámite que el SENACE evaluó (un estudio de impacto
ambiental, un informe técnico sustentatorio, un plan de participación ciudadana...) con su titular, su ubicación,
su resultado, su resolución y sus fechas. Crece cada vez que el SENACE emite una resolución, así que el servidor lo
baja completo una vez al día y lo guarda en datos/.

Las cuentas las hace Python, no el modelo: así cada cifra sale de una llamada que se puede repetir.
"""
import json
import re
import time
import unicodedata
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path

import httpx
import pandas as pd
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

AQUI = Path(__file__).parent
TABLA = AQUI / "datos" / "rca_senace.csv"
RCA = "https://enlinea.senace.gob.pe/Certificacion/CatalagoCertificacion"
# El buscador del RCA con todos los filtros en «todos», salvo la entidad evaluadora: solo el SENACE (IdOrigen=1).
CONSULTA = {"NroCatalogo": "", "NroRecurso": "", "DesTitular": "", "NroRuc": "", "IdTipoEstudio": "0",
            "IdEstadoProyecto": "0", "CodSector": "0|0", "IdGrupoSector": "0", "DesConsultora": "", "NroRucCons": "",
            "IdDepartamento": "00", "IdProvincia": "", "IdDistrito": "", "NombreProyecto": "", "IdOrigen": "1",
            "Unidad": "", "IdEntidadOr": "0"}
COLUMNAS = {"NRO. TRÁMITE": "tramite", "TITULAR": "titular", "NOMBRE PROYECTO": "proyecto",
            "UNIDAD PROYECTO": "unidad", "TIPO IGA": "tipo", "ACTIVIDAD": "sector", "UBIGEO": "ubicacion",
            "RESULTADO EVALUACIÓN": "resultado", "FECHA INGRESO": "ingreso", "NRO. RESOLUCIÓN": "resolucion",
            "FECHA RESOLUCIÓN": "fecha"}
# Siglas con que se nombran los instrumentos de gestión ambiental, y el nombre que usa el RCA
SIGLAS = {"eia-d": "Estudio de Impacto Ambiental Detallado", "eia": "Estudio de Impacto Ambiental Detallado",
          "meia-d": "Modificación de Estudio de Impacto Ambiental Detallado",
          "meia": "Modificación de Estudio de Impacto Ambiental Detallado",
          "eia-sd": "Estudio de Impacto Ambiental Semidetallado", "its": "Informe Técnico Sustentatorio",
          "dia": "Declaracion de Impacto Ambiental", "ppc": "Plan de Participación Ciudadana",
          "mppc": "Modificacion de Plan de Participacion Ciudadana", "tdr": "TDR"}
HORAS_DE_VIGENCIA = 24
SOLO_LECTURA = {"readOnlyHint": True, "openWorldHint": True}

mcp = FastMCP("senace", instructions=(
    "Registro Administrativo de Certificaciones Ambientales (RCA) del SENACE, el Servicio Nacional de "
    "Certificación Ambiental del Perú: los trámites que evaluó, con su resultado, resolución y fechas. Para contar "
    "usa resumen; para tiempos de evaluación, plazos; para encontrar proyectos o empresas, buscar_certificaciones; "
    "para un trámite, certificacion. No cuentes a mano: cita el número de trámite o de resolución y la fecha de "
    "corte de los datos."))


def _sin_tildes(s):
    return unicodedata.normalize("NFD", str(s).lower()).encode("ascii", "ignore").decode().strip()


class _Tabla(HTMLParser):
    """Junta el texto de cada celda de la página en una lista de filas."""

    def __init__(self):
        super().__init__()
        self.filas, self._fila, self._celda = [], None, None

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self._fila = []
        elif tag in ("td", "th") and self._fila is not None:
            self._celda = []

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._celda is not None:
            self._fila.append(" ".join("".join(self._celda).split()))
            self._celda = None
        elif tag == "tr" and self._fila:
            self.filas.append(self._fila)
            self._fila = None

    def handle_data(self, data):
        if self._celda is not None:
            self._celda.append(data)


def _descargar():
    """Pide al buscador del RCA todos los trámites del SENACE (unos 6 MB de HTML) y los deja en una tabla."""
    for intento in range(3):
        try:
            r = httpx.post(f"{RCA}/BuscarCatalogoCertificacion", params=CONSULTA, content=b"",
                           headers={"X-Requested-With": "XMLHttpRequest"}, timeout=180)
            r.raise_for_status()
            break
        except httpx.HTTPError:
            if intento == 2:
                raise
            time.sleep(5)
    p = _Tabla()
    p.feed(r.text)
    cabecera = next(f for f in p.filas if "NRO. TRÁMITE" in f)
    filas = [f for f in p.filas if len(f) == len(cabecera) and f[0].isdigit()]
    df = pd.DataFrame(filas, columns=cabecera)[list(COLUMNAS)].rename(columns=COLUMNAS)
    # La ubicación llega como "- AYACUCHO-VICTOR FAJARDO-CANARIA"; un proyecto lineal (una carretera, una línea de
    # transmisión) trae varias: "- APURIMAC-COTABAMBAS-TAMBOBAMBA - APURIMAC-GRAU-PROGRESO". Se guardan todas.
    lugares = df.ubicacion.str.removeprefix("- ").str.split(" - ").map(
        lambda ls: [[p.strip() for p in l.split("-", 2)] for l in ls if l.strip()])
    df["ubicacion"] = lugares.map(lambda ls: "; ".join("/".join(l) for l in ls))
    df["departamentos"] = lugares.map(lambda ls: "; ".join(dict.fromkeys(l[0] for l in ls)))
    for c in ("ingreso", "fecha"):
        df[c] = pd.to_datetime(df[c], format="%d/%m/%Y", errors="coerce").dt.strftime("%Y-%m-%d")
    return df


_memo = {}


def tabla():
    """El RCA del SENACE. Se baja si no está en datos/ o si tiene más de un día; si el SENACE no responde, se usa la
    última copia."""
    vieja = not TABLA.exists() or time.time() - TABLA.stat().st_mtime > HORAS_DE_VIGENCIA * 3600
    if vieja:
        try:
            df = _descargar()
            TABLA.parent.mkdir(exist_ok=True)
            df.to_csv(TABLA, index=False)
        except (httpx.HTTPError, StopIteration):
            if not TABLA.exists():
                raise ToolError("El RCA del SENACE no respondió y no hay una copia en datos/. Reintenten en unos minutos.")
    marca = TABLA.stat().st_mtime
    if _memo.get("marca") != marca:
        df = pd.read_csv(TABLA, dtype=str, keep_default_na=False)
        for c in ("ingreso", "fecha"):
            df[c] = pd.to_datetime(df[c], errors="coerce")
        df["texto"] = (df.tramite + " " + df.titular + " " + df.proyecto + " " + df.unidad).map(_sin_tildes)
        df["deps"] = df.departamentos.map(lambda s: s.split("; ") if s else [])
        _memo.update(marca=marca, df=df, corte=datetime.fromtimestamp(marca).strftime("%Y-%m-%d %H:%M"))
    return _memo["df"]


def _origen():
    return {"fuente": RCA, "datos_al": _memo["corte"]}


def _fecha(s, fin):
    """"2026" → el año entero, "2026-09" → el mes, "2026-09-15" → el día."""
    s = str(s).strip()
    if re.fullmatch(r"\d{4}", s):
        return pd.Timestamp(f"{s}-12-31") if fin else pd.Timestamp(f"{s}-01-01")
    if re.fullmatch(r"\d{4}-\d{2}", s):
        t = pd.Timestamp(f"{s}-01")
        return t + pd.offsets.MonthEnd(0) if fin else t
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        return pd.Timestamp(s)
    raise ToolError(f"La fecha {s!r} no es válida: usen 2026, 2026-09 o 2026-09-15.")


def _valor(columna, pedido):
    """El valor exacto del RCA que corresponde a lo pedido, sin importar tildes, mayúsculas ni siglas."""
    df = tabla()
    validos = sorted({d for ds in df.deps for d in ds} if columna == "departamento" else set(df[columna]) - {""})
    p = _sin_tildes(SIGLAS.get(_sin_tildes(pedido), pedido)) if columna == "tipo" else _sin_tildes(pedido)
    exactos = [v for v in validos if _sin_tildes(v) == p]
    empiezan = [v for v in validos if _sin_tildes(v).startswith(p)]
    if exactos or len(empiezan) == 1:
        return (exactos or empiezan)[0]
    raise ToolError(f"{columna} {pedido!r} no existe en el RCA. Valores posibles: {', '.join(validos)}.")


def _filtrar(desde=None, hasta=None, sector=None, tipo=None, resultado=None, departamento=None, texto=None):
    df = tabla()
    m = pd.Series(True, index=df.index)
    if desde:
        m &= df.fecha >= _fecha(desde, fin=False)
    if hasta:
        m &= df.fecha <= _fecha(hasta, fin=True)
    for columna, pedido in (("sector", sector), ("tipo", tipo), ("resultado", resultado)):
        if pedido:
            m &= df[columna] == _valor(columna, pedido)
    if departamento:
        d = _valor("departamento", departamento)
        m &= df.deps.map(lambda ds: d in ds)
    for palabra in _sin_tildes(texto or "").split():
        m &= df.texto.str.contains(re.escape(palabra))
    return df[m]


def _ficha(f):
    dias = (f.fecha - f.ingreso).days if pd.notna(f.fecha) and pd.notna(f.ingreso) else None
    return {"tramite": f.tramite, "titular": f.titular, "proyecto": f.proyecto, "unidad": f.unidad, "tipo": f.tipo,
            "sector": f.sector, "departamentos": f.deps, "ubicaciones": f.ubicacion.split("; ") if f.ubicacion else [],
            "resultado": f.resultado, "resolucion": f.resolucion,
            "fecha_ingreso": f.ingreso.strftime("%Y-%m-%d") if pd.notna(f.ingreso) else None,
            "fecha_resolucion": f.fecha.strftime("%Y-%m-%d") if pd.notna(f.fecha) else None,
            "dias_de_evaluacion": dias}


def _conteo(serie, limite=None):
    c = serie[serie != ""].value_counts()
    return {k: int(v) for k, v in (c.head(limite) if limite else c).items()}


@mcp.tool(annotations=SOLO_LECTURA)
def buscar_certificaciones(texto: str | None = None, sector: str | None = None, tipo: str | None = None,
                           resultado: str | None = None, departamento: str | None = None, desde: str | None = None,
                           hasta: str | None = None, limite: int = 10) -> dict:
    """Busca trámites del SENACE por palabras (todas deben aparecer en el titular, el proyecto, la unidad o el número
    de trámite) y por filtros. Devuelve el total encontrado y los más recientes primero.

    Ejemplos de texto: "Las Bambas", "Quellaveco", "Antamina relaves", "aeropuerto Chinchero", "línea de transmisión".
    sector: Minería, Transportes, Electricidad, Hidrocarburos, Agricultura, Residuos Sólidos, Saneamiento...
    tipo: el nombre del RCA o su sigla: EIA-d, MEIA-d, EIA-sd, ITS, DIA, PPC, TdR.
    resultado: Aprobado, Conforme, Desaprobado, No conforme, Desistido o Improcedente.
    departamento: Piura, Cusco, Arequipa... (un proyecto lineal aparece en todos los departamentos que cruza).
    desde y hasta filtran la fecha de la resolución: "2026", "2026-09" o "2026-09-15". Para contar, usen resumen.
    """
    sel = _filtrar(desde, hasta, sector, tipo, resultado, departamento, texto)
    sel = sel.sort_values(["fecha", "tramite"], ascending=False)
    return {"total": len(sel), "tramites": [_ficha(f) for f in sel.head(limite).itertuples()], **_origen()}


@mcp.tool(annotations=SOLO_LECTURA)
def certificacion(tramite: str) -> dict:
    """La ficha completa de un trámite del SENACE por su número, por ejemplo "03951-2025" o "M-ITS-00151-2026":
    titular, proyecto, tipo de estudio, sector, ubicación, resultado, resolución, fechas de ingreso y de resolución, y
    los días calendario que tomó la evaluación. Si no tienen el número, búsquenlo con buscar_certificaciones.
    """
    df = tabla()
    fila = df[df.tramite.str.upper() == tramite.strip().upper()]
    if fila.empty:
        raise ToolError(f"No existe el trámite {tramite!r} en el RCA del SENACE. Búsquenlo con buscar_certificaciones.")
    return {**_ficha(next(fila.itertuples())), **_origen()}


@mcp.tool(annotations=SOLO_LECTURA)
def resumen(desde: str, hasta: str, sector: str | None = None, tipo: str | None = None,
            resultado: str | None = None, departamento: str | None = None) -> dict:
    """Cuenta los trámites que el SENACE resolvió entre dos fechas, ambas incluidas, con filtros opcionales: el total,
    y cuántos por resultado, tipo de estudio, sector, departamento y mes, además del primero y el último.

    Fechas: "2026" (año), "2026-09" (mes) o "2026-09-15" (día); cuentan por la fecha de la resolución.
    Un proyecto lineal que cruza varios departamentos cuenta en cada uno de ellos dentro de por_departamento.
    Ojo: un ITS o un PPC se aprueba con resultado «Conforme» o «Aprobado» según el caso; si preguntan por
    aprobaciones, revisen por_resultado. Úsenla siempre para contar: no sumen a mano.
    """
    sel = _filtrar(desde, hasta, sector, tipo, resultado, departamento)
    orden = sel.sort_values(["fecha", "tramite"])
    corto = lambda f: {"tramite": f.tramite, "titular": f.titular, "tipo": f.tipo, "resultado": f.resultado,
                       "fecha_resolucion": f.fecha.strftime("%Y-%m-%d")}
    return {"desde": _fecha(desde, False).strftime("%Y-%m-%d"), "hasta": _fecha(hasta, True).strftime("%Y-%m-%d"),
            "total": len(sel), "por_resultado": _conteo(sel.resultado), "por_tipo": _conteo(sel.tipo),
            "por_sector": _conteo(sel.sector), "por_departamento": _conteo(sel.deps.explode().dropna()),
            "por_mes": {k: int(v) for k, v in sel.fecha.dt.strftime("%Y-%m").value_counts().sort_index().items()},
            "primero": corto(next(orden.itertuples())) if len(sel) else None,
            "ultimo": corto(next(orden.iloc[::-1].itertuples())) if len(sel) else None, **_origen()}


@mcp.tool(annotations=SOLO_LECTURA)
def plazos(desde: str, hasta: str, tipo: str | None = None, sector: str | None = None,
           resultado: str | None = None) -> dict:
    """¿Cuánto tarda el SENACE en evaluar? Días calendario entre el ingreso del trámite y su resolución, para los
    trámites resueltos entre dos fechas: promedio, mediana, el más rápido y el más lento.

    Úsenla para preguntas como «¿cuánto demoró en promedio la evaluación de un EIA-d en 2025?» o «¿qué trámite
    minero tardó más en 2026?». Son días calendario, no hábiles: el SENACE suele informar días hábiles, que son menos.
    Los trámites con una fecha de ingreso posterior a la resolución (errores del registro) se excluyen y se cuentan.
    Fechas, tipo, sector y resultado como en resumen.
    """
    sel = _filtrar(desde, hasta, sector, tipo, resultado)
    dias = (sel.fecha - sel.ingreso).dt.days
    validos = sel[dias >= 0].assign(dias=dias[dias >= 0])
    if validos.empty:
        raise ToolError("No hay trámites con fechas válidas para esos filtros.")
    extremo = lambda f: {"tramite": f.tramite, "titular": f.titular, "tipo": f.tipo, "dias": int(f.dias),
                         "fecha_ingreso": f.ingreso.strftime("%Y-%m-%d"),
                         "fecha_resolucion": f.fecha.strftime("%Y-%m-%d")}
    orden = validos.sort_values(["dias", "tramite"])
    return {"tramites": len(validos), "excluidos_por_fechas_inconsistentes": int((dias < 0).sum()),
            "dias_promedio": round(float(validos.dias.mean()), 1), "dias_mediana": float(validos.dias.median()),
            "mas_rapido": extremo(next(orden.itertuples())), "mas_lento": extremo(next(orden.iloc[::-1].itertuples())),
            **_origen()}


@mcp.resource("senace://tramite/{tramite}", mime_type="application/json")
def ficha_tramite(tramite: str) -> str:
    """La ficha de un trámite del RCA del SENACE, por su número."""
    return json.dumps(certificacion(tramite), ensure_ascii=False, indent=1)


@mcp.resource("senace://valores", mime_type="application/json")
def valores() -> str:
    """Los valores que aceptan los filtros: sectores, tipos de estudio, resultados y departamentos, con cuántos
    trámites tiene cada uno, y la fecha de la primera y la última resolución del registro."""
    df = tabla()
    return json.dumps({"sectores": _conteo(df.sector), "tipos": _conteo(df.tipo), "resultados": _conteo(df.resultado),
                       "departamentos": _conteo(df.deps.explode().dropna()), "siglas_de_tipo": SIGLAS,
                       "primera_resolucion": df.fecha.min().strftime("%Y-%m-%d"),
                       "ultima_resolucion": df.fecha.max().strftime("%Y-%m-%d"), **_origen()},
                      ensure_ascii=False, indent=1)


@mcp.prompt
def informe(tema: str) -> str:
    """Un informe breve, con cifras rastreables, sobre la certificación ambiental de un sector, una región, una
    empresa o un periodo."""
    return (f"Prepara un informe breve sobre «{tema}» con el Registro Administrativo de Certificaciones Ambientales "
            "del SENACE. Usa resumen para los conteos y plazos para los tiempos de evaluación; usa "
            "buscar_certificaciones o certificacion para los casos concretos. No hagas cuentas a mano. Cita el número "
            "de trámite o de resolución de cada caso, aclara que los plazos son días calendario y termina con la "
            "fecha de corte de los datos y el enlace al RCA.")


if __name__ == "__main__":
    mcp.run()
