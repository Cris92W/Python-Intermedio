# PRÁCTICA 3 · Un MCP del SENACE: Claude conectado a la certificación ambiental del Perú

**Sesión 04 · MCP: Claude conectado a tus datos.** Ciencia de Datos con Python (Python Intermedio), octubre de 2026.

- **Estudiante:** Cristian Moises Wong Pagan ([@Cris92W](https://github.com/Cris92W))
- **Estado:** en construcción

## La tarea

Construir un servidor MCP con FastMCP, conectarlo a Claude Code y medir si ayuda: cuántas cifras acierta Claude sin
el servidor y cuántas con él. La sesión propone las series del BCRP; con autorización del profesor, este proyecto usa
otra institución con datos que se actualizan periódicamente, y las preguntas de prueba se adaptan a ella.

## La institución

El **Servicio Nacional de Certificación Ambiental para las Inversiones Sostenibles (SENACE)** evalúa y aprueba los
estudios de impacto ambiental detallados (EIA-d) de los grandes proyectos de inversión del Perú. Publica sus datos en
su [portal de datos abiertos](https://datosabiertos.senace.gob.pe): estudios ambientales aprobados, en evaluación y
desaprobados, consultoras registradas y talleres de participación ciudadana, entre otros.

## Entregables

| Archivo | Qué es |
|---|---|
| `server.py` | El servidor MCP del SENACE |
| `test_server.py` | Las pruebas del servidor, adaptadas al SENACE |
| `.mcp.json` | El servidor del SENACE y Fetch, para Claude Code |
| `preguntas.csv` | Las preguntas de prueba, con la cifra verificada a mano en el portal del SENACE |
| `evaluar.py` / `resultados.csv` | La evaluación: Claude sin herramientas frente a Claude con el MCP |
| `informe.md` / `grafico.png` | El análisis de los resultados |
