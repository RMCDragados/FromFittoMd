"""Procesamiento de entrenamientos de FUERZA (strength_training) FIT -> Markdown.

Los archivos FIT de fuerza no usan la estructura de laps/records/velocidad de las
actividades de resistencia. En su lugar registran mensajes `set`, uno por cada
serie ejecutada (o descanso), con:

    - set_type: "active" (serie de trabajo) o "rest" (descanso)
    - repetitions: nº de repeticiones
    - weight: peso en kg
    - duration: duración de la serie/descanso en segundos
    - category: tupla de códigos de categoría de ejercicio (FIT exercise_category)
    - category_subtype: subtipo/ejercicio concreto (a menudo None)

Este módulo genera un informe Markdown adaptado a esos datos.
"""

from datetime import timedelta


# --- Mapa de categorías de ejercicio (FIT SDK: exercise_category enum) ---
# Solo los grupos habituales. 65534 es el centinela "unknown/custom" de Garmin.
EXERCISE_CATEGORY = {
    0: "Press de banca",
    1: "Curl de bíceps",
    2: "Cardio",
    3: "Carry (transporte de carga)",
    4: "Crunch",
    5: "Curl",
    6: "Curl",
    7: "Peso muerto",
    8: "Flexión de codo",
    9: "Elevación lateral/frontal",
    10: "Extensión de tríceps",
    11: "Aperturas (fly)",
    12: "Hip raise",
    13: "Hip stability",
    14: "Hip swing",
    15: "Hiperextensión",
    16: "Encogimiento abdominal",
    17: "Salto (jump)",
    18: "Lunge (zancada)",
    19: "Oblicuos (olympic lift)",
    20: "Plancha (plank)",
    21: "Plancha (plank)",
    22: "Pull-up variante",
    23: "Dominadas (pull-up)",
    24: "Flexiones (push-up)",
    25: "Remo (row)",
    26: "Running",
    27: "Press de hombro",
    28: "Encogimiento de hombros (shrug)",
    29: "Sit-up",
    30: "Sentadilla (squat)",
    31: "Estiramiento total",
    32: "Levantamiento total",
    33: "Warm up",
    65534: None,  # centinela custom: se ignora al nombrar
}


def _nombre_ejercicio(category):
    """Traduce la tupla de category a un nombre legible.

    Toma el primer código que no sea el centinela 65534 ni None.
    """
    if category is None:
        return "Ejercicio"
    if not isinstance(category, (list, tuple)):
        category = [category]
    for code in category:
        if code is None or code == 65534:
            continue
        nombre = EXERCISE_CATEGORY.get(code)
        if nombre:
            return nombre
        return f"Ejercicio (cat. {code})"
    return "Ejercicio"


def _seg_a_tiempo(segundos):
    if segundos is not None and segundos > 0:
        return str(timedelta(seconds=int(segundos)))
    return "N/A"


def _mmss(segundos):
    """Formatea segundos como m:ss."""
    if segundos is None or segundos <= 0:
        return "0:00"
    segundos = int(segundos)
    return f"{segundos // 60}:{segundos % 60:02d}"


def es_entrenamiento_fuerza(datos_sesion):
    """Devuelve True si la sesión es un entrenamiento de fuerza."""
    sub = str(datos_sesion.get("sub_sport", "")).lower()
    sport = str(datos_sesion.get("sport", "")).lower()
    return sub == "strength_training" or "strength" in sub or (sport == "training" and sub == "strength_training")


def procesar_fuerza(
    fitfile,
    datos_sesion,
    nombre_workout=None,
    titulo_personalizado=None,
    notas_personalizadas=None,
    garmin_metadata=None,
):
    """Genera el informe Markdown de un entrenamiento de fuerza.

    Args:
        fitfile: objeto fitparse.FitFile ya abierto.
        datos_sesion: dict con los datos del mensaje 'session'.
        nombre_workout: nombre del workout programado (wkt_name) si existe.
        titulo_personalizado: título manual (máxima prioridad).
        notas_personalizadas: notas manuales (máxima prioridad).
        garmin_metadata: dict de Garmin Connect (activityName, description).

    Returns:
        (markdown_str, fecha_inicio)
    """
    fecha_inicio = datos_sesion.get("start_time", "Desconocida")

    # --- Leer los sets ---
    sets_activos = []
    sets_descanso = []
    for msg in fitfile.get_messages("set"):
        s = {}
        for data in msg:
            if data.value is not None:
                s[data.name] = data.value
        tipo = str(s.get("set_type", "")).lower()
        if tipo == "active":
            # Descartar sets fantasma: sin repeticiones y duración despreciable
            reps = s.get("repetitions") or 0
            dur = s.get("duration") or 0
            if reps == 0 and dur < 3:
                continue
            sets_activos.append(s)
        elif tipo == "rest":
            sets_descanso.append(s)

    # --- Datos generales de la sesión ---
    calorias = datos_sesion.get("total_calories", "N/A")
    fc_media = datos_sesion.get("avg_heart_rate", "N/A")
    fc_maxima = datos_sesion.get("max_heart_rate", "N/A")
    tiempo_total = _seg_a_tiempo(datos_sesion.get("total_timer_time"))
    tiempo_transcurrido = _seg_a_tiempo(datos_sesion.get("total_elapsed_time"))
    te_aerobico = datos_sesion.get("total_training_effect", "N/A")
    te_anaerobico = datos_sesion.get("total_anaerobic_training_effect", "N/A")

    # --- Métricas derivadas de los sets ---
    total_series = len(sets_activos)
    total_reps = sum(s.get("repetitions", 0) or 0 for s in sets_activos)
    total_descansos = len(sets_descanso)
    tiempo_trabajo = sum(s.get("duration", 0) or 0 for s in sets_activos)
    tiempo_descanso = sum(s.get("duration", 0) or 0 for s in sets_descanso)

    # Volumen total (kg levantados = suma de peso * reps de cada serie)
    volumen_total = 0.0
    pesos_usados = []
    for s in sets_activos:
        peso = s.get("weight")
        reps = s.get("repetitions") or 0
        if peso is not None and peso > 0:
            volumen_total += peso * reps
            pesos_usados.append(peso)

    peso_max = max(pesos_usados) if pesos_usados else None

    # --- Agrupar por ejercicio ---
    ejercicios = {}  # nombre -> list de sets
    orden_ejercicios = []
    for s in sets_activos:
        nombre = _nombre_ejercicio(s.get("category"))
        if nombre not in ejercicios:
            ejercicios[nombre] = []
            orden_ejercicios.append(nombre)
        ejercicios[nombre].append(s)

    # --- Construir Markdown ---
    md = []

    # Título: manual > Garmin Connect > nombre workout/sport > fecha
    garmin_nombre = None
    if garmin_metadata and isinstance(garmin_metadata, dict):
        garmin_nombre = garmin_metadata.get("activityName")

    nombre_sport = datos_sesion.get("_sport_name")  # se inyecta desde fitTOmd si existe

    if titulo_personalizado and titulo_personalizado.strip():
        md.append(f"# 🏋️ {titulo_personalizado.strip()} — {fecha_inicio}")
    elif garmin_nombre and garmin_nombre.strip():
        md.append(f"# 🏋️ {garmin_nombre.strip()} — {fecha_inicio}")
    elif nombre_workout:
        md.append(f"# 🏋️ {nombre_workout} — {fecha_inicio}")
    elif nombre_sport:
        md.append(f"# 🏋️ {nombre_sport} — {fecha_inicio}")
    else:
        md.append(f"# 🏋️ Entrenamiento de Fuerza — {fecha_inicio}")

    # Notas: manual > Garmin description > notas del FIT
    garmin_descripcion = None
    if garmin_metadata and isinstance(garmin_metadata, dict):
        garmin_descripcion = garmin_metadata.get("description")

    notas_fit = datos_sesion.get("notes")
    if not notas_fit:
        for record in fitfile.get_messages("activity"):
            for data in record:
                if data.name == "notes" and data.value:
                    notas_fit = data.value
                    break
            if notas_fit:
                break

    notas_finales = None
    if notas_personalizadas and notas_personalizadas.strip():
        notas_finales = notas_personalizadas.strip()
    elif garmin_descripcion and garmin_descripcion.strip():
        notas_finales = garmin_descripcion.strip()
    elif notas_fit:
        notas_finales = notas_fit

    if notas_finales:
        md.append("")
        md.append(f"> 📝 {notas_finales}")
    md.append("")

    # --- RESUMEN GENERAL ---
    md.append("## 📊 Resumen General")
    md.append("| Métrica | Valor |")
    md.append("| :--- | :--- |")
    md.append(f"| **Ejercicios distintos** | `{len(orden_ejercicios)}` |")
    md.append(f"| **Series de trabajo** | `{total_series}` |")
    md.append(f"| **Repeticiones totales** | `{total_reps}` |")
    if volumen_total > 0:
        md.append(f"| **Volumen total levantado** | `{volumen_total:,.0f} kg` |")
    if peso_max is not None:
        md.append(f"| **Peso máximo** | `{peso_max:g} kg` |")
    md.append(f"| **Calorías** | `{calorias} kcal` |")
    md.append(f"| **Tiempo total (movimiento)** | `{tiempo_total}` |")
    md.append(f"| **Tiempo transcurrido** | `{tiempo_transcurrido}` |")
    if tiempo_trabajo > 0:
        md.append(f"| **Tiempo bajo tensión (trabajo)** | `{_seg_a_tiempo(tiempo_trabajo)}` |")
    if tiempo_descanso > 0:
        md.append(f"| **Tiempo de descanso** | `{_seg_a_tiempo(tiempo_descanso)}` |")
    md.append("")

    # --- FRECUENCIA CARDÍACA / EFECTO ENTRENAMIENTO ---
    md.append("### 🫀 Frecuencia Cardíaca y Esfuerzo")
    md.append("| Métrica | Valor |")
    md.append("| :--- | :--- |")
    md.append(f"| **FC Media** | `{fc_media} ppm` |")
    md.append(f"| **FC Máxima** | `{fc_maxima} ppm` |")
    md.append(f"| **Training Effect (Aeróbico / Anaeróbico)** | `{te_aerobico} / {te_anaerobico}` |")
    md.append("")

    # --- RESUMEN POR EJERCICIO ---
    if orden_ejercicios:
        md.append("## 💪 Resumen por Ejercicio")
        md.append("| Ejercicio | Series | Reps totales | Peso (min-máx) | Volumen |")
        md.append("| :--- | :---: | :---: | :---: | :---: |")
        for nombre in orden_ejercicios:
            series = ejercicios[nombre]
            n_series = len(series)
            reps = sum(s.get("repetitions", 0) or 0 for s in series)
            pesos = [s.get("weight") for s in series if s.get("weight")]
            if pesos:
                p_min, p_max = min(pesos), max(pesos)
                peso_str = f"{p_min:g} kg" if p_min == p_max else f"{p_min:g}–{p_max:g} kg"
                vol = sum((s.get("weight") or 0) * (s.get("repetitions") or 0) for s in series)
                vol_str = f"{vol:,.0f} kg"
            else:
                peso_str = "—"
                vol_str = "—"
            md.append(f"| **{nombre}** | {n_series} | {reps} | {peso_str} | {vol_str} |")
        md.append("")

    # --- DETALLE POR SERIE ---
    if sets_activos:
        md.append("## 📋 Detalle de Series")
        md.append("| # | Ejercicio | Reps | Peso | Duración | Descanso |")
        md.append("| :---: | :--- | :---: | :---: | :---: | :---: |")

        # Emparejar cada set activo con el descanso que le sigue (por message_index)
        # Recorremos todos los sets en orden para calcular el descanso posterior.
        todos = []
        for msg in fitfile.get_messages("set"):
            s = {}
            for data in msg:
                if data.value is not None:
                    s[data.name] = data.value
            todos.append(s)
        todos.sort(key=lambda x: x.get("message_index", 0))

        num = 0
        for i, s in enumerate(todos):
            if str(s.get("set_type", "")).lower() != "active":
                continue
            # Descartar sets fantasma (coherente con el filtro de arriba)
            if (s.get("repetitions") or 0) == 0 and (s.get("duration") or 0) < 3:
                continue
            num += 1
            nombre = _nombre_ejercicio(s.get("category"))
            reps = s.get("repetitions", "—")
            peso = s.get("weight")
            peso_str = f"{peso:g} kg" if peso else "—"
            dur = _mmss(s.get("duration"))
            # Descanso posterior: siguiente set de tipo rest
            descanso_str = "—"
            for j in range(i + 1, len(todos)):
                if str(todos[j].get("set_type", "")).lower() == "rest":
                    descanso_str = _mmss(todos[j].get("duration"))
                    break
                if str(todos[j].get("set_type", "")).lower() == "active":
                    break
            md.append(f"| {num} | {nombre} | {reps} | {peso_str} | {dur} | {descanso_str} |")
        md.append("")

    # --- GRÁFICO DE VOLUMEN POR EJERCICIO ---
    if orden_ejercicios:
        vols = []
        for nombre in orden_ejercicios:
            vol = sum((s.get("weight") or 0) * (s.get("repetitions") or 0) for s in ejercicios[nombre])
            vols.append((nombre, vol))
        max_vol = max((v for _, v in vols), default=0)
        if max_vol > 0:
            md.append("### 📈 Volumen por Ejercicio")
            md.append("```")
            for nombre, vol in vols:
                bar_len = int((vol / max_vol) * 30) if max_vol > 0 else 0
                bar = "█" * bar_len
                md.append(f"  {nombre[:22]:<22} | {bar} {vol:,.0f} kg")
            md.append("```")
            md.append("")

    md.append("\n---\n")
    return "\n".join(md), fecha_inicio
