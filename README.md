# FromFitToMd

Procesador de archivos `.FIT` (Garmin) a Markdown. Extrae las metricas de entrenamiento y genera informes estructurados listos para copiar a Copilot 365, Obsidian o cualquier herramienta que soporte Markdown.

## Funcionalidades

- Deteccion automatica del tipo de entrenamiento:
  - **Intervalos**: separa calentamiento, series de trabajo, descansos y enfriamiento
  - **Rodaje continuo**: desglose km a km con splits y resumen (km mas rapido/lento)
- Titulo y notas personalizables desde la interfaz web (prioridad: titulo manual > nombre del workout > fecha)
- Metricas generales: calorias, volumen, Training Effect, FC, potencia, altitud, ritmo, dinamica de carrera
- Zonas de frecuencia cardiaca y zonas de potencia con tiempo y porcentaje por zona
- Indicadores de rendimiento premium: IF, TSS, desacoplamiento Pw:Hr, economia de carrera, indice de fatiga
- Graficos sparkline de evolucion (FC, ritmo, altitud, potencia) en Markdown puro (Unicode)
- Grafico de barras de eficiencia por vuelta (velocidad/FC)
- Nombre del workout programado como titulo (si existe en el .FIT)
- Estructura del workout planificado vs ejecutado (para entrenamientos programados)
- Interfaz web con Streamlit para subir archivos, añadir titulo/notas y descargar el `.md`
- Procesamiento por lotes desde directorio con filtros por fecha y limite de archivos

## Requisitos

- Python 3.9+
- Dependencias:

```
pip install -r requirements.txt
```

Contenido de `requirements.txt`:
```
fitparse
streamlit
```

## Uso

### Interfaz web (Streamlit)

```bash
python -m streamlit run app.py
```

Se abre en `http://localhost:8501`. Sube un archivo `.FIT` y obtendras:
- Campos opcionales para titulo y notas de la sesion
- Vista previa renderizada del informe
- Markdown en crudo para copiar
- Boton de descarga del archivo `.md`

El titulo sigue esta prioridad:
1. Titulo escrito manualmente en la interfaz
2. Nombre del workout programado del .FIT (`wkt_name`)
3. Fecha de la actividad

### Desde Python (procesamiento por lotes)

```python
import fitTOmd

# Un solo archivo con titulo y notas personalizados
contenido_md = fitTOmd.procesar_archivo_temporal(
    "ruta/al/archivo.fit",
    titulo="Tirada + 2km a umbral",
    notas="Sensaciones buenas, ultimos 2km a ritmo de umbral."
)

# Un solo archivo (funcion base)
contenido_md, fecha = fitTOmd.procesar_fit(
    "ruta/al/archivo.fit",
    titulo_personalizado="Mi titulo",
    notas_personalizadas="Mis notas"
)

# Directorio completo
fitTOmd.procesar_directorio(
    carpeta_fit="ruta/a/carpeta/",
    modo="individual",          # "individual" o "unico"
    carpeta_salida="salida/",
    max_archivos=100,           # 0 o None para todos
    fecha_min="2024-01-01",     # Opcional
    fecha_max="2026-12-31",     # Opcional
)
```

### Parametros de `procesar_directorio`

| Parametro | Descripcion | Default |
| :--- | :--- | :--- |
| `carpeta_fit` | Ruta a la carpeta con archivos .FIT | (requerido) |
| `modo` | `"individual"` (un .md por archivo) o `"unico"` (todo en uno) | `"individual"` |
| `carpeta_salida` | Carpeta destino para los .md individuales | `"entrenamientos_md"` |
| `archivo_unico` | Ruta del .md unico (modo "unico") | `"diario_entrenamientos.md"` |
| `max_archivos` | Limite de archivos a procesar (0 = sin limite) | `0` |
| `fecha_min` | Fecha minima en formato `"YYYY-MM-DD"` | `None` |
| `fecha_max` | Fecha maxima en formato `"YYYY-MM-DD"` | `None` |

## Estructura del informe generado

```
# Titulo (manual > nombre workout > fecha)
## Notas
Sensaciones, comentarios, etc, sobre el entramiento
## Resumen General de Metricas
  - Calorias
  - Volumen (distancia, tiempo movimiento/transcurrido, zancadas)
  - Training Effect
  - Frecuencia Cardiaca
  - Potencia (media, normalizada, maxima)
  - Altitud y Desnivel
  - Ritmo
  - Dinamica de Carrera
  - Zonas de Frecuencia Cardiaca
  - Indicadores de Rendimiento (drift, variabilidad, eficiencia, IF, TSS, Pw:Hr, economia, fatiga)
  - Zonas de Potencia
## Analisis de Intervalos (si aplica)
  - Entrenamiento Programado (planificado vs ejecutado)
  - Calentamiento
  - Series de Trabajo (tabla con NP, zancada, GCT, pendiente)
  - Descansos entre series
  - Enfriamiento
## Desglose por Kilometro (si es rodaje)
  - Splits km a km (con potencia, NP, zancada, GCT, pendiente)
  - Resumen (km rapido/lento/diferencia)
## Evolucion de la Actividad
  - Sparkline de Frecuencia Cardiaca
  - Sparkline de Ritmo
  - Sparkline de Altitud
  - Sparkline de Potencia
  - Grafico de barras de Eficiencia por vuelta
## Desglose General de Vueltas (con eficiencia por lap)
## Notas (manuales o del .FIT)
```

## Metricas premium

Metricas calculadas a partir de los datos del .FIT, equivalentes a servicios como Strava Summit o TrainingPeaks:

| Metrica | Descripcion | Interpretacion |
| :--- | :--- | :--- |
| **Drift cardiaco** | Diferencia de FC media entre 1a y 2a mitad | <5% = buena base aerobica |
| **Variabilidad de ritmo (CV)** | Coeficiente de variacion de la velocidad | Menor = ritmo mas estable |
| **Indice de eficiencia** | Velocidad / FC (x1000) | Mayor = mas eficiente |
| **Intensity Factor (IF)** | Potencia normalizada / FTP estimado | <1.0 = sub-umbral |
| **Training Stress Score (TSS)** | Carga de entrenamiento acumulada | <150 = recuperable en 24h |
| **Desacoplamiento Pw:Hr** | Cambio ratio potencia/FC entre mitades | <5% = buena base aerobica |
| **Economia de carrera** | Potencia media / velocidad media | Menor = mas economico |
| **Indice de fatiga** | Perdida de eficiencia (vel/FC) inicio vs fin | Indica degradacion mecanica |
| **Zonas de potencia** | Distribucion de tiempo en 6 zonas (basadas en FTP estimado) | Similar a TrainingPeaks |

## Graficos en Markdown

Los graficos usan caracteres Unicode estandar compatibles con cualquier renderer Markdown:

- **Sparklines** (`▁▂▃▄▅▆▇█`): evolucion temporal de FC, ritmo, altitud y potencia durante toda la actividad
- **Barras de eficiencia**: grafico horizontal por vuelta mostrando la relacion velocidad/FC

Ejemplo de sparkline de FC en un entrenamiento de intervalos:
```
▁▃▄▄▄▄▅▄▃▅▅▆▅▅▆▅▅▇▇▅▇█▅▅▅▆▆▆▅▅▆▆▅▆▆▆▆
```

## Zonas de Frecuencia Cardiaca

Las zonas estan configuradas en `ZONAS_FC` dentro de `fitTOmd.py`:

| Zona | Rango (ppm) |
| :--- | :--- |
| Z1 (Recuperacion) | 0 - 130 |
| Z2 (Aerobico Bajo) | 131 - 143 |
| Z3 (Aerobico Alto/Tempo) | 144 - 156 |
| Z4 (Umbral) | 157 - 168 |
| Z5 (VO2 Max) | 169 - 250 |

Puedes ajustar estos rangos a tus zonas personales editando el diccionario.

## Limitaciones

- La autoevaluacion (RPE) no se exporta en el formato .FIT de Garmin (queda solo en Garmin Connect). El titulo y las notas se pueden añadir manualmente desde la interfaz web.
- El nombre del workout solo aparece si el entrenamiento fue programado desde Garmin (no en actividades libres).
- Los campos GAP (ritmo ajustado a pendiente) y tiempo de carrera/caminar no estan disponibles en la exportacion .FIT estandar.
- El FTP se estima como el 75% de la potencia maxima de la sesion. Para metricas IF/TSS mas precisas, se recomienda configurar el FTP real en el codigo.

## Estructura del proyecto

```
FromFitToMd/
  app.py              # Interfaz web Streamlit (con campos de titulo y notas)
  fitTOmd.py          # Logica de procesamiento FIT -> Markdown
  requirements.txt    # Dependencias
  docs/               # Archivos FIT de ejemplo
```
