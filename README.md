# FromFitToMd

Procesador de archivos `.FIT` (Garmin) a Markdown. Extrae las metricas de entrenamiento y genera informes estructurados listos para copiar a Copilot 365, Obsidian o cualquier herramienta que soporte Markdown.

## Funcionalidades

- Deteccion automatica del tipo de entrenamiento:
  - **Intervalos**: separa calentamiento, series de trabajo, descansos y enfriamiento
  - **Rodaje continuo**: desglose km a km con splits y resumen (km mas rapido/lento)
- Metricas generales: calorias, Training Effect, FC, potencia, altitud, ritmo, dinamica de carrera
- Zonas de frecuencia cardiaca con tiempo y porcentaje por zona
- Nombre del workout programado como titulo (si existe en el .FIT)
- Interfaz web con Streamlit para subir archivos y descargar el `.md`
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
- Vista previa renderizada del informe
- Markdown en crudo para copiar
- Boton de descarga del archivo `.md`

### Desde Python (procesamiento por lotes)

```python
import fitTOmd

# Un solo archivo
contenido_md, fecha = fitTOmd.procesar_fit("ruta/al/archivo.fit")

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
# Titulo (nombre del workout o fecha)
## Resumen General de Metricas
  - Calorias
  - Training Effect
  - FC y Tiempo
  - Potencia
  - Altitud y Desnivel
  - Ritmo
  - Dinamica de Carrera
  - Zonas de Frecuencia Cardiaca
## Analisis de Intervalos (si aplica)
  - Calentamiento
  - Series de Trabajo (tabla)
  - Descansos entre series
  - Enfriamiento
## Desglose por Kilometro (si es rodaje)
  - Splits km a km
  - Resumen (km rapido/lento/diferencia)
## Desglose General de Vueltas
## Notas (si existen en el .FIT)
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

- El titulo personalizado, la autoevaluacion (RPE) y las notas post-actividad no se exportan en el formato .FIT de Garmin (quedan solo en Garmin Connect).
- El nombre del workout solo aparece si el entrenamiento fue programado desde Garmin (no en actividades libres).
- Los campos GAP (ritmo ajustado a pendiente) y tiempo de carrera/caminar no estan disponibles en la exportacion .FIT estandar.

## Estructura del proyecto

```
FromFitToMd/
  app.py              # Interfaz web Streamlit
  fitTOmd.py          # Logica de procesamiento FIT -> Markdown
  requirements.txt    # Dependencias
  docs/               # Archivos FIT de ejemplo
```
