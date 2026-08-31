"""Generador de informes de salud diaria en Markdown a partir de datos de Garmin Connect.

Recibe el diccionario generado por garmin_client.obtener_datos_salud() y produce
un informe Markdown estructurado con todas las métricas disponibles.
"""

from datetime import timedelta


# Caracteres sparkline
SPARK_CHARS = "▁▂▃▄▅▆▇█"


def _sparkline(valores, ancho=60):
    """Genera sparkline Unicode desde una lista de valores numéricos."""
    if not valores or len(valores) < 2:
        return ""
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


def _seg_a_tiempo(segundos):
    """Convierte segundos a formato legible (Xh Ym)."""
    if not segundos or segundos <= 0:
        return "N/A"
    h = int(segundos // 3600)
    m = int((segundos % 3600) // 60)
    if h > 0:
        return f"{h}h {m}min"
    return f"{m}min"


def _valor_o_na(dato, clave, sufijo="", multiplicador=1):
    """Extrae un valor de un dict o devuelve N/A."""
    if dato is None:
        return "N/A"
    val = dato.get(clave)
    if val is None:
        return "N/A"
    if isinstance(val, (int, float)):
        val = val * multiplicador
        if isinstance(val, float):
            val = round(val, 1)
    return f"{val}{sufijo}"


def generar_salud_md(datos: dict) -> str:
    """Genera un informe Markdown de salud diaria.

    Args:
        datos: Diccionario devuelto por garmin_client.obtener_datos_salud().

    Retorna:
        String con el informe completo en Markdown.
    """
    fecha = datos.get("fecha", "Desconocida")
    md = []

    md.append(f"# 🏥 Informe de Salud: {fecha}")
    md.append("")

    # =====================================================================
    # RESUMEN GENERAL (stats)
    # =====================================================================
    stats = datos.get("stats")
    if stats:
        md.append("## 📊 Resumen del Día")
        md.append("| Métrica | Valor |")
        md.append("| :--- | :--- |")

        pasos = stats.get("totalSteps", 0)
        md.append(f"| **Pasos** | `{pasos:,}` |")

        dist_m = stats.get("totalDistanceMeters", 0)
        if dist_m:
            md.append(f"| **Distancia** | `{dist_m / 1000:.2f} km` |")

        cal_total = stats.get("totalKilocalories", 0)
        cal_activas = stats.get("activeKilocalories", 0)
        cal_bmr = stats.get("bmrKilocalories", 0)
        md.append(f"| **Calorías totales** | `{cal_total:.0f} kcal` |")
        md.append(f"| **Calorías activas** | `{cal_activas:.0f} kcal` |")
        md.append(f"| **Calorías en reposo (BMR)** | `{cal_bmr:.0f} kcal` |")

        vigorosos = stats.get("vigorousIntensityMinutes", 0) or 0
        moderados = stats.get("moderateIntensityMinutes", 0) or 0
        md.append(f"| **Minutos intensidad moderada** | `{moderados} min` |")
        md.append(f"| **Minutos intensidad vigorosa** | `{vigorosos} min` |")

        md.append("")

    # =====================================================================
    # FRECUENCIA CARDÍACA
    # =====================================================================
    hr = datos.get("heart_rates")
    if hr:
        md.append("## ❤️ Frecuencia Cardíaca")
        md.append("| Métrica | Valor |")
        md.append("| :--- | :--- |")
        md.append(f"| **FC en reposo** | `{_valor_o_na(hr, 'restingHeartRate', ' ppm')}` |")
        md.append(f"| **FC máxima del día** | `{_valor_o_na(hr, 'maxHeartRate', ' ppm')}` |")
        md.append(f"| **FC mínima del día** | `{_valor_o_na(hr, 'minHeartRate', ' ppm')}` |")
        md.append("")

        # Sparkline de HR si hay datos de time series
        hr_values = hr.get("heartRateValues") or hr.get("heartRateValueDescriptors")
        if not hr_values:
            # Intentar extraer de la estructura alternativa
            hr_ts = []
            for entry in (hr.get("allDayHRValues") or []):
                if isinstance(entry, (list, tuple)) and len(entry) >= 2 and entry[1]:
                    hr_ts.append(entry[1])
            if hr_ts:
                spark = _sparkline(hr_ts)
                if spark:
                    md.append(f"**Evolución FC diaria** (min {min(hr_ts)} — max {max(hr_ts)} ppm)")
                    md.append(f"`{spark}`")
                    md.append("")

    # =====================================================================
    # SUEÑO
    # =====================================================================
    sleep_raw = datos.get("sleep")
    if sleep_raw:
        # La API puede devolver los datos directamente o dentro de "dailySleepDTO"
        if isinstance(sleep_raw, dict):
            sleep = sleep_raw.get("dailySleepDTO") or sleep_raw
        else:
            sleep = sleep_raw

        if isinstance(sleep, dict):
            md.append("## 😴 Sueño")
            md.append("| Métrica | Valor |")
            md.append("| :--- | :--- |")

            # Buscar duración total en varias claves posibles
            total_sleep = (
                sleep.get("sleepTimeSeconds")
                or sleep.get("deepSleepSeconds", 0) + sleep.get("lightSleepSeconds", 0)
                   + sleep.get("remSleepSeconds", 0) + sleep.get("awakeSleepSeconds", 0)
                if sleep.get("deepSleepSeconds") else None
            )
            # Alternativa: duración desde timestamps
            if not total_sleep:
                dur = sleep.get("sleepDurationInSeconds") or sleep.get("durationInSeconds")
                if dur:
                    total_sleep = dur

            md.append(f"| **Duración total** | `{_seg_a_tiempo(total_sleep)}` |")

            deep = sleep.get("deepSleepSeconds") or sleep.get("deepSleepDurationInSeconds")
            light = sleep.get("lightSleepSeconds") or sleep.get("lightSleepDurationInSeconds")
            rem = sleep.get("remSleepSeconds") or sleep.get("remSleepInSeconds")
            awake = sleep.get("awakeSleepSeconds") or sleep.get("awakeDurationInSeconds")

            md.append(f"| **Sueño profundo** | `{_seg_a_tiempo(deep)}` |")
            md.append(f"| **Sueño ligero** | `{_seg_a_tiempo(light)}` |")
            md.append(f"| **Sueño REM** | `{_seg_a_tiempo(rem)}` |")
            md.append(f"| **Tiempo despierto** | `{_seg_a_tiempo(awake)}` |")

            # Puntuación del sueño — buscar en varias rutas
            scores = sleep.get("sleepScores") or sleep_raw.get("sleepScores")
            score_val = None
            if scores:
                overall = scores.get("overall", {})
                if isinstance(overall, dict):
                    score_val = overall.get("value") or overall.get("qualifierKey")
                elif isinstance(overall, (int, float)):
                    score_val = overall
            # Alternativa directa
            if score_val is None:
                score_val = sleep.get("sleepScore") or sleep.get("overallScore")
            if score_val is not None:
                md.append(f"| **Puntuación del sueño** | `{score_val}/100` |")

            # Conteo despertares
            restless = sleep.get("restlessMoments") or sleep.get("restlessMomentsCount")
            awake_count = sleep.get("awakeCount") or sleep.get("awakingsCount")
            if restless is not None:
                md.append(f"| **Momentos inquietos** | `{restless}` |")
            if awake_count is not None:
                md.append(f"| **Despertares** | `{awake_count}` |")

            # FC, HRV y respiración durante el sueño
            avg_hr = sleep.get("avgSleepHeartRate") or sleep.get("averageHeartRate")
            avg_hrv = sleep.get("avgSleepHRV") or sleep.get("averageHRV")
            avg_resp = sleep.get("avgSleepRespiration") or sleep.get("averageRespirationValue")
            avg_spo2 = sleep.get("averageSpO2Value") or sleep.get("avgSleepSpO2")
            avg_stress = sleep.get("avgSleepStress") or sleep.get("averageSleepStress")

            if avg_hr is not None:
                md.append(f"| **FC media durante sueño** | `{avg_hr} ppm` |")
            if avg_hrv is not None:
                md.append(f"| **HRV media durante sueño** | `{avg_hrv} ms` |")
            if avg_resp is not None:
                md.append(f"| **Respiración media sueño** | `{avg_resp} rpm` |")
            if avg_spo2 is not None:
                md.append(f"| **SpO2 media sueño** | `{avg_spo2}%` |")
            if avg_stress is not None:
                md.append(f"| **Estrés medio sueño** | `{avg_stress}` |")

            md.append("")

            # Gráfico de fases del sueño
            fases_total = (deep or 0) + (light or 0) + (rem or 0) + (awake or 0)
            if fases_total > 0:
                fases = []
                if deep:
                    fases.append(("Profundo", deep))
                if light:
                    fases.append(("Ligero", light))
                if rem:
                    fases.append(("REM", rem))
                if awake:
                    fases.append(("Despierto", awake))

                if fases:
                    md.append("**Distribución del sueño**")
                    md.append("```")
                    for nombre, segs in fases:
                        pct = (segs / fases_total) * 100
                        bar_len = int(pct / 2.5)
                        bar = "█" * bar_len
                        md.append(f"  {nombre:>10s} | {bar} {pct:.0f}% ({_seg_a_tiempo(segs)})")
                    md.append("```")
                    md.append("")

    # =====================================================================
    # ESTRÉS
    # =====================================================================
    stress = datos.get("stress")
    if stress:
        md.append("## 😤 Estrés")
        md.append("| Métrica | Valor |")
        md.append("| :--- | :--- |")
        md.append(f"| **Estrés medio** | `{_valor_o_na(stress, 'avgStressLevel')}` |")
        md.append(f"| **Estrés máximo** | `{_valor_o_na(stress, 'maxStressLevel')}` |")

        low = stress.get("lowStressDuration", 0) or 0
        med = stress.get("mediumStressDuration", 0) or 0
        high = stress.get("highStressDuration", 0) or 0
        total_stress = low + med + high

        if total_stress > 0:
            md.append(f"| **Tiempo estrés bajo** | `{_seg_a_tiempo(low)} ({low / total_stress * 100:.0f}%)` |")
            md.append(f"| **Tiempo estrés medio** | `{_seg_a_tiempo(med)} ({med / total_stress * 100:.0f}%)` |")
            md.append(f"| **Tiempo estrés alto** | `{_seg_a_tiempo(high)} ({high / total_stress * 100:.0f}%)` |")

        md.append("")

        # Sparkline de estrés si hay series temporales
        stress_values = stress.get("stressValuesArray") or stress.get("bodyStressValueList") or []
        if stress_values:
            vals = []
            for entry in stress_values:
                if isinstance(entry, (list, tuple)) and len(entry) >= 2:
                    v = entry[1]
                    if v is not None and v >= 0:
                        vals.append(v)
                elif isinstance(entry, dict):
                    v = entry.get("stressLevel") or entry.get("value")
                    if v is not None and v >= 0:
                        vals.append(v)
            if vals:
                spark = _sparkline(vals)
                if spark:
                    md.append(f"**Evolución del estrés** (min {min(vals)} — max {max(vals)})")
                    md.append(f"`{spark}`")
                    md.append("")

    # =====================================================================
    # BODY BATTERY
    # =====================================================================
    bb = datos.get("body_battery")
    if bb and isinstance(bb, list) and len(bb) > 0:
        md.append("## 🔋 Body Battery")

        # Extraer valores de la serie temporal
        bb_values = []
        for entry in bb:
            if isinstance(entry, dict):
                val = entry.get("value") or entry.get("charged")
                if val is not None:
                    bb_values.append(val)
            elif isinstance(entry, (list, tuple)) and len(entry) >= 2:
                if entry[1] is not None:
                    bb_values.append(entry[1])

        if bb_values:
            md.append("| Métrica | Valor |")
            md.append("| :--- | :--- |")
            md.append(f"| **Máximo del día** | `{max(bb_values)}` |")
            md.append(f"| **Mínimo del día** | `{min(bb_values)}` |")
            md.append(f"| **Último valor** | `{bb_values[-1]}` |")
            md.append("")

            spark = _sparkline(bb_values)
            if spark:
                md.append(f"**Evolución Body Battery** (min {min(bb_values)} — max {max(bb_values)})")
                md.append(f"`{spark}`")
                md.append("")

        # Cargado/drenado
        charged_total = sum(e.get("charged", 0) or 0 for e in bb if isinstance(e, dict))
        drained_total = sum(e.get("drained", 0) or 0 for e in bb if isinstance(e, dict))
        if charged_total or drained_total:
            md.append(f"- **Energía cargada:** {charged_total}")
            md.append(f"- **Energía drenada:** {drained_total}")
            md.append("")

    # =====================================================================
    # HRV (Variabilidad de Frecuencia Cardíaca)
    # =====================================================================
    hrv = datos.get("hrv")
    if hrv:
        summary = hrv.get("hrvSummary") or hrv
        if summary:
            md.append("## 💓 HRV (Variabilidad Cardíaca)")
            md.append("| Métrica | Valor |")
            md.append("| :--- | :--- |")
            md.append(f"| **HRV media nocturna** | `{_valor_o_na(summary, 'lastNightAvg', ' ms')}` |")
            md.append(f"| **HRV máxima (5 min)** | `{_valor_o_na(summary, 'lastNight5MinHigh', ' ms')}` |")
            md.append(f"| **HRV mínima (5 min)** | `{_valor_o_na(summary, 'lastNight5MinLow', ' ms')}` |")
            md.append(f"| **Media semanal** | `{_valor_o_na(summary, 'weeklyAvg', ' ms')}` |")

            baseline_low = summary.get("baselineBalancedLow")
            baseline_high = summary.get("baselineBalancedHigh")
            if baseline_low is not None and baseline_high is not None:
                md.append(f"| **Rango baseline** | `{baseline_low} — {baseline_high} ms` |")

            status = summary.get("status")
            if status:
                status_emoji = {
                    "BALANCED": "✅ Equilibrado",
                    "UNBALANCED": "⚠️ Desequilibrado",
                    "POOR": "🔴 Pobre",
                    "LOW": "🟡 Bajo",
                }.get(status, status)
                md.append(f"| **Estado** | `{status_emoji}` |")

            md.append("")

    # =====================================================================
    # SpO2 (Saturación de oxígeno)
    # =====================================================================
    spo2 = datos.get("spo2")
    if spo2:
        md.append("## 🫁 SpO2 (Saturación de Oxígeno)")
        md.append("| Métrica | Valor |")
        md.append("| :--- | :--- |")

        avg_spo2 = spo2.get("averageSpO2") or spo2.get("avgValue")
        low_spo2 = spo2.get("lowestSpO2") or spo2.get("minValue")
        latest = spo2.get("latestSpO2") or spo2.get("latestValue")

        if avg_spo2 is not None:
            md.append(f"| **SpO2 media** | `{avg_spo2}%` |")
        if low_spo2 is not None:
            md.append(f"| **SpO2 mínima** | `{low_spo2}%` |")
        if latest is not None:
            md.append(f"| **Última medición** | `{latest}%` |")

        md.append("")

    # =====================================================================
    # RESPIRACIÓN
    # =====================================================================
    resp = datos.get("respiration")
    if resp:
        md.append("## 🌬️ Respiración")
        md.append("| Métrica | Valor |")
        md.append("| :--- | :--- |")

        avg_resp = resp.get("avgWakingRespirationValue") or resp.get("avgRespirationValue")
        low_resp = resp.get("lowestRespirationValue") or resp.get("minRespirationValue")
        high_resp = resp.get("highestRespirationValue") or resp.get("maxRespirationValue")

        if avg_resp is not None:
            md.append(f"| **Respiración media (despierto)** | `{avg_resp:.1f} rpm` |")
        if low_resp is not None:
            md.append(f"| **Respiración mínima** | `{low_resp:.1f} rpm` |")
        if high_resp is not None:
            md.append(f"| **Respiración máxima** | `{high_resp:.1f} rpm` |")

        md.append("")

    # =====================================================================
    # MINUTOS DE INTENSIDAD
    # =====================================================================
    intensity = datos.get("intensity_minutes")
    if intensity:
        md.append("## ⚡ Minutos de Intensidad")
        md.append("| Métrica | Valor |")
        md.append("| :--- | :--- |")

        moderate = intensity.get("moderateMinutes") or intensity.get("moderateIntensityMinutes")
        vigorous = intensity.get("vigorousMinutes") or intensity.get("vigorousIntensityMinutes")
        weekly_mod = intensity.get("weeklyModerate")
        weekly_vig = intensity.get("weeklyVigorous")
        weekly_total = intensity.get("weeklyTotal")
        goal = intensity.get("weekGoal") or intensity.get("weeklyGoal") or intensity.get("intensityMinutesGoal")

        if moderate is not None:
            md.append(f"| **Minutos moderados (hoy)** | `{moderate} min` |")
        if vigorous is not None:
            md.append(f"| **Minutos vigorosos (hoy)** | `{vigorous} min` |")
        if weekly_mod is not None:
            md.append(f"| **Moderados (semana)** | `{weekly_mod} min` |")
        if weekly_vig is not None:
            md.append(f"| **Vigorosos (semana)** | `{weekly_vig} min` |")
        if weekly_total is not None and goal:
            md.append(f"| **Progreso semanal** | `{weekly_total}/{goal} min` |")
        elif goal and (moderate or vigorous):
            total_int = (moderate or 0) + (vigorous or 0) * 2
            md.append(f"| **Progreso semanal** | `{total_int}/{goal} min` |")

        md.append("")

    # =====================================================================
    # TRAINING READINESS
    # =====================================================================
    readiness = datos.get("training_readiness")
    if readiness:
        # Puede ser lista o dict
        if isinstance(readiness, list) and readiness:
            readiness = readiness[0]

        if isinstance(readiness, dict):
            score = readiness.get("score") or readiness.get("readinessScore")
            level = readiness.get("level") or readiness.get("readinessLevel")
            if score is not None or level is not None:
                md.append("## 🎯 Training Readiness")
                md.append("| Métrica | Valor |")
                md.append("| :--- | :--- |")
                if score is not None:
                    md.append(f"| **Puntuación** | `{score}/100` |")
                if level is not None:
                    level_emoji = {
                        "PRIME": "🟢 Óptimo",
                        "GOOD": "🟢 Bueno",
                        "MODERATE": "🟡 Moderado",
                        "LOW": "🟠 Bajo",
                        "POOR": "🔴 Pobre",
                    }.get(str(level).upper(), str(level))
                    md.append(f"| **Nivel** | `{level_emoji}` |")

                # Factores individuales
                for factor_key in ["sleepScore", "recoveryScore", "activityHistoryScore",
                                   "hrvScore", "sleepHistoryScore", "stressHistoryScore"]:
                    val = readiness.get(factor_key)
                    if val is not None:
                        label = factor_key.replace("Score", "").replace("History", " historial")
                        label = label[0].upper() + label[1:]
                        md.append(f"| **{label}** | `{val}` |")

                md.append("")

    # =====================================================================
    # TRAINING STATUS
    # =====================================================================
    tstatus = datos.get("training_status")
    if tstatus and isinstance(tstatus, dict):
        # Buscar en raíz y en posibles sub-dicts
        def _buscar(d, *claves):
            """Busca un valor en un dict y en sus sub-dicts de primer nivel."""
            for k in claves:
                val = d.get(k)
                if val is not None and not isinstance(val, dict):
                    return val
            # Buscar en sub-dicts conocidos
            for sub_key in ["latestTrainingStatus", "currentDayData", "mostRecentVO2MaxDTO"]:
                sub = d.get(sub_key)
                if isinstance(sub, dict):
                    for k in claves:
                        val = sub.get(k)
                        if val is not None and not isinstance(val, dict):
                            return val
            return None

        status_phrase = _buscar(tstatus, "trainingStatusPhrase", "currentDayTrainingStatus",
                                "trainingStatus", "statusPhrase")
        vo2 = _buscar(tstatus, "vo2MaxValue", "mostRecentVO2Max", "vo2MaxPreciseValue",
                       "generic", "runVo2Max")
        load_total = _buscar(tstatus, "trainingLoadWeeklyTotal", "currentLoadTotal",
                              "weeklyTrainingLoad", "totalLoad")
        load_low = _buscar(tstatus, "lowAerobicTrainingLoadWeekly", "lowAerobicLoad")
        load_high = _buscar(tstatus, "highAerobicTrainingLoadWeekly", "highAerobicLoad")
        load_anaerobic = _buscar(tstatus, "anaerobicTrainingLoadWeekly", "anaerobicLoad")

        has_data = any([status_phrase, vo2, load_total])
        if has_data:
            md.append("## 📈 Training Status")
            md.append("| Métrica | Valor |")
            md.append("| :--- | :--- |")
            if status_phrase:
                md.append(f"| **Estado** | `{status_phrase}` |")
            if vo2:
                md.append(f"| **VO2 Max** | `{vo2} ml/kg/min` |")
            if load_total:
                md.append(f"| **Carga semanal total** | `{load_total}` |")
            if load_low is not None:
                md.append(f"| **Carga aeróbica baja** | `{load_low}` |")
            if load_high is not None:
                md.append(f"| **Carga aeróbica alta** | `{load_high}` |")
            if load_anaerobic is not None:
                md.append(f"| **Carga anaeróbica** | `{load_anaerobic}` |")
            md.append("")

    # =====================================================================
    # COMPOSICIÓN CORPORAL
    # =====================================================================
    body = datos.get("body_composition")
    if body and isinstance(body, dict):
        weight = body.get("weight")
        bmi = body.get("bmi")
        fat = body.get("bodyFat")
        muscle = body.get("muscleMass")
        water = body.get("bodyWater")

        if any([weight, bmi, fat]):
            md.append("## ⚖️ Composición Corporal")
            md.append("| Métrica | Valor |")
            md.append("| :--- | :--- |")
            if weight:
                # Peso viene en gramos
                peso_kg = weight / 1000 if weight > 500 else weight
                md.append(f"| **Peso** | `{peso_kg:.1f} kg` |")
            if bmi:
                md.append(f"| **IMC** | `{bmi:.1f}` |")
            if fat:
                md.append(f"| **Grasa corporal** | `{fat:.1f}%` |")
            if muscle:
                muscle_kg = muscle / 1000 if muscle > 500 else muscle
                md.append(f"| **Masa muscular** | `{muscle_kg:.1f} kg` |")
            if water:
                md.append(f"| **Agua corporal** | `{water:.1f}%` |")
            md.append("")

    md.append("\n---\n")
    return "\n".join(md)
