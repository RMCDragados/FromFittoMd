from datetime import datetime, timedelta
from pathlib import Path
import glob
import os
import fitparse


# Configuración de Zonas de Frecuencia Cardíaca
ZONAS_FC = {
    "Z1 (Recuperación)": (0, 130),
    "Z2 (Aeróbico Bajo)": (131, 143),
    "Z3 (Aeróbico Alto/Tempo)": (144, 156),
    "Z4 (Umbral)": (157, 168),
    "Z5 (VO2 Máx)": (169, 250),
}


def calcular_zonas_fc(records):
    tiempos_zona = {zona: 0 for zona in ZONAS_FC}
    total_segundos = 0

    for record in records:
        fc = record.get("heart_rate")
        if fc is not None:
            total_segundos += 1
            for zona, (lim_inf, lim_sup) in ZONAS_FC.items():
                if lim_inf <= fc <= lim_sup:
                    tiempos_zona[zona] += 1
                    break

    resumen_zonas = []
    if total_segundos > 0:
        for zona, segs in tiempos_zona.items():
            pct = (segs / total_segundos) * 100
            tiempo_fmt = str(timedelta(seconds=segs))
            resumen_zonas.append((zona, tiempo_fmt, round(pct, 1)))

    return resumen_zonas


def procesar_fit(archivo_fit):
    fitfile = fitparse.FitFile(archivo_fit)

    # 1. Leer mensaje de la Sesión principal
    datos_sesion = {}
    for record in fitfile.get_messages("session"):
        for data in record:
            datos_sesion[data.name] = data.value

    # 2. Leer vueltas (Laps)
    vueltas = []
    for lap in fitfile.get_messages("lap"):
        l_data = {}
        for data in lap:
            l_data[data.name] = data.value
        vueltas.append(l_data)

    # Helpers de conversión
    def ms_a_ritmo(velocidad_ms):
        if velocidad_ms and velocidad_ms > 0:
            sec_per_km = 1000 / velocidad_ms
            return f"{int(sec_per_km // 60)}:{int(sec_per_km % 60):02d} min/km"
        return "N/A"

    def seg_a_tiempo(segundos):
        if segundos is not None and segundos > 0:
            return str(timedelta(seconds=int(segundos)))
        return "N/A"

    # --- DATOS GENERALES ---
    deporte = str(datos_sesion.get("sport", "Desconocido")).capitalize()
    sub_deporte = str(datos_sesion.get("sub_sport", "")).capitalize()
    fecha_inicio = datos_sesion.get("start_time", "Desconocida")

    # Calorías
    calorias_activas = datos_sesion.get("total_calories", "N/A")
    calorias_reposo = datos_sesion.get("bmr_calories", "N/A")
    calorias_consumidas = datos_sesion.get("calories_consumed", "N/A")
    total_calorias = (
        calorias_activas + calorias_reposo
        if isinstance(calorias_activas, (int, float))
        and isinstance(calorias_reposo, (int, float))
        else calorias_activas
    )

    # Training Effect & Beneficio
    te_aerobico = datos_sesion.get("total_training_effect", "N/A")
    te_anaerobico = datos_sesion.get("total_anaerobic_training_effect", "N/A")
    beneficio_principal = datos_sesion.get("primary_benefit", "N/A")

    # FC, Tiempo y Potencia
    fc_media = datos_sesion.get("avg_heart_rate", "N/A")
    fc_maxima = datos_sesion.get("max_heart_rate", "N/A")
    tiempo_total = seg_a_tiempo(datos_sesion.get("total_timer_time"))
    potencia_media = datos_sesion.get("avg_power", "N/A")
    potencia_maxima = datos_sesion.get("max_power", "N/A")

    # Altitud y Carrera/Caminar
    ascenso_total = datos_sesion.get("total_ascent", "N/A")
    descenso_total = datos_sesion.get("total_descent", "N/A")
    altura_minima = datos_sesion.get("enhanced_min_altitude", "N/A")
    altura_maxima = datos_sesion.get("enhanced_max_altitude", "N/A")
    tiempo_carrera = seg_a_tiempo(datos_sesion.get("time_in_run"))
    tiempo_caminar = seg_a_tiempo(datos_sesion.get("time_in_walk"))

    # Ritmos
    ritmo_medio = ms_a_ritmo(datos_sesion.get("avg_speed"))
    ritmo_movimiento = ms_a_ritmo(datos_sesion.get("enhanced_avg_speed"))
    ritmo_optimo = ms_a_ritmo(datos_sesion.get("max_speed"))
    ritmo_gap = ms_a_ritmo(datos_sesion.get("avg_grade_adjusted_speed"))

    # Dinámica de carrera
    cadencia_med = datos_sesion.get(
        "avg_running_cadence", datos_sesion.get("avg_cadence", "N/A")
    )
    if isinstance(cadencia_med, (int, float)) and cadencia_med < 100:
        cadencia_med *= 2

    cadencia_max = datos_sesion.get(
        "max_running_cadence", datos_sesion.get("max_cadence", "N/A")
    )
    if isinstance(cadencia_max, (int, float)) and cadencia_max < 100:
        cadencia_max *= 2

    longitud_zancada = datos_sesion.get("avg_step_length", "N/A")
    if isinstance(longitud_zancada, (int, float)):
        longitud_zancada = (
            round(longitud_zancada / 1000, 2)
            if longitud_zancada > 10
            else round(longitud_zancada, 2)
        )

    relacion_vertical = datos_sesion.get("avg_vertical_ratio", "N/A")
    oscilacion_vertical = datos_sesion.get("avg_vertical_oscillation", "N/A")
    if isinstance(oscilacion_vertical, (int, float)):
        oscilacion_vertical = round(oscilacion_vertical / 10, 2)

    tiempo_contacto_suelo = datos_sesion.get("avg_stance_time", "N/A")
    minutos_intensidad = datos_sesion.get("intensity_factor", "N/A")

    # --- FORMATO MARKDOWN EN TABLAS RESUMEN ---
    md = []
    md.append(f"# 🏃‍♂️ Entrenamiento: {fecha_inicio}")
    md.append(f"**Deporte:** {deporte} ({sub_deporte})  ")
    md.append(f"**Archivo:** `{archivo_fit}`  \n")

    md.append("## 📊 Resumen General de Métricas")

    md.append("### 🔥 Calorías")
    md.append("| Métrica | Valor |")
    md.append("| :--- | :--- |")
    md.append(f"| **Calorías en reposo** | `{calorias_reposo} kcal` |")
    md.append(f"| **Calorías activas** | `{calorias_activas} kcal` |")
    md.append(f"| **Total de calorías quemadas** | `{total_calorias} kcal` |")
    md.append(f"| **Calorías consumidas** | `{calorias_consumidas} kcal` |")
    md.append(f"| **Calorías netas** | `{calorias_activas} kcal` |")
    md.append("")

    md.append("### 📈 EFECTO DE ENTRENAMIENTO (Training Effect)")
    md.append("| Métrica | Valor |")
    md.append("| :--- | :--- |")
    md.append(f"| **Training Effect (Aeróbico / Anaeróbico)** | `{te_aerobico} / {te_anaerobico}` |")
    md.append(f"| **Beneficio principal** | `{beneficio_principal}` |")
    md.append("")

    md.append("### 🫀 Frecuencia Cardíaca y Tiempo")
    md.append("| Métrica | Valor |")
    md.append("| :--- | :--- |")
    md.append(f"| **Tiempo Total** | `{tiempo_total}` |")
    md.append(f"| **FC Media** | `{fc_media} ppm` |")
    md.append(f"| **FC Máxima** | `{fc_maxima} ppm` |")
    md.append(f"| **Minutos de intensidad** | `{minutos_intensidad}` |")
    md.append("")

    md.append("### ⚡ Potencia")
    md.append("| Métrica | Valor |")
    md.append("| :--- | :--- |")
    md.append(f"| **Potencia media** | `{potencia_media} W` |")
    md.append(f"| **Potencia máxima** | `{potencia_maxima} W` |")
    md.append("")

    md.append("### ⛰️ Altitud y Desnivel")
    md.append("| Métrica | Valor |")
    md.append("| :--- | :--- |")
    md.append(f"| **Ascenso total** | `+{ascenso_total} m` |")
    md.append(f"| **Descenso total** | `-{descenso_total} m` |")
    md.append(f"| **Altura mínima** | `{altura_minima} m` |")
    md.append(f"| **Altura máxima** | `{altura_maxima} m` |")
    md.append("")

    md.append("### 🚶‍♂️ Detección de Carrera / Caminar")
    md.append("| Métrica | Valor |")
    md.append("| :--- | :--- |")
    md.append(f"| **Tiempo de carrera** | `{tiempo_carrera}` |")
    md.append(f"| **Tiempo de caminar** | `{tiempo_caminar}` |")
    md.append("")

    md.append("### ⏱️ Ritmo")
    md.append("| Métrica | Valor |")
    md.append("| :--- | :--- |")
    md.append(f"| **Ritmo medio** | `{ritmo_medio}` |")
    md.append(f"| **Ritmo medio en movimiento** | `{ritmo_movimiento}` |")
    md.append(f"| **Ritmo óptimo (Máximo)** | `{ritmo_optimo}` |")
    md.append(
        f"| **Ritmo medio adaptado a la pendiente (GAP)** | `{ritmo_gap}` |"
    )
    md.append("")

    md.append("### 🦶 Dinámica de Carrera")
    md.append("| Métrica | Valor |")
    md.append("| :--- | :--- |")
    md.append(f"| **Cadencia media** | `{cadencia_med} ppm` |")
    md.append(f"| **Cadencia máxima** | `{cadencia_max} ppm` |")
    md.append(f"| **Longitud media de zancada** | `{longitud_zancada} m` |")
    md.append(f"| **Relación vertical media** | `{relacion_vertical} %` |")
    md.append(f"| **Oscilación vertical media** | `{oscilacion_vertical} cm` |")
    md.append(
        f"| **Tiempo medio de contacto con el suelo** | `{tiempo_contacto_suelo} ms` |"
    )
    md.append("")

    # --- DETECCIÓN Y ANÁLISIS DE SERIES / INTERVALOS ---
    series = []
    for lap in vueltas:
        intensidad = str(lap.get("intensity", "")).lower()
        trigger = str(lap.get("lap_trigger", "")).lower()

        # Se considera serie activa si el entrenamiento de Garmin lo marca como 'active'
        # o si la vuelta fue dada manualmente por botón (manual)
        if intensidad in ["active", "0"] or trigger == "manual":
            series.append(lap)

    # Solo añade el apartado de Series si hay laps identificados como tales
    if series and len(series) > 1:
        md.append("## 🎯 Análisis Específico de Series / Intervalos")
        md.append(
            "| Serie Nº | Distancia | Tiempo | Ritmo Medio | FC Media | FC Máxima | Cadencia | Potencia |"
        )
        md.append(
            "| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |"
        )

        num_serie = 1
        for lap in vueltas:
            intensidad = str(lap.get("intensity", "")).lower()
            trigger = str(lap.get("lap_trigger", "")).lower()

            # Filtramos solo laps de trabajo (eliminando calentamientos, descansos y enfriamiento si están etiquetados)
            if intensidad in ["warmup", "cooldown", "rest", "recovery"]:
                continue

            l_dist_m = lap.get("total_distance", 0) or 0
            l_dist_km = round(l_dist_m / 1000, 2)
            l_time_s = lap.get("total_timer_time", 0) or 0
            l_time_str = seg_a_tiempo(l_time_s)
            l_ritmo = ms_a_ritmo(lap.get("avg_speed", 0))
            l_fc_med = lap.get("avg_heart_rate", "N/A")
            l_fc_max = lap.get("max_heart_rate", "N/A")

            l_cad = lap.get(
                "avg_running_cadence", lap.get("avg_cadence", "N/A")
            )
            if isinstance(l_cad, (int, float)) and l_cad < 100:
                l_cad *= 2

            l_pot = lap.get("avg_power", "N/A")

            md.append(
                f"| **Serie {num_serie}** | {l_dist_km} km ({int(l_dist_m)}m) | {l_time_str} | **{l_ritmo}** | {l_fc_med} ppm | {l_fc_max} ppm | {l_cad} ppm | {l_pot} W |"
            )
            num_serie += 1

        md.append("")

    # --- TABLA DE DESGLOSE COMPLETO POR VUELTAS (LAPS) ---
    if vueltas:
        md.append("## ⏱️ Desglose General de Vueltas (Todas)")
        md.append(
            "| Vuelta | Tipo / Intensidad | Distancia | Tiempo | Ritmo | FC Med | FC Máx | Cadencia | Desnivel |"
        )
        md.append(
            "| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |"
        )
        for i, lap in enumerate(vueltas, 1):
            l_dist_m = lap.get("total_distance", 0) or 0
            l_dist_km = round(l_dist_m / 1000, 2)
            l_time_s = lap.get("total_timer_time", 0) or 0
            l_time_str = seg_a_tiempo(l_time_s)
            l_ritmo = ms_a_ritmo(lap.get("avg_speed", 0))

            tipo_lap = str(lap.get("intensity", "Lap")).capitalize()
            if tipo_lap == "0" or tipo_lap == "Active":
                tipo_lap = "🔥 Serie (Trabajo)"
            elif tipo_lap == "4" or tipo_lap == "Rest" or tipo_lap == "Recovery":
                tipo_lap = "😮‍💨 Descanso"
            elif tipo_lap == "Warmup":
                tipo_lap = "🏃 Calentamiento"
            elif tipo_lap == "Cooldown":
                tipo_lap = "🧘 Enfriamiento"

            l_fc_med = lap.get("avg_heart_rate", "N/A")
            l_fc_max = lap.get("max_heart_rate", "N/A")

            l_cad = lap.get(
                "avg_running_cadence", lap.get("avg_cadence", "N/A")
            )
            if isinstance(l_cad, (int, float)) and l_cad < 100:
                l_cad *= 2

            l_asc = lap.get("total_ascent", 0) or 0
            l_desc = lap.get("total_descent", 0) or 0

            md.append(
                f"| {i} | {tipo_lap} | {l_dist_km} km | {l_time_str} | {l_ritmo} | {l_fc_med} | {l_fc_max} | {l_cad} | +{l_asc}/-{l_desc}m |"
            )
        md.append("")

    md.append("\n---\n")
    return "\n".join(md), fecha_inicio


def procesar_directorio(
    carpeta_fit,
    modo="individual",
    carpeta_salida="entrenamientos_md",
    archivo_unico="diario_entrenamientos.md",
    max_archivos=0,  # 0, None o Vacío para procesar todos
    fecha_min=None,  # Formato "YYYY-MM-DD" o "YYYY-MM-DD HH:MM" (o tipo datetime)
    fecha_max=None,  # Formato "YYYY-MM-DD" o "YYYY-MM-DD HH:MM" (o tipo datetime)
):
    """Procesa los archivos .FIT filtrando por límites de archivos y rango de fechas.

    Parámetros:
        max_archivos: (int) Límitar número de archivos. 0 o None para sin
        límite.
        fecha_min: (str o datetime) Fecha mínima a procesar (ej. "2026-01-01").
        fecha_max: (str o datetime) Fecha máxima a procesar (ej.
        "2026-12-31").
    """
    # 1. Parsear fechas límite si se pasan como string
    def a_datetime(fecha):
        if isinstance(fecha, str) and fecha.strip():
            for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
                try:
                    return datetime.strptime(fecha.strip(), fmt)
                except ValueError:
                    pass
        elif isinstance(fecha, datetime):
            return fecha
        return None

    dt_min = a_datetime(fecha_min)
    dt_max = a_datetime(fecha_max)

    # 2. Buscar archivos sin duplicados (usando pathlib)
    archivos_fit = [
        str(p)
        for p in Path(carpeta_fit).iterdir()
        if p.suffix.lower() == ".fit"
    ]
    print(f"📁 Encontrados {len(archivos_fit)} archivos .fit en total.")

    if modo == "individual":
        os.makedirs(carpeta_salida, exist_ok=True)

    f_out = None
    if modo == "unico":
        f_out = open(archivo_unico, "a", encoding="utf-8")

    procesados_exito = 0

    try:
        for idx, ruta_fit in enumerate(archivos_fit, 1):
            # Comprobar límite de archivos antes de procesar
            if (
                max_archivos
                and max_archivos > 0
                and procesados_exito >= max_archivos
            ):
                print(
                    f"\n🛑 Se ha alcanzado el límite máximo de {max_archivos} archivos a procesar."
                )
                break

            try:
                # Lectura rápida de fecha para comprobación de rango antes de procesar entero
                fit_temp = fitparse.FitFile(ruta_fit)
                actividad = False
                tipo = None
                fecha_fit = None
                for record in fit_temp.get_messages("file_id"):
                    for data in record:
                        if data.name == "time_created" and data.value:
                            fecha_fit = data.value
                        if data.name == "type":
                            tipo = data.value
                            actividad = tipo == "activity"
                            break
                    if actividad:
                        break
                if not actividad:
                    print(
                        f"⚠️ Omitido y ❌ Eliminado [{os.path.basename(ruta_fit)}]: No es un archivo de actividad válido [{tipo}]."
                    )
                    fit_temp.close()
                    os.remove(ruta_fit)
                    continue
                    
                for record in fit_temp.get_messages("session"):
                    for data in record:
                        if data.name == "start_time":
                            fecha_fit = data.value
                            break
                    if fecha_fit:
                        break

                if fecha_fit == None:
                    for record in fit_temp.get_messages("record"):
                        for data in record:
                            if data.name == "timestamp" and data.value:
                                fecha_fit = data.value
                                break
                        if fecha_fit:
                            break

                if fecha_fit == None:
                    for record in fit_temp.get_messages("file_id"):
                        for data in record:
                            if data.name == "time_created" and data.value:
                                fecha_fit = data.value
                                break
                        if fecha_fit:
                            break      

                # Filtrar por fecha mínima
                if dt_min and fecha_fit and fecha_fit < dt_min:
                    print(
                        f"⏩ Omitido [{os.path.basename(ruta_fit)}]: Fecha {fecha_fit} es anterior a {dt_min}"
                    )
                    continue

                # Filtrar por fecha máxima
                if dt_max and fecha_fit and fecha_fit > dt_max:
                    print(
                        f"⏩ Omitido [{os.path.basename(ruta_fit)}]: Fecha {fecha_fit} es posterior a {dt_max}"
                    )
                    continue

                # Si pasa los filtros, se procesa completamente
                if fecha_fit == None:
                    print(
                        f"⏩ Omitido [{os.path.basename(ruta_fit)}]: Fecha {fecha_fit} no disponible"
                    )                    
                    continue

                print(
                    f"[{procesados_exito + 1}] Procesando: {os.path.basename(ruta_fit)} ({fecha_fit})..."
                )
                contenido_md, fecha = procesar_fit(ruta_fit)

                if modo == "unico":
                    f_out.write(contenido_md + "\n")
                elif modo == "individual":
                    nombre_base = os.path.splitext(
                        os.path.basename(ruta_fit)
                    )[0]
                    if isinstance(fecha, datetime):
                        nom_fecha = fecha.strftime("%Y-%m-%d_%H-%M")
                        nombre_archivo = f"{nom_fecha}_{nombre_base}.md"
                    else:
                        nombre_archivo = f"{nombre_base}.md"

                    ruta_salida = os.path.join(carpeta_salida, nombre_archivo)
                    with open(ruta_salida, "w", encoding="utf-8") as f_ind:
                        f_ind.write(contenido_md)

                procesados_exito += 1

            except Exception as e:
                print(
                    f"⚠️ Error procesando {os.path.basename(ruta_fit)}: {e}"
                )
    finally:
        if f_out:
            f_out.close()

    print(
        f"\n✅ ¡Proceso completado! Se han procesado {procesados_exito} entrenamientos."
    )


# --- EJECUCIÓN ---
# Elige el modo que prefieras: 'individual' o 'unico'
procesar_directorio(
    carpeta_fit="C:\\Users\\rmagroc\\Downloads\\Entrenamientos\\",
    modo="unico",  # <--- Cambia a 'unico' si prefieres todo en un solo archivo
    carpeta_salida="C:\\Users\\rmagroc\\Downloads\\Entrenamientos\\MD\\",
    archivo_unico="Todo2.md",
    max_archivos=1000,  # 0, None o Vacío para procesar todos
    fecha_min="2024-01-01",  # Formato "YYYY-MM-DD" o "YYYY-MM-DD HH:MM" (o tipo datetime)
    fecha_max=None,  # Formato "YYYY-MM-DD" o "YYYY-MM-DD HH:MM" (o tipo datetime)
)