# FromFitToMd v2.0

Procesador de entrenamientos y datos de salud de Garmin a Markdown. Se integra con Garmin Connect para descargar actividades y metricas de salud automaticamente, o procesa archivos `.FIT` manualmente. Genera informes estructurados listos para Copilot 365, Obsidian o cualquier herramienta Markdown.

## Novedades v2.0

- Soporte para entrenamientos de fuerza (gimnasio): informe con series, repeticiones, peso y volumen
- Integracion directa con Garmin Connect (descarga automatica de actividades y salud)
- Credenciales cifradas con Fernet (nunca en texto plano)
- Informe de salud diaria: sueno, estres, Body Battery, HRV, SpO2, respiracion, training readiness y mas
- Titulo y notas recuperados automaticamente de Garmin Connect (sin escribirlos a mano)
- Meteorologia de la actividad incluida en el informe
- Tres modos de operacion: datos de ayer, rango de fechas, archivo FIT manual
- Descarga masiva en ZIP para rangos de fechas

## Modos de operacion

### 1. Datos de ayer

Un clic: descarga automaticamente las actividades y datos de salud del dia anterior. Ideal para la rutina diaria de analisis.

### 2. Rango de fechas

- Selecciona fecha inicio y fin
- Elige: solo actividades, solo salud, o ambas
- Barra de progreso durante el procesamiento
- Descarga individual de cada informe o descarga masiva en ZIP

### 3. Archivo .FIT manual

Funciona como la v1: sube un archivo .FIT, anade titulo y notas opcionales, y descarga el informe.

## Requisitos

- Python 3.9+
- Cuenta de Garmin Connect (para modos 1 y 2)

```bash
pip install -r requirements.txt
```

Dependencias:
```
fitparse>=1.2.0
streamlit>=1.60.0
garminconnect>=0.3.7
cryptography>=42.0.0
```

## Configuracion de credenciales

Las credenciales de Garmin se cifran con Fernet y se almacenan como variables de entorno. Nunca se guardan en texto plano.

### Paso 1: Generar clave y cifrar credenciales

```bash
python garmin_client.py
```

Esto ejecuta un asistente interactivo que:
1. Genera una clave Fernet
2. Pide tu email y contrasena de Garmin
3. Muestra las variables de entorno cifradas

### Paso 2: Configurar variables de entorno

En Windows (PowerShell):
```powershell
$env:GARMIN_KEY = "tu_clave_fernet"
$env:GARMIN_EMAIL_ENC = "email_cifrado"
$env:GARMIN_PASS_ENC = "password_cifrado"
```

En Linux/Mac:
```bash
export GARMIN_KEY="tu_clave_fernet"
export GARMIN_EMAIL_ENC="email_cifrado"
export GARMIN_PASS_ENC="password_cifrado"
```

Opcional (ruta de tokens):
```
GARMINTOKENS=~/.garminconnect
```

### Tokens reutilizables

Tras el primer login, los tokens OAuth se guardan en `~/.garminconnect` y se reutilizan automaticamente. No necesitas introducir credenciales de nuevo salvo que caduquen.

## Uso

### Interfaz web (Streamlit)

```bash
python -m streamlit run app.py
```

Se abre en `http://localhost:8501` con las tres opciones de operacion.

### Desde Python

```python
import garmin_client as gc
import fitTOmd as ftm
import health_to_md as htm

# Login
garmin = gc.login_garmin()

# Actividades de ayer
actividades = gc.obtener_actividades_ayer(garmin)
for act in actividades:
    activity_id = str(act["activityId"])
    metadata = gc.obtener_metadata_actividad(garmin, activity_id)
    weather = gc.obtener_meteorologia_actividad(garmin, activity_id)
    ruta_fit = gc.descargar_fit_actividad(garmin, activity_id)
    md = ftm.procesar_archivo_temporal(
        ruta_fit,
        garmin_metadata=metadata,
        meteorologia=weather,
    )

# Salud de una fecha
datos = gc.obtener_datos_salud(garmin, "2026-08-20")
md_salud = htm.generar_salud_md(datos)

# Archivo FIT manual (sin Garmin Connect)
md_manual = ftm.procesar_archivo_temporal(
    "ruta/al/archivo.fit",
    titulo="Mi titulo",
    notas="Mis notas",
)
```

## Estructura del informe de actividad

```
# Titulo (manual > Garmin Connect > workout FIT > fecha)
> Notas (manual > Garmin description > FIT notes)
> Meteorologia (temperatura, humedad, viento)
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
  - Indicadores de Rendimiento (drift, CV, eficiencia, IF, TSS, Pw:Hr, economia, fatiga)
  - Zonas de Potencia
## Analisis de Intervalos / Desglose por Kilometro
## Evolucion de la Actividad (sparklines)
  - FC, Ritmo, Altitud, Potencia
  - Carrera / Caminar, Cadencia, Zancada, GCT
  - Eficiencia por vuelta (barras)
## Desglose General de Vueltas
```

## Estructura del informe de fuerza

Cuando el archivo FIT es un entrenamiento de fuerza (`sub_sport = strength_training`), se detecta automáticamente y se genera un informe adaptado al gimnasio, sin métricas de ritmo/velocidad/altitud que no aplican. Los datos provienen de los mensajes `set` del FIT (series y descansos).

```
# Titulo (manual > Garmin Connect > nombre del deporte/workout > fecha)
> Notas (manual > Garmin description > FIT notes)
## Resumen General
  - Ejercicios distintos
  - Series de trabajo
  - Repeticiones totales
  - Volumen total levantado (peso x reps de cada serie)
  - Peso maximo
  - Calorias
  - Tiempo total, transcurrido, bajo tension y de descanso
### Frecuencia Cardiaca y Esfuerzo (FC media/max, Training Effect)
## Resumen por Ejercicio (series, reps, rango de peso, volumen)
## Detalle de Series (reps, peso, duracion y descanso posterior por serie)
### Volumen por Ejercicio (grafico de barras)
```

Notas sobre los datos de fuerza:

- El **volumen** se calcula como la suma de `peso x repeticiones` de cada serie de trabajo.
- El reconocimiento del **tipo de ejercicio** depende de Garmin. Cuando el reloj no clasifica un movimiento, usa un código genérico (`65534`) y el informe cae en el nombre disponible; ejercicios distintos pueden agruparse bajo una misma etiqueta. Es una limitación del archivo, no del procesado.
- Los "sets fantasma" (0 repeticiones y duracion despreciable, generados al cerrar la sesion) se descartan.

## Estructura del informe de salud

```
# Informe de Salud: YYYY-MM-DD
## Resumen del Dia (pasos, distancia, calorias, intensidad)
## Frecuencia Cardiaca (reposo, max, min)
## Sueno (duracion, fases, puntuacion, grafico distribucion)
## Estres (media, max, distribucion, sparkline)
## Body Battery (max, min, sparkline, carga/descarga)
## HRV (media nocturna, baseline, estado)
## SpO2 (media, minima)
## Respiracion (media, min, max)
## Pisos subidos/bajados
## Minutos de Intensidad (moderados, vigorosos, progreso)
## Hidratacion (ingesta, objetivo, progreso)
## Training Readiness (puntuacion, nivel)
## Training Status (estado, VO2 Max, carga semanal)
## Composicion Corporal (peso, IMC, grasa, musculo)
```

## Cadena de prioridad de datos

| Dato | Prioridad 1 | Prioridad 2 | Prioridad 3 | Prioridad 4 |
| :--- | :--- | :--- | :--- | :--- |
| **Titulo** | Input manual (UI) | activityName (Garmin Connect) | wkt_name (archivo FIT) | Fecha |
| **Notas** | Input manual (UI) | description (Garmin Connect) | notes (archivo FIT) | — |
| **Meteorologia** | Garmin Connect API | — | — | — |

## Metricas premium calculadas

| Metrica | Descripcion |
| :--- | :--- |
| Drift cardiaco | Diferencia FC media entre mitades (<5% = buena base) |
| Variabilidad ritmo (CV) | Estabilidad del ritmo |
| Indice de eficiencia | Velocidad/FC (mayor = mejor) |
| Intensity Factor (IF) | Potencia normalizada / FTP estimado |
| Training Stress Score (TSS) | Carga de entrenamiento (<150 = recuperable en 24h) |
| Desacoplamiento Pw:Hr | Fatiga aerobica por ratio potencia/FC |
| Economia de carrera | Potencia / velocidad |
| Indice de fatiga | Perdida de eficiencia inicio vs fin |
| Zonas de potencia | 6 zonas basadas en FTP estimado |

## Graficos en Markdown

Caracteres Unicode compatibles con cualquier renderer:

- **Sparklines** (`▁▂▃▄▅▆▇█`): FC, ritmo, altitud, potencia, cadencia, zancada, GCT, body battery, estres
- **Timeline carrera/caminar**: `█` corriendo / `░` caminando
- **Barras de eficiencia**: grafico horizontal por vuelta
- **Distribucion del sueno**: barras con porcentajes por fase

## Seguridad

- Las credenciales se cifran con **Fernet** (AES-128-CBC + HMAC-SHA256)
- La clave de cifrado se almacena como variable de entorno, nunca en el codigo
- Los tokens OAuth se guardan localmente en `~/.garminconnect` y se auto-refrescan
- Las credenciales en texto plano solo existen en memoria durante el login inicial
- El archivo `.gitignore` debe excluir `~/.garminconnect` y cualquier archivo `.env`

## Limitaciones

- La API de Garmin Connect es no oficial y puede cambiar sin previo aviso
- Rate limiting: ~50-100 peticiones cada 10 minutos. La app anade delays automaticos
- La autoevaluacion (RPE) no se exporta en el formato FIT
- El FTP se estima como 75% de la potencia maxima. Para IF/TSS mas precisos, configurar FTP real
- Algunos datos de salud requieren dispositivos compatibles (Body Battery, HRV, SpO2)

## Estructura del proyecto

```
FromFitToMd/
  app.py              # Interfaz web Streamlit (3 modos de operacion)
  fitTOmd.py          # Procesamiento FIT -> Markdown (actividades; detecta fuerza y delega)
  strength_to_md.py   # Procesamiento FIT de fuerza (strength_training) -> Markdown
  health_to_md.py     # Procesamiento datos salud -> Markdown
  garmin_client.py    # Cliente Garmin Connect (login, descarga, salud)
  requirements.txt    # Dependencias
  docs/               # Archivos FIT de ejemplo
```
