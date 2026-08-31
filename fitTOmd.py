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


# Caracteres sparkline de menor a mayor (bloques Unicode de 1/8 a 8/8)
SPARK_CHARS = "▁▂▃▄▅▆▇█"


def sparkline(valores, ancho=50):
    """Genera una sparkline Unicode a partir de una lista de valores numéricos.
    Los valores se agrupan en 'ancho' segmentos y se mapean a caracteres de bloque."""
    if not valores or len(valores) < 2:
        return ""

    # Agrupar valores en segmentos
    paso = max(1, len(valores) // ancho)
    segmentos = []
    for i in range(0, len(valores), paso):
        chunk = valores[i : i + paso]
        segmentos.append(sum(chunk) / len(chunk))

    if not segmentos:
        return ""

    v_min = min(segmentos)
    v_max = max(segmentos)
    rango = v_max - v_min

    if rango == 0:
        return SPARK_CHARS[4] * len(segmentos)

    resultado = []
    for v in segmentos:
        idx = int(((v - v_min) / rango) * (len(SPARK_CHARS) - 1))
        resultado.append(SPARK_CHARS[idx])

    return "".join(resultado)


def generar_graficos_evolucion(records_completos, vueltas, obtener_velocidad_fn, ms_a_ritmo_fn):
    """Genera sección de gráficos sparkline para la evolución de métricas clave."""
    md = []
    ANCHO = 80  # Caracteres de ancho para los sparklines

    # Extraer series temporales desde records
    hrs = [r["heart_rate"] for r in records_completos if r.get("heart_rate")]
    speeds = [r["speed"] for r in records_completos if r.get("speed") and r["speed"] > 0.5]
    alts = [r["altitude"] for r in records_completos if r.get("altitude")]
    powers = [r["power"] for r in records_completos if r.get("power") and r["power"] > 0]
    cadencias = [r["cadence"] * 2 if r.get("cadence") and r["cadence"] < 100 else r["cadence"] for r in records_completos if r.get("cadence")]
    gcts = [r["stance_time"] for r in records_completos if r.get("stance_time") and r["stance_time"] > 0]
    strides = [r["step_length"] / 1000 if r.get("step_length") and r["step_length"] > 10 else r.get("step_length", 0) for r in records_completos if r.get("step_length") and r["step_length"] > 0]

    if not any([hrs, speeds, alts, powers]):
        return md

    md.append("## 📈 Evolución de la Actividad")
    md.append("")

    if hrs:
        spark_hr = sparkline(hrs, ANCHO)
        md.append(f"**Frecuencia Cardíaca** (min {min(hrs)} — max {max(hrs)} ppm)")
        md.append(f"`{spark_hr}`")
        md.append("")

    if speeds:
        # Ritmo (invertir: más velocidad = menor ritmo = más rápido)
        ritmos_s = [1000 / s for s in speeds]
        spark_ritmo = sparkline([-r for r in ritmos_s], ANCHO)
        ritmo_min_s = min(ritmos_s)
        ritmo_max_s = max(ritmos_s)
        r_min = f"{int(ritmo_min_s // 60)}:{int(ritmo_min_s % 60):02d}"
        r_max = f"{int(ritmo_max_s // 60)}:{int(ritmo_max_s % 60):02d}"
        md.append(f"**Ritmo** (rápido {r_min} — lento {r_max} min/km) *arriba = más rápido*")
        md.append(f"`{spark_ritmo}`")
        md.append("")

    if alts:
        spark_alt = sparkline(alts, ANCHO)
        md.append(f"**Altitud** (min {round(min(alts), 1)} — max {round(max(alts), 1)} m)")
        md.append(f"`{spark_alt}`")
        md.append("")

    if powers:
        spark_pw = sparkline(powers, ANCHO)
        md.append(f"**Potencia** (min {min(powers)} — max {max(powers)} W)")
        md.append(f"`{spark_pw}`")
        md.append("")

    # Carrera / Caminar: línea de tiempo
    if speeds:
        UMBRAL_CAMINAR = 1.8  # m/s (~9:15 min/km)
        paso = max(1, len(speeds) // ANCHO)
        timeline = []
        for i in range(0, len(speeds), paso):
            chunk = speeds[i : i + paso]
            media_chunk = sum(chunk) / len(chunk)
            if media_chunk >= UMBRAL_CAMINAR:
                timeline.append("█")  # Corriendo
            else:
                timeline.append("░")  # Caminando
        pct_corriendo = sum(1 for s in speeds if s >= UMBRAL_CAMINAR) / len(speeds) * 100
        pct_caminando = 100 - pct_corriendo
        md.append(f"**Carrera / Caminar** (█ corriendo {pct_corriendo:.0f}% — ░ caminando {pct_caminando:.0f}%)")
        md.append(f"`{''.join(timeline)}`")
        md.append("")

    if cadencias:
        spark_cad = sparkline(cadencias, ANCHO)
        md.append(f"**Cadencia** (min {min(cadencias)} — max {max(cadencias)} ppm)")
        md.append(f"`{spark_cad}`")
        md.append("")

    if strides:
        spark_stride = sparkline(strides, ANCHO)
        md.append(f"**Longitud de zancada** (min {min(strides):.2f} — max {max(strides):.2f} m)")
        md.append(f"`{spark_stride}`")
        md.append("")

    if gcts:
        spark_gct = sparkline(gcts, ANCHO)
        md.append(f"**Tiempo de contacto con el suelo** (min {min(gcts):.0f} — max {max(gcts):.0f} ms)")
        md.append(f"`{spark_gct}`")
        md.append("")

    # Gráfico de eficiencia por lap (velocidad/FC)
    eficiencias_lap = []
    for lap in vueltas:
        speed = obtener_velocidad_fn(lap)
        hr = lap.get("avg_heart_rate")
        if speed and hr and speed > 0 and hr > 0:
            eficiencias_lap.append(round((speed / hr) * 1000, 1))
        else:
            eficiencias_lap.append(0)

    if eficiencias_lap and max(eficiencias_lap) > 0:
        max_ef = max(eficiencias_lap)
        md.append("**Eficiencia por vuelta** (velocidad/FC — mayor = mejor)")
        md.append("```")
        for i, ef in enumerate(eficiencias_lap, 1):
            if ef > 0:
                bar_len = int((ef / max_ef) * 40)
                bar = "█" * bar_len
                md.append(f"  Lap {i:>2d} | {bar} {ef}")
            else:
                md.append(f"  Lap {i:>2d} | — sin datos")
        md.append("```")
        md.append("")

    return md


def procesar_fit(archivo_fit, titulo_personalizado=None, notas_personalizadas=None):
    fitfile = fitparse.FitFile(archivo_fit)

    # 1. Leer mensaje de la Sesión principal
    datos_sesion = {}
    for record in fitfile.get_messages("session"):
        for data in record:
            # No sobreescribir un valor válido con None (campos duplicados en FIT)
            if data.value is not None or data.name not in datos_sesion:
                datos_sesion[data.name] = data.value

    # 2. Leer vueltas (Laps)
    vueltas = []
    for lap in fitfile.get_messages("lap"):
        l_data = {}
        for data in lap:
            # No sobreescribir un valor válido con None (campos duplicados en FIT)
            if data.value is not None or data.name not in l_data:
                l_data[data.name] = data.value
        vueltas.append(l_data)

    # 3. Leer records individuales para zonas de FC y métricas derivadas
    records_fc = []
    records_speed = []
    records_power = []
    records_completos = []
    for record in fitfile.get_messages("record"):
        r_data = {}
        for data in record:
            if data.value is not None:
                if data.name == "heart_rate":
                    r_data["heart_rate"] = data.value
                elif data.name == "enhanced_speed":
                    r_data["speed"] = data.value
                elif data.name == "power":
                    r_data["power"] = data.value
                elif data.name == "enhanced_altitude":
                    r_data["altitude"] = data.value
                elif data.name == "cadence":
                    r_data["cadence"] = data.value
                elif data.name == "stance_time":
                    r_data["stance_time"] = data.value
                elif data.name == "vertical_oscillation":
                    r_data["vertical_oscillation"] = data.value
                elif data.name == "step_length":
                    r_data["step_length"] = data.value
        records_completos.append(r_data)
        if r_data.get("heart_rate"):
            records_fc.append(r_data)
        if r_data.get("speed"):
            records_speed.append(r_data)
        if r_data.get("power"):
            records_power.append(r_data)

    # 4. Leer estructura del workout programado (si existe)
    workout_steps = []
    for msg in fitfile.get_messages("workout_step"):
        step = {}
        for data in msg:
            if data.value is not None and "unknown" not in data.name:
                step[data.name] = data.value
        if step:
            workout_steps.append(step)

    # Helpers de conversión
    def ms_a_ritmo(velocidad_ms):
        """Convierte velocidad en m/s a ritmo min/km. Acepta enhanced_avg_speed como fallback."""
        if velocidad_ms and velocidad_ms > 0:
            sec_per_km = 1000 / velocidad_ms
            return f"{int(sec_per_km // 60)}:{int(sec_per_km % 60):02d} min/km"
        return "N/A"

    def obtener_velocidad(datos, campo_normal="avg_speed", campo_enhanced="enhanced_avg_speed"):
        """Obtiene velocidad priorizando enhanced sobre normal."""
        return datos.get(campo_enhanced) or datos.get(campo_normal)

    def seg_a_tiempo(segundos):
        if segundos is not None and segundos > 0:
            return str(timedelta(seconds=int(segundos)))
        return "N/A"

    # --- DATOS GENERALES ---
    deporte = str(datos_sesion.get("sport", "Desconocido")).capitalize()
    sub_deporte = str(datos_sesion.get("sub_sport", "")).capitalize()
    fecha_inicio = datos_sesion.get("start_time", "Desconocida")

    # Nombre del entrenamiento (si viene de un workout programado)
    nombre_workout = None
    for record in fitfile.get_messages("workout"):
        for data in record:
            if data.name == "wkt_name" and data.value:
                nombre_workout = data.value
                break
        if nombre_workout:
            break

    # Calorías
    calorias_activas = datos_sesion.get("total_calories", "N/A")

    # Training Effect
    te_aerobico = datos_sesion.get("total_training_effect", "N/A")
    te_anaerobico = datos_sesion.get("total_anaerobic_training_effect", "N/A")

    # FC, Tiempo y Potencia
    fc_media = datos_sesion.get("avg_heart_rate", "N/A")
    fc_maxima = datos_sesion.get("max_heart_rate", "N/A")
    tiempo_total = seg_a_tiempo(datos_sesion.get("total_timer_time"))
    potencia_media = datos_sesion.get("avg_power", "N/A")
    potencia_maxima = datos_sesion.get("max_power", "N/A")

    # Altitud (calcular min/max desde los laps)
    ascenso_total = datos_sesion.get("total_ascent", "N/A")
    descenso_total = datos_sesion.get("total_descent", "N/A")
    
    # Obtener altitud min/max desde laps (no está en sesión pero sí en cada lap)
    altitudes_min = [lap.get("enhanced_min_altitude") for lap in vueltas if lap.get("enhanced_min_altitude") is not None]
    altitudes_max = [lap.get("enhanced_max_altitude") for lap in vueltas if lap.get("enhanced_max_altitude") is not None]
    altura_minima = round(min(altitudes_min), 1) if altitudes_min else "N/A"
    altura_maxima = round(max(altitudes_max), 1) if altitudes_max else "N/A"

    # Ritmos (priorizar enhanced sobre normal)
    ritmo_medio = ms_a_ritmo(obtener_velocidad(datos_sesion, "avg_speed", "enhanced_avg_speed"))
    ritmo_movimiento = ms_a_ritmo(datos_sesion.get("enhanced_avg_speed"))
    ritmo_optimo = ms_a_ritmo(obtener_velocidad(datos_sesion, "max_speed", "enhanced_max_speed"))

    # Métricas avanzadas de rendimiento
    distancia_total_m = datos_sesion.get("total_distance", 0) or 0
    distancia_total_km = round(distancia_total_m / 1000, 2)
    potencia_normalizada = datos_sesion.get("normalized_power", "N/A")
    total_zancadas = datos_sesion.get("total_strides", "N/A")
    tiempo_transcurrido = datos_sesion.get("total_elapsed_time", 0) or 0
    tiempo_en_movimiento = datos_sesion.get("total_timer_time", 0) or 0
    tiempo_pausa = tiempo_transcurrido - tiempo_en_movimiento if tiempo_transcurrido and tiempo_en_movimiento else 0

    # Drift cardíaco (comparar FC media 1ª mitad vs 2ª mitad)
    drift_cardiaco = "N/A"
    if len(records_fc) > 20:
        mitad = len(records_fc) // 2
        fc_primera_mitad = [r["heart_rate"] for r in records_fc[:mitad]]
        fc_segunda_mitad = [r["heart_rate"] for r in records_fc[mitad:]]
        fc_media_1 = sum(fc_primera_mitad) / len(fc_primera_mitad)
        fc_media_2 = sum(fc_segunda_mitad) / len(fc_segunda_mitad)
        drift_pct = ((fc_media_2 - fc_media_1) / fc_media_1) * 100
        drift_cardiaco = f"{drift_pct:+.1f}% ({round(fc_media_1)} → {round(fc_media_2)} ppm)"

    # Variabilidad de ritmo (coeficiente de variación de velocidad)
    variabilidad_ritmo = "N/A"
    if len(records_speed) > 20:
        velocidades = [r["speed"] for r in records_speed if r["speed"] > 0.5]  # Filtrar paradas
        if velocidades:
            media_vel = sum(velocidades) / len(velocidades)
            varianza = sum((v - media_vel) ** 2 for v in velocidades) / len(velocidades)
            desv_std = varianza ** 0.5
            cv = (desv_std / media_vel) * 100
            variabilidad_ritmo = f"{cv:.1f}%"

    # Índice de eficiencia (velocidad media / FC media)
    indice_eficiencia = "N/A"
    vel_media = obtener_velocidad(datos_sesion, "avg_speed", "enhanced_avg_speed")
    if vel_media and isinstance(fc_media, (int, float)) and fc_media > 0:
        # m/s por ppm - multiplicado por 1000 para legibilidad
        ie = (vel_media / fc_media) * 1000
        indice_eficiencia = f"{ie:.2f}"

    # --- MÉTRICAS PREMIUM ---

    # Intensity Factor (IF) = Potencia Normalizada / FTP estimado
    # Estimamos FTP como 95% de la potencia máxima de la sesión (aproximación si no se conoce)
    intensity_factor = "N/A"
    np_val = datos_sesion.get("normalized_power")
    max_pow = datos_sesion.get("max_power")
    if np_val and max_pow and max_pow > 0:
        ftp_estimado = max_pow * 0.75  # Aproximación conservadora
        if_val = np_val / ftp_estimado
        intensity_factor = f"{if_val:.2f}"

    # Training Stress Score (TSS) = (duración_s * NP * IF) / (FTP * 3600) * 100
    tss = "N/A"
    if np_val and max_pow and tiempo_en_movimiento and tiempo_en_movimiento > 0:
        ftp_estimado = max_pow * 0.75
        if ftp_estimado > 0:
            if_val = np_val / ftp_estimado
            tss_val = (tiempo_en_movimiento * np_val * if_val) / (ftp_estimado * 3600) * 100
            tss = f"{tss_val:.0f}"

    # Desacoplamiento Potencia:FC (Pw:Hr) - compara ratio potencia/FC entre 1ª y 2ª mitad
    desacoplamiento = "N/A"
    records_con_pw_hr = [r for r in records_completos if r.get("power") and r.get("heart_rate") and r["power"] > 0 and r["heart_rate"] > 0]
    if len(records_con_pw_hr) > 40:
        mitad = len(records_con_pw_hr) // 2
        ratio_1 = sum(r["power"] for r in records_con_pw_hr[:mitad]) / sum(r["heart_rate"] for r in records_con_pw_hr[:mitad])
        ratio_2 = sum(r["power"] for r in records_con_pw_hr[mitad:]) / sum(r["heart_rate"] for r in records_con_pw_hr[mitad:])
        if ratio_1 > 0:
            desacop_pct = ((ratio_1 - ratio_2) / ratio_1) * 100
            desacoplamiento = f"{desacop_pct:+.1f}%"

    # Economía de carrera (potencia media / velocidad media en m/s)
    economia_carrera = "N/A"
    if vel_media and isinstance(potencia_media, (int, float)) and vel_media > 0:
        eco = potencia_media / vel_media
        economia_carrera = f"{eco:.1f} W/(m/s)"

    # Zonas de Potencia (basadas en FTP estimado)
    zonas_potencia = []
    if records_power and max_pow:
        ftp_est = max_pow * 0.75
        ZONAS_POT = {
            "Z1 (Recuperación)": (0, ftp_est * 0.55),
            "Z2 (Resistencia)": (ftp_est * 0.55, ftp_est * 0.75),
            "Z3 (Tempo)": (ftp_est * 0.75, ftp_est * 0.90),
            "Z4 (Umbral)": (ftp_est * 0.90, ftp_est * 1.05),
            "Z5 (VO2 Máx)": (ftp_est * 1.05, ftp_est * 1.20),
            "Z6 (Anaeróbico)": (ftp_est * 1.20, ftp_est * 5),
        }
        tiempos_pot = {z: 0 for z in ZONAS_POT}
        total_pot = 0
        for r in records_power:
            pw = r["power"]
            total_pot += 1
            for zona, (lo, hi) in ZONAS_POT.items():
                if lo <= pw < hi:
                    tiempos_pot[zona] += 1
                    break
        if total_pot > 0:
            for zona, segs in tiempos_pot.items():
                pct = (segs / total_pot) * 100
                zonas_potencia.append((zona, str(timedelta(seconds=segs)), round(pct, 1)))

    # Índice de fatiga por lap (comparar ritmo/FC del primer y último lap similar)
    fatiga_por_laps = "N/A"
    laps_con_datos = [l for l in vueltas if l.get("avg_heart_rate") and obtener_velocidad(l) and obtener_velocidad(l) > 0]
    if len(laps_con_datos) >= 3:
        primer_lap = laps_con_datos[0]
        ultimo_lap = laps_con_datos[-2] if len(laps_con_datos) > 2 else laps_con_datos[-1]  # Evitar el parcial final
        ef_inicio = obtener_velocidad(primer_lap) / primer_lap["avg_heart_rate"]
        ef_fin = obtener_velocidad(ultimo_lap) / ultimo_lap["avg_heart_rate"]
        if ef_inicio > 0:
            fatiga_pct = ((ef_inicio - ef_fin) / ef_inicio) * 100
            fatiga_por_laps = f"{fatiga_pct:+.1f}%"

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

    # Notas de la actividad
    notas = datos_sesion.get("notes", None)
    if not notas:
        # Buscar en mensajes "activity"
        for record in fitfile.get_messages("activity"):
            for data in record:
                if data.name == "notes" and data.value:
                    notas = data.value
                    break
            if notas:
                break
    if not notas:
        # Buscar en mensajes "sport"
        for record in fitfile.get_messages("sport"):
            for data in record:
                if data.name in ("name", "notes") and data.value:
                    if data.name == "notes":
                        notas = data.value
                        break
            if notas:
                break

    # --- FORMATO MARKDOWN EN TABLAS RESUMEN ---
    md = []
    if titulo_personalizado and titulo_personalizado.strip():
        md.append(f"# 🏃‍♂️ {titulo_personalizado.strip()} — {fecha_inicio}")
    elif nombre_workout:
        md.append(f"# 🏃‍♂️ {nombre_workout} — {fecha_inicio}")
    else:
        md.append(f"# 🏃‍♂️ Entrenamiento: {fecha_inicio}")

    # --- NOTAS (justo después del título) ---
    notas_finales = notas_personalizadas if notas_personalizadas and notas_personalizadas.strip() else notas
    if notas_finales:
        md.append("")
        md.append("## 📝 Notas")
        md.append(f"{notas_finales}")
        md.append("")

    md.append("## 📊 Resumen General de Métricas")

    md.append("### 🔥 Calorías")
    md.append("| Métrica | Valor |")
    md.append("| :--- | :--- |")
    md.append(f"| **Calorías activas** | `{calorias_activas} kcal` |")
    md.append("")

    md.append("### 📏 Volumen")
    md.append("| Métrica | Valor |")
    md.append("| :--- | :--- |")
    md.append(f"| **Distancia total** | `{distancia_total_km} km` |")
    md.append(f"| **Tiempo en movimiento** | `{seg_a_tiempo(tiempo_en_movimiento)}` |")
    md.append(f"| **Tiempo transcurrido** | `{seg_a_tiempo(tiempo_transcurrido)}` |")
    if tiempo_pausa > 30:
        md.append(f"| **Tiempo en pausa** | `{seg_a_tiempo(tiempo_pausa)}` |")
    md.append(f"| **Total de zancadas** | `{total_zancadas}` |")
    md.append("")

    md.append("### 📈 EFECTO DE ENTRENAMIENTO (Training Effect)")
    md.append("| Métrica | Valor |")
    md.append("| :--- | :--- |")
    md.append(f"| **Training Effect (Aeróbico / Anaeróbico)** | `{te_aerobico} / {te_anaerobico}` |")
    md.append("")

    md.append("### 🫀 Frecuencia Cardíaca y Tiempo")
    md.append("| Métrica | Valor |")
    md.append("| :--- | :--- |")
    md.append(f"| **FC Media** | `{fc_media} ppm` |")
    md.append(f"| **FC Máxima** | `{fc_maxima} ppm` |")
    md.append("")

    md.append("### ⚡ Potencia")
    md.append("| Métrica | Valor |")
    md.append("| :--- | :--- |")
    md.append(f"| **Potencia media** | `{potencia_media} W` |")
    md.append(f"| **Potencia normalizada** | `{potencia_normalizada} W` |")
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

    md.append("### ⏱️ Ritmo")
    md.append("| Métrica | Valor |")
    md.append("| :--- | :--- |")
    md.append(f"| **Ritmo medio** | `{ritmo_medio}` |")
    md.append(f"| **Ritmo medio en movimiento** | `{ritmo_movimiento}` |")
    md.append(f"| **Ritmo óptimo (Máximo)** | `{ritmo_optimo}` |")
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

    # --- ZONAS DE FRECUENCIA CARDÍACA ---
    resumen_zonas = calcular_zonas_fc(records_fc)
    if resumen_zonas:
        md.append("### ❤️ Zonas de Frecuencia Cardíaca")
        md.append("| Zona | Tiempo | % del total |")
        md.append("| :--- | :---: | :---: |")
        for zona, tiempo_fmt, pct in resumen_zonas:
            barra = "█" * int(pct // 5) + "░" * (20 - int(pct // 5))
            md.append(f"| **{zona}** | `{tiempo_fmt}` | `{pct}%` {barra} |")
        md.append("")

    # --- INDICADORES DE RENDIMIENTO ---
    md.append("### 🧠 Indicadores de Rendimiento")
    md.append("| Métrica | Valor | Interpretación |")
    md.append("| :--- | :---: | :--- |")
    md.append(f"| **Drift cardíaco** | `{drift_cardiaco}` | Fatiga aeróbica (<5% = bueno) |")
    md.append(f"| **Variabilidad de ritmo (CV)** | `{variabilidad_ritmo}` | Regularidad (menor = más estable) |")
    md.append(f"| **Índice de eficiencia** | `{indice_eficiencia}` | Velocidad/FC (mayor = más eficiente) |")
    md.append(f"| **Intensity Factor (IF)** | `{intensity_factor}` | Intensidad relativa al FTP (<1.0 = sub-umbral) |")
    md.append(f"| **Training Stress Score (TSS)** | `{tss}` | Carga de entrenamiento (<150 = recuperable en 24h) |")
    md.append(f"| **Desacoplamiento Pw:Hr** | `{desacoplamiento}` | Fatiga aeróbica (<5% = buena base) |")
    md.append(f"| **Economía de carrera** | `{economia_carrera}` | Potencia necesaria por velocidad (menor = mejor) |")
    md.append(f"| **Índice de fatiga** | `{fatiga_por_laps}` | Pérdida de eficiencia inicio vs fin |")
    md.append("")

    # --- ZONAS DE POTENCIA ---
    if zonas_potencia:
        md.append("### ⚡ Zonas de Potencia")
        md.append("| Zona | Tiempo | % del total |")
        md.append("| :--- | :---: | :---: |")
        for zona, tiempo_fmt, pct in zonas_potencia:
            barra = "█" * int(pct // 5) + "░" * (20 - int(pct // 5))
            md.append(f"| **{zona}** | `{tiempo_fmt}` | `{pct}%` {barra} |")
        md.append("")

    # --- DETECCIÓN DEL TIPO DE ENTRENAMIENTO ---
    # Analizar las intensidades de las vueltas para clasificar el entrenamiento
    intensidades_unicas = set()
    for lap in vueltas:
        intensidad = lap.get("intensity", "")
        if intensidad is not None:
            intensidades_unicas.add(str(intensidad).lower())

    # Clasificación:
    # - INTERVALOS: tiene mezcla de warmup/active/cooldown y rest (intensity=4)
    # - RODAJE CONTINUO: todas las vueltas tienen la misma intensidad (ej. "5") 
    #   o son solo "active" con trigger "distance" (auto-lap)
    es_intervalos = bool(
        intensidades_unicas & {"warmup", "cooldown"}
        or ({"active", "4"}.issubset(intensidades_unicas))
    )

    if es_intervalos:
        # --- ANÁLISIS DE SERIES / INTERVALOS ---
        # Separar en fases: calentamiento, series de trabajo, descansos, enfriamiento
        laps_calentamiento = []
        laps_trabajo = []
        laps_descanso = []
        laps_enfriamiento = []

        for lap in vueltas:
            intensidad = str(lap.get("intensity", "")).lower()
            if intensidad == "warmup":
                laps_calentamiento.append(lap)
            elif intensidad in ["active", "0"]:
                laps_trabajo.append(lap)
            elif intensidad in ["4", "rest", "recovery"]:
                laps_descanso.append(lap)
            elif intensidad == "cooldown":
                laps_enfriamiento.append(lap)

        md.append("## 🎯 Análisis de Intervalos")
        md.append("")

        # Estructura programada del workout (si existe)
        if workout_steps:
            md.append("### 📋 Entrenamiento Programado (planificado)")
            for step in workout_steps:
                intensidad_step = str(step.get("intensity", "")).lower()
                dur_type = step.get("duration_type", "")
                dur_time = step.get("duration_time")
                repeat = step.get("repeat_steps")
                target_type = step.get("target_type", "")
                speed_low = step.get("custom_target_speed_low")
                speed_high = step.get("custom_target_speed_high")
                notes_step = step.get("notes", "")

                if dur_type == "repeat_until_steps_cmplt" and repeat:
                    md.append(f"- **Repeticiones:** {repeat}x")
                elif intensidad_step == "warmup":
                    md.append(f"- **Calentamiento:** duración libre")
                elif intensidad_step == "cooldown":
                    md.append(f"- **Enfriamiento:** duración libre")
                elif intensidad_step in ["active", "0"]:
                    dur_str = f"{int(dur_time)}s" if dur_time else "libre"
                    ritmo_obj = ""
                    if speed_low and speed_high and target_type == "speed":
                        ritmo_low = ms_a_ritmo(speed_low)
                        ritmo_high = ms_a_ritmo(speed_high)
                        ritmo_obj = f" a {ritmo_high} - {ritmo_low}"
                    md.append(f"- **Serie activa:** {dur_str}{ritmo_obj}")
                elif intensidad_step in ["4", "rest", "recovery"]:
                    dur_str = f"{int(dur_time)}s" if dur_time else "libre"
                    extra = f" ({notes_step})" if notes_step else ""
                    md.append(f"- **Descanso:** {dur_str}{extra}")
            md.append("")

        # Resumen de la estructura del entrenamiento
        if laps_calentamiento:
            dist_calent = sum(l.get("total_distance", 0) or 0 for l in laps_calentamiento)
            tiempo_calent = sum(l.get("total_timer_time", 0) or 0 for l in laps_calentamiento)
            ritmo_calent = ms_a_ritmo(dist_calent / tiempo_calent if tiempo_calent > 0 else 0)
            md.append(f"### 🔥 Calentamiento")
            md.append(f"- **Distancia:** {round(dist_calent/1000, 2)} km")
            md.append(f"- **Tiempo:** {seg_a_tiempo(tiempo_calent)}")
            md.append(f"- **Ritmo medio:** {ritmo_calent}")
            md.append("")

        # Tabla de series de trabajo
        if laps_trabajo:
            md.append("### 💪 Series de Trabajo")
            md.append(
                "| Serie | Distancia | Tiempo | Ritmo | FC Media | FC Máx | Cadencia | Potencia | NP | Zancada | GCT | Pendiente |"
            )
            md.append(
                "| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |"
            )

            for num, lap in enumerate(laps_trabajo, 1):
                l_dist_m = lap.get("total_distance", 0) or 0
                l_dist_km = round(l_dist_m / 1000, 2)
                l_time_s = lap.get("total_timer_time", 0) or 0
                l_time_str = seg_a_tiempo(l_time_s)
                l_speed = obtener_velocidad(lap)
                l_ritmo = ms_a_ritmo(l_speed)
                l_fc_med = lap.get("avg_heart_rate", "N/A")
                l_fc_max = lap.get("max_heart_rate", "N/A")

                l_cad = lap.get("avg_running_cadence", lap.get("avg_cadence", "N/A"))
                if isinstance(l_cad, (int, float)) and l_cad < 100:
                    l_cad *= 2

                l_pot = lap.get("avg_power", "N/A")
                l_np = lap.get("normalized_power", "N/A")

                # Longitud de zancada
                l_zancada = lap.get("avg_step_length", "N/A")
                if isinstance(l_zancada, (int, float)):
                    l_zancada = round(l_zancada / 1000, 2) if l_zancada > 10 else round(l_zancada, 2)

                # Tiempo de contacto con el suelo (GCT)
                l_gct = lap.get("avg_stance_time", "N/A")
                if isinstance(l_gct, (int, float)):
                    l_gct = f"{round(l_gct)}ms"

                # Pendiente (% desnivel positivo y negativo)
                l_asc = lap.get("total_ascent", 0) or 0
                l_desc = lap.get("total_descent", 0) or 0
                if l_dist_m > 0:
                    pend_pos = round((l_asc / l_dist_m) * 100, 1)
                    pend_neg = round((l_desc / l_dist_m) * 100, 1)
                    l_pendiente = f"+{pend_pos}%/-{pend_neg}%"
                else:
                    l_pendiente = "N/A"

                md.append(
                    f"| **{num}** | {l_dist_km} km ({int(l_dist_m)}m) | {l_time_str} | **{l_ritmo}** | {l_fc_med} ppm | {l_fc_max} ppm | {l_cad} ppm | {l_pot} W | {l_np} W | {l_zancada} m | {l_gct} | {l_pendiente} |"
                )

            md.append("")

            # Resumen de descansos
            if laps_descanso:
                dist_desc = sum(l.get("total_distance", 0) or 0 for l in laps_descanso)
                tiempo_desc = sum(l.get("total_timer_time", 0) or 0 for l in laps_descanso)
                ritmo_desc = ms_a_ritmo(dist_desc / tiempo_desc if tiempo_desc > 0 else 0)
                md.append(f"### 😮‍💨 Descansos entre series")
                md.append(f"- **Nº de descansos:** {len(laps_descanso)}")
                md.append(f"- **Tiempo total de descanso:** {seg_a_tiempo(tiempo_desc)}")
                md.append(f"- **Distancia en descansos:** {round(dist_desc/1000, 2)} km")
                md.append(f"- **Ritmo medio en descanso:** {ritmo_desc}")
                md.append("")

        # Enfriamiento
        if laps_enfriamiento:
            dist_enfr = sum(l.get("total_distance", 0) or 0 for l in laps_enfriamiento)
            tiempo_enfr = sum(l.get("total_timer_time", 0) or 0 for l in laps_enfriamiento)
            ritmo_enfr = ms_a_ritmo(dist_enfr / tiempo_enfr if tiempo_enfr > 0 else 0)
            md.append(f"### 🧘 Enfriamiento")
            md.append(f"- **Distancia:** {round(dist_enfr/1000, 2)} km")
            md.append(f"- **Tiempo:** {seg_a_tiempo(tiempo_enfr)}")
            md.append(f"- **Ritmo medio:** {ritmo_enfr}")
            md.append("")

    else:
        # --- RODAJE CONTINUO / VUELTAS AUTOMÁTICAS ---
        md.append("## 🏃 Desglose por Kilómetro")
        md.append(
            "| Km | Distancia | Tiempo | Ritmo | FC Media | FC Máx | Cadencia | Potencia | NP | Zancada | GCT | Pendiente |"
        )
        md.append(
            "| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |"
        )

        dist_acumulada = 0
        for i, lap in enumerate(vueltas, 1):
            l_dist_m = lap.get("total_distance", 0) or 0
            l_dist_km = round(l_dist_m / 1000, 2)
            dist_acumulada += l_dist_m
            l_time_s = lap.get("total_timer_time", 0) or 0
            l_time_str = seg_a_tiempo(l_time_s)
            l_speed = obtener_velocidad(lap)
            l_ritmo = ms_a_ritmo(l_speed)
            l_fc_med = lap.get("avg_heart_rate", "N/A")
            l_fc_max = lap.get("max_heart_rate", "N/A")

            l_cad = lap.get("avg_running_cadence", lap.get("avg_cadence", "N/A"))
            if isinstance(l_cad, (int, float)) and l_cad < 100:
                l_cad *= 2

            l_pot = lap.get("avg_power", "N/A")
            l_np = lap.get("normalized_power", "N/A")

            # Longitud de zancada
            l_zancada = lap.get("avg_step_length", "N/A")
            if isinstance(l_zancada, (int, float)):
                l_zancada = round(l_zancada / 1000, 2) if l_zancada > 10 else round(l_zancada, 2)

            # Tiempo de contacto con el suelo (GCT)
            l_gct = lap.get("avg_stance_time", "N/A")
            if isinstance(l_gct, (int, float)):
                l_gct = f"{round(l_gct)}ms"

            # Pendiente (% desnivel positivo y negativo)
            l_asc = lap.get("total_ascent", 0) or 0
            l_desc = lap.get("total_descent", 0) or 0
            if l_dist_m > 0:
                pend_pos = round((l_asc / l_dist_m) * 100, 1)
                pend_neg = round((l_desc / l_dist_m) * 100, 1)
                l_pendiente = f"+{pend_pos}%/-{pend_neg}%"
            else:
                l_pendiente = "N/A"

            # Para la última vuelta parcial, indicarlo
            trigger = str(lap.get("lap_trigger", "")).lower()
            etiqueta_km = f"**{i}**" if trigger != "session_end" else f"*{i} (parcial)*"

            md.append(
                f"| {etiqueta_km} | {l_dist_km} km | {l_time_str} | **{l_ritmo}** | {l_fc_med} ppm | {l_fc_max} ppm | {l_cad} ppm | {l_pot} W | {l_np} W | {l_zancada} m | {l_gct} | {l_pendiente} |"
            )

        md.append("")

        # Resumen del rodaje
        dist_total_km = round(dist_acumulada / 1000, 2)
        ritmos_validos = []
        for lap in vueltas:
            s = obtener_velocidad(lap)
            if s and s > 0:
                ritmos_validos.append(1000 / s)

        if ritmos_validos:
            ritmo_mas_rapido = min(ritmos_validos)
            ritmo_mas_lento = max(ritmos_validos)
            diferencia = ritmo_mas_lento - ritmo_mas_rapido

            md.append("### 📊 Resumen del Rodaje")
            md.append("| Métrica | Valor |")
            md.append("| :--- | :--- |")
            md.append(f"| **Distancia total** | `{dist_total_km} km` |")
            md.append(f"| **Km más rápido** | `{int(ritmo_mas_rapido // 60)}:{int(ritmo_mas_rapido % 60):02d} min/km` |")
            md.append(f"| **Km más lento** | `{int(ritmo_mas_lento // 60)}:{int(ritmo_mas_lento % 60):02d} min/km` |")
            md.append(f"| **Diferencia máxima** | `{int(diferencia // 60)}:{int(diferencia % 60):02d} min/km` |")
            md.append("")

    # --- GRÁFICOS DE EVOLUCIÓN ---
    graficos = generar_graficos_evolucion(records_completos, vueltas, obtener_velocidad, ms_a_ritmo)
    md.extend(graficos)

    # --- TABLA DE DESGLOSE COMPLETO POR VUELTAS (LAPS) ---
    if vueltas:
        md.append("## ⏱️ Desglose General de Vueltas (Todas)")
        md.append(
            "| Vuelta | Tipo | Distancia | Tiempo | Ritmo | FC Med | FC Máx | Cadencia | Potencia | NP | Zancada | GCT | Pendiente | Eficiencia |"
        )
        md.append(
            "| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |"
        )
        for i, lap in enumerate(vueltas, 1):
            l_dist_m = lap.get("total_distance", 0) or 0
            l_dist_km = round(l_dist_m / 1000, 2)
            l_time_s = lap.get("total_timer_time", 0) or 0
            l_time_str = seg_a_tiempo(l_time_s)
            l_speed = obtener_velocidad(lap)
            l_ritmo = ms_a_ritmo(l_speed)

            tipo_lap = str(lap.get("intensity", "Lap")).capitalize()
            if tipo_lap in ["0", "Active"]:
                tipo_lap = "🔥 Trabajo"
            elif tipo_lap in ["4", "Rest", "Recovery"]:
                tipo_lap = "😮‍💨 Descanso"
            elif tipo_lap == "Warmup":
                tipo_lap = "🏃 Calent."
            elif tipo_lap == "Cooldown":
                tipo_lap = "🧘 Enfr."
            elif tipo_lap == "5":
                tipo_lap = "🏃 Auto"

            l_fc_med = lap.get("avg_heart_rate", "N/A")
            l_fc_max = lap.get("max_heart_rate", "N/A")

            l_cad = lap.get(
                "avg_running_cadence", lap.get("avg_cadence", "N/A")
            )
            if isinstance(l_cad, (int, float)) and l_cad < 100:
                l_cad *= 2

            l_pot = lap.get("avg_power", "N/A")
            l_np = lap.get("normalized_power", "N/A")

            # Longitud de zancada
            l_zancada = lap.get("avg_step_length", "N/A")
            if isinstance(l_zancada, (int, float)):
                l_zancada = round(l_zancada / 1000, 2) if l_zancada > 10 else round(l_zancada, 2)

            # GCT
            l_gct = lap.get("avg_stance_time", "N/A")
            if isinstance(l_gct, (int, float)):
                l_gct = f"{round(l_gct)}ms"

            # Pendiente
            l_asc = lap.get("total_ascent", 0) or 0
            l_desc = lap.get("total_descent", 0) or 0
            if l_dist_m > 0:
                pend_pos = round((l_asc / l_dist_m) * 100, 1)
                pend_neg = round((l_desc / l_dist_m) * 100, 1)
                l_pendiente = f"+{pend_pos}%/-{pend_neg}%"
            else:
                l_pendiente = "N/A"

            # Eficiencia por lap (velocidad/FC)
            l_eficiencia = "N/A"
            if l_speed and isinstance(l_fc_med, (int, float)) and l_speed > 0 and l_fc_med > 0:
                l_eficiencia = f"{(l_speed / l_fc_med) * 1000:.1f}"

            md.append(
                f"| {i} | {tipo_lap} | {l_dist_km} km | {l_time_str} | {l_ritmo} | {l_fc_med} | {l_fc_max} | {l_cad} | {l_pot} W | {l_np} W | {l_zancada} m | {l_gct} | {l_pendiente} | {l_eficiencia} |"
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


def procesar_archivo_temporal(ruta_fit, titulo=None, notas=None):
    """Procesa un único archivo .FIT y devuelve el contenido markdown.

    Parámetros:
        ruta_fit: (str) Ruta al archivo .fit temporal.
        titulo: (str) Título personalizado para la actividad (opcional).
        notas: (str) Notas personalizadas para la actividad (opcional).

    Retorna:
        str: Contenido markdown generado a partir del archivo .fit.

    Lanza:
        FileNotFoundError: Si el archivo no existe.
        ValueError: Si el archivo no es una actividad válida.
    """
    if not os.path.isfile(ruta_fit):
        raise FileNotFoundError(f"No se encontró el archivo: {ruta_fit}")

    # Validar que sea un archivo de actividad
    fit_temp = fitparse.FitFile(ruta_fit)
    es_actividad = False
    for record in fit_temp.get_messages("file_id"):
        for data in record:
            if data.name == "type" and data.value == "activity":
                es_actividad = True
                break
        if es_actividad:
            break

    if not es_actividad:
        raise ValueError(f"El archivo no es una actividad válida: {ruta_fit}")

    contenido_md, _ = procesar_fit(ruta_fit, titulo_personalizado=titulo, notas_personalizadas=notas)
    return contenido_md


# # --- EJECUCIÓN ---
# # Elige el modo que prefieras: 'individual' o 'unico'
# procesar_directorio(
#     carpeta_fit="C:\\Users\\rmagroc\\Downloads\\Entrenamientos\\",
#     modo="individual",  # <--- Cambia a 'unico' si prefieres todo en un solo archivo
#     carpeta_salida="C:\\Users\\rmagroc\\Downloads\\Entrenamientos\\",
#     archivo_unico="C:\\Users\\rmagroc\\Downloads\\Entrenamientos\\Todo.md",
#     max_archivos=1000,  # 0, None o Vacío para procesar todos
#     fecha_min="2024-01-01",  # Formato "YYYY-MM-DD" o "YYYY-MM-DD HH:MM" (o tipo datetime)
#     fecha_max=None,  # Formato "YYYY-MM-DD" o "YYYY-MM-DD HH:MM" (o tipo datetime)
# )