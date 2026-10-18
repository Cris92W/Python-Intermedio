# Tarea 1 – Noticias peruanas: del titular al clasificador

> **¿Pueden convertir titulares peruanos en un clasificador de noticias?**

La Tarea 1 consiste en construir, de principio a fin, un clasificador automático de noticias peruanas a partir de titulares reales del diario **El Comercio** (Caso B), recolectados de forma responsable mediante sus canales oficiales de RSS y sitemaps, respetando su `robots.txt` y aplicando pausas entre solicitudes. Con `requests`, `BeautifulSoup` y `pandas` se extraen y limpian más de 350 noticias, que se normalizan en cuatro categorías fijas (política, economía, deportes y ciencia y tecnología) y se exploran con gráficos interactivos en Plotly. Luego se comparan tres enfoques de clasificación evaluados sobre un mismo conjunto de test aislado: un modelo zero-shot sin entrenamiento como línea base, un LLM que etiqueta los titulares mediante un prompt estructurado (validado con una auditoría humana de 20 casos) y un Transformer ligero, DistilBERT multilingüe, ajustado con fine-tuning usando el `Trainer` de Hugging Face en CPU. Finalmente, el modelo se integra en un dashboard de Streamlit que permite explorar los datos y clasificar titulares nuevos en vivo. A lo largo del proyecto se aprende a recolectar datos web de manera ética, a limpiar y estructurar información real, a usar LLMs como herramienta de etiquetado (supervisión débil), a aplicar transfer learning con modelos de lenguaje, a evaluar con rigor mediante F1 macro y matriz de confusión sin contaminar el test, y a llevar un modelo hasta una aplicación funcional, todo documentado con un flujo de trabajo ordenado en Git y GitHub.

| | |
|---|---|
| **Estudiante** | Cristian Moises Wong Pagan ([@Cris92W](https://github.com/Cris92W)) |
| **Medio** | El Comercio (Caso B) |
| **Dashboard** | `streamlit run app.py` (ejecución local comprobada) |
| **Resultados test** | F1 Macro: **0.88** · Zero-shot: 0.69 · Acuerdo LLM-Humano: **19/20** |

---

## 1. Pregunta del proyecto

**¿Pueden convertir titulares peruanos en un clasificador de noticias?** En concreto: con unos cientos de titulares reales y sin GPU, ¿se puede entrenar un modelo que asigne un titular nuevo a una de cuatro categorías (`politica`, `economia`, `deportes`, `ciencia_tecnologia`) mejor que un modelo zero-shot y que un LLM, y lo bastante rápido para usarlo en vivo?

**Respuesta: sí.** Un DistilBERT multilingüe ajustado con 275 titulares en unos 11 minutos de CPU obtiene **F1 macro 0.885** en un test de 60 noticias que nunca vio, frente a 0.695 del zero-shot y 0.779 del LLM, y clasifica cada titular en menos de 0.1 s.

## 2. Medio y fechas de extracción

| | |
|---|---|
| Medio | **El Comercio** (`https://elcomercio.pe`) |
| Fuentes | RSS de portada + RSS y sitemap de noticias de 4 secciones: `politica`, `economia`, `deporte-total`, `tecnologia` (9 feeds) |
| Fecha de extracción | **17 de octubre de 2026**, de 00:17 a 00:30 (hora de Lima): 252 solicitudes HTTP, todas 200, con pausas de 1–2 s y User-Agent identificado |
| Fechas de publicación cubiertas | **6 al 17 de octubre de 2026** |
| Volumen | 715 filas crudas → **394 noticias** tras limpieza (100 política, 100 economía, 99 deportes, 95 ciencia y tecnología) |
| Respaldo crudo | `datos/raw/` (XML originales, `robots.txt`, log de solicitudes) |

Las etiquetas del LLM (`Qwen/Qwen2.5-1.5B-Instruct`, local) se generaron el 17/10/2026 y la auditoría humana de 20 casos se hizo a mano en `datos/auditoria_llm.xlsx`.

## 3. Resultados

Los tres enfoques se miden sobre **las mismas 60 noticias de test** (split estratificado 70/15/15, `random_state=42`), apartadas antes de cualquier decisión.

| Enfoque | Modelo | F1 macro (test) | Latencia por titular (CPU) |
|---|---|:---:|:---:|
| Zero-shot NLI | `joeddav/xlm-roberta-large-xnli` | 0.695 (0.694 en los 40 titulares de la línea base) | ~1.6–2.6 s |
| LLM (supervisión débil) | `Qwen/Qwen2.5-1.5B-Instruct` | 0.779 | ~2.7 s |
| **DistilBERT fine-tuned** | `distilbert-base-multilingual-cased` | **0.885** (accuracy 0.883) | **< 0.1 s** |

Auditoría humana del LLM: **19/20 = 95 %** de acuerdo (IC 95 % de Wilson: 76 %–99 %).

## 4. Hallazgos analíticos

1. **Un modelo pequeño ajustado supera a los modelos grandes sin ajustar y es 25–40 veces más rápido.** El DistilBERT (135 M de parámetros) gana por 19 puntos de F1 al zero-shot (560 M) y por 11 al LLM (1 544 M). Lo más fácil es **deportes** (F1 0.93: clubes, torneos y marcadores forman un vocabulario casi exclusivo). Lo más difícil es separar **política de economía** (F1 0.84 cada una), que solo se confunden entre sí: en la agenda peruana comparten actores y temas (minería, MAPE, aranceles, nombramientos en entidades económicas). El editor archiva por el *tema*, pero el modelo se guía por el *actor*: cuando aparece un ministro o un jefe de Estado, tiende a responder política.
2. **La sección editorial es una etiqueta ruidosa, y el LLM sirve como etiquetador.** En la auditoría, el LLM coincide más con la persona (19/20) que con la sección del diario (16/20). Incluso la persona discrepa de la sección en 3 de 20 casos (por ejemplo, notas sobre IA publicadas en Economía o el nombramiento de un directorio en Fonafe). Un DistilBERT entrenado **solo** con las etiquetas del LLM, sin mirar la sección, llega a F1 0.80 en test, por encima del propio LLM (0.78). Si un medio no tuviera secciones confiables, se podría etiquetar con un LLM, auditar una muestra y destilar el resultado en un modelo pequeño.

## 5. Limitaciones técnicas

1. **Datos pocos, de un solo medio y de una ventana corta.** Son 394 titulares de El Comercio publicados en 12 días, y el test tiene solo 60 noticias: cada error mueve la accuracy 1.7 puntos, con un intervalo de confianza de aproximadamente ±0.08. Además, la coyuntura de esos días (las Elecciones Regionales y Municipales 2026) domina la categoría política. Con titulares de otro medio (con otro estilo, como La República) o de otro período, el desempeño probablemente baje, y el modelo debería reentrenarse cada cierto tiempo con titulares nuevos.
2. **El modelo trabaja con 4 categorías cerradas y es sobreconfiado.** Cualquier titular (policiales, espectáculos, internacionales) recibe una de las 4 categorías, porque no existe la opción "ninguna". Las probabilidades tampoco están calibradas: en el test, los 7 errores tuvieron probabilidades de 0.76 a 0.99. Por eso el dashboard muestra la distribución completa y avisa cuando la probabilidad es baja. Además, la métrica se calcula contra la sección editorial, que también tiene ruido (hallazgo 2).

## 6. Cómo ejecutarlo en local

Requisitos: Python **3.12** y unos 3 GB de espacio libre para las dependencias y los modelos. Comandos exactos (Windows, con Anaconda/Miniconda):

```bash
git clone https://github.com/Cris92W/Python-Intermedio.git
cd Python-Intermedio/tarea_1
conda create -n tarea1 python=3.12 -y
conda activate tarea1
pip install -r requirements.txt
streamlit run app.py
```

La app se abre en `http://localhost:8501`. Sin conda: `python -m venv .venv`, luego `.venv\Scripts\activate` (Windows) o `source .venv/bin/activate` (Linux/macOS), y después los mismos `pip install -r requirements.txt` y `streamlit run app.py`.

**Pesos del modelo.** `modelo/model.safetensors` (541 MB) no está en GitHub porque supera el límite de 100 MB (ver `.gitignore`). Está publicado en Hugging Face Hub: [`Criswong92/distilbert-noticias-elcomercio`](https://huggingface.co/Criswong92/distilbert-noticias-elcomercio). Sin él, el dashboard funciona igual (datos, filtros, métricas, gráficos, tabla y entidades), pero el probador en vivo muestra un aviso. Hay dos formas de obtenerlo:

- indicar el repositorio de Hugging Face antes de lanzar la app (se descarga solo la primera vez):
  `$env:MODELO_HF="Criswong92/distilbert-noticias-elcomercio"; streamlit run app.py` (PowerShell) o `MODELO_HF=Criswong92/distilbert-noticias-elcomercio streamlit run app.py` (bash), o
- ejecutar `02_clasificacion.ipynb`, que entrena el modelo y lo guarda en `modelo/` (unos 25–30 minutos en CPU).

Para volver a ejecutar los notebooks se usan las mismas dependencias (sección "Notebooks" de `requirements.txt`). Con `USAR_CACHE = True` reutilizan los datos crudos y las etiquetas del LLM, así que no vuelven a descargar nada del medio.

### Qué tiene el dashboard (`app.py`)

- **Encabezado:** la pregunta del trabajo, la respuesta corta y un resumen metodológico en 4 pasos.
- **Barra lateral:** filtros por **medio**, **categoría**, rango de fechas y palabra clave (sin distinguir tildes).
- **Indicadores (`st.metric`):** noticias recolectadas, noticias en la selección, **F1 macro en test** y **% de acuerdo LLM-humano**.
- **Explorar datos:** gráfico Plotly interactivo de la distribución de categorías filtradas (por sección editorial o por etiqueta del LLM), acuerdo LLM-sección por categoría y `st.dataframe` con **descarga en CSV**.
- **Probador en vivo:** se escribe un titular, se pulsa *Clasificar titular* y se obtiene la categoría predicha, su probabilidad, la distribución sobre las 4 categorías y las 5 noticias más parecidas del dataset (buscador semántico de la Parte 1).
- **Extras:** entidades nombradas (NER) más mencionadas en la selección, y comparativa de modelos con la auditoría y el prompt del LLM.

## 7. Estructura

```text
tarea_1/
├── 01_recoleccion.ipynb       # Parte 1: recolección, limpieza, EDA (+ NER y buscador semántico)
├── 02_clasificacion.ipynb     # Parte 2: zero-shot, LLM + auditoría, fine-tuning, evaluación
├── app.py                     # Parte 3: dashboard en Streamlit
├── requirements.txt           # Dependencias exactas
├── README.md                  # Este reporte
├── .gitignore                 # Excluye pesos del modelo y checkpoints
├── datos/
│   ├── noticias.csv           # 394 noticias, 7 columnas
│   ├── etiquetas_llm.csv      # titular, etiqueta_llm, confianza, modelo_llm, fecha
│   ├── etiquetas_llm_meta.json# prompt, modelo y tiempos del etiquetado
│   ├── auditoria_llm.csv/.xlsx# auditoría humana de 20 casos
│   ├── particion.csv          # train / val / test por URL
│   ├── descartes.csv          # filas descartadas y motivo
│   ├── entidades_ner.csv      # entidades nombradas (extra)
│   ├── embeddings_noticias.npy# embeddings para el buscador semántico (extra)
│   └── raw/                   # respaldo crudo de la recolección
└── modelo/
    ├── config.json, tokenizer.json, tokenizer_config.json
    ├── info_entrenamiento.json # hiperparámetros y F1 de validación
    ├── metricas.json          # métricas finales que lee el dashboard
    └── model.safetensors      # pesos (541 MB, no se sube a GitHub)
```

## 8. Despliegue en Streamlit Community Cloud (opcional)

1. En [share.streamlit.io](https://share.streamlit.io): *Create app* → repositorio `Cris92W/Python-Intermedio`, rama `main`, archivo `tarea_1/app.py`. En *Advanced settings*, elegir Python 3.12.
2. Como los pesos no están en GitHub, se leen de Hugging Face Hub. En *Secrets* se agrega `MODELO_HF = "Criswong92/distilbert-noticias-elcomercio"`. Streamlit expone ese secret como variable de entorno, y la app descarga el modelo al iniciar.
3. En Linux, `requirements.txt` instala la rueda CPU oficial de `torch` para Python 3.12, para no descargar las librerías de CUDA (unos 2 GB).
