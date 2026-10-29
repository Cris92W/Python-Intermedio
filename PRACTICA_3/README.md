# PRÁCTICA 3 · Un MCP del SENACE: Claude conectado a la certificación ambiental del Perú

**Sesión 04 · MCP: Claude conectado a tus datos.** Ciencia de Datos con Python (Python Intermedio), octubre de 2026.

- **Estudiante:** Cristian Moises Wong Pagan ([@Cris92W](https://github.com/Cris92W))
- **Resultado:** con el MCP, Claude (Haiku) acertó **10 de 10** cifras del SENACE; sin herramientas y con búsqueda web,
  **0 de 10** (respondió «no sé»). Detalle en el [informe](informe.md).

![Aciertos por modo y resoluciones del SENACE por mes](grafico.png)

## La tarea

Construir un servidor MCP con FastMCP, conectarlo a Claude Code y medir si ayuda: cuántas cifras acierta Claude sin
el servidor y cuántas con él. La sesión propone las series del BCRP; con autorización del profesor, este proyecto usa
otra institución con datos que se actualizan periódicamente, y las preguntas de prueba se adaptan a ella.

## La institución y la fuente

El **Servicio Nacional de Certificación Ambiental para las Inversiones Sostenibles (SENACE)** evalúa los estudios de
impacto ambiental de los grandes proyectos de inversión del Perú: minería, transportes, electricidad, hidrocarburos,
agricultura y residuos, entre otros.

Se revisaron dos fuentes públicas del SENACE, ninguna pide clave:

| Fuente | Qué tiene | ¿Se actualiza? |
|---|---|---|
| [Registro Administrativo de Certificaciones Ambientales (RCA)](https://enlinea.senace.gob.pe/Certificacion/CatalagoCertificacion) | 2 304 trámites evaluados por el SENACE desde 2016, con titular, proyecto, tipo de estudio, sector, ubicación, resultado, resolución y fechas | **Sí**: al 28/10/2026 tenía resoluciones del 23/10/2026; entre 8 y 25 por mes en 2026 |
| [Portal de datos abiertos](https://datosabiertos.senace.gob.pe) | Estudios aprobados, en evaluación y desaprobados, con coordenadas | **No**: el registro más reciente es del 07/05/2024 |

El servidor usa el **RCA**, porque es el que crece con cada resolución. Lo baja completo (unos 6 MB) una vez al día y
lo guarda en `datos/`, que no se sube al repositorio.

## El servidor

| Componente | Qué hace |
|---|---|
| `buscar_certificaciones` | Busca trámites por palabras (titular, proyecto, unidad) y por sector, tipo de estudio, resultado, departamento y fechas |
| `certificacion` | La ficha de un trámite por su número, con los días que tomó la evaluación |
| `resumen` | Cuenta los trámites resueltos en un periodo: total y por resultado, tipo, sector, departamento y mes |
| `plazos` (herramienta propia) | Días calendario entre el ingreso y la resolución: promedio, mediana, el más rápido y el más lento |
| Recursos | `senace://tramite/{tramite}` (ficha) y `senace://valores` (valores válidos de cada filtro) |
| Prompt | `informe(tema)`: un informe con cifras rastreables a su trámite o resolución |

Cada respuesta trae la fuente (el enlace al RCA) y la fecha de corte de los datos. Acepta las siglas de los
instrumentos: EIA-d, MEIA-d, EIA-sd, ITS, DIA, PPC y TdR.

## Cómo usarlo

Requiere [uv](https://docs.astral.sh/uv/) y Claude Code. Desde `PRACTICA_3/`:

```bash
uv run pytest -q                              # 9 pruebas con datos reales del RCA
claude                                        # aprobar los servidores de .mcp.json: senace y fetch
uv run verificar_web.py                       # la verdad de cada pregunta, desde la web del RCA
uv run evaluar.py                             # corrida base: sin herramientas frente a MCP, con Haiku
cp resultados.csv resultados_base.csv
uv run evaluar.py --modos memoria web mcp     # experimento extra: también con búsqueda web
uv run grafico.py                             # la figura del informe
```

En Claude Code: `/mcp` muestra los dos servidores; `@senace:senace://valores` lee un recurso; `/mcp__senace__informe
minería en Cusco` usa el prompt.

## Archivos

| Archivo | Qué es |
|---|---|
| `server.py` | El servidor MCP del SENACE |
| `test_server.py` | Las pruebas del servidor, adaptadas del contrato del BCRP al SENACE |
| `.mcp.json` | El servidor del SENACE y Fetch, para Claude Code (sin claves) |
| `preguntas.csv` | 10 preguntas de prueba con su verdad, cómo verificarla en el RCA y cuáles son propias |
| `verificar_web.py` | Comprueba la verdad de cada pregunta con el buscador web del RCA, sin usar el servidor |
| `evaluar.py` | La evaluación de la sesión, con el servidor `senace`; lanza a Claude sin memoria del proyecto |
| `resultados_base.csv` | Corrida base: sin herramientas y con el MCP |
| `resultados.csv` | Experimento extra: sin herramientas, con búsqueda web y con el MCP |
| `grafico.py`, `grafico.png` | La figura: aciertos por modo y resoluciones del SENACE por mes |
| `informe.md` | El análisis: qué acertó cada modo y por qué, cifras comprobadas a mano y contraste con la prensa |
