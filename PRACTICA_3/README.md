# PRÁCTICA 3 · Un MCP del SENACE: Claude conectado a la certificación ambiental del Perú

**Sesión 04 · MCP: Claude conectado a tus datos.** Ciencia de Datos con Python (Python Intermedio), octubre de 2026.

- **Estudiante:** Cristian Moises Wong Pagan ([@Cris92W](https://github.com/Cris92W))
- **Estado:** servidor, pruebas (9 de 9 en verde) y conexión listos; faltan verificar a mano las preguntas, correr la
  evaluación y escribir el informe

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
uv run pytest -q                 # 9 pruebas con datos reales del RCA
claude                           # aprobar los servidores de .mcp.json: senace y fetch
uv run evaluar.py                # Claude sin herramientas frente a Claude con el MCP, con Haiku
```

En Claude Code: `/mcp` muestra los dos servidores; `@senace:senace://valores` lee un recurso; `/mcp__senace__informe
minería en Cusco` usa el prompt.

## Archivos

| Archivo | Qué es |
|---|---|
| `server.py` | El servidor MCP del SENACE |
| `test_server.py` | Las pruebas del servidor, adaptadas del contrato del BCRP al SENACE |
| `.mcp.json` | El servidor del SENACE y Fetch, para Claude Code (sin claves) |
| `preguntas.csv` | 10 preguntas de prueba, cada una con cómo verificarla a mano en el RCA |
| `evaluar.py` | La evaluación de la sesión, con el servidor `senace` |
| `resultados.csv`, `informe.md`, `grafico.png` | Pendientes |
