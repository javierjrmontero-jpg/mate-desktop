#!/usr/bin/env python3
"""
MATE Briefing Tools — PRO
Briefing matutino unificado: hora, clima, noticias, agenda del día y recordatorios.
Comando: "dame el briefing" / "briefing del día" / "resumen de la mañana".
"""

import logging
from datetime import datetime

logger = logging.getLogger(__name__)

_DIAS  = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
_MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio",
          "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def get_morning_briefing() -> str:
    """
    Ensambla el briefing completo del día:
    1. Saludo con hora y fecha
    2. Clima
    3. Agenda del día (Google Calendar o local)
    4. Recordatorios pendientes
    5. Titular de noticias
    """
    parts = []
    now = datetime.now()
    hora = f"{now.hour}:{now.minute:02d}"
    dia  = _DIAS[now.weekday()]
    mes  = _MESES[now.month - 1]

    # 1. Saludo contextual
    if now.hour < 12:
        saludo = "Buenos días"
    elif now.hour < 19:
        saludo = "Buenas tardes"
    else:
        saludo = "Buenas noches"

    parts.append(f"{saludo}. Son las {hora} del {dia} {now.day} de {mes}.")

    # 2. Clima
    try:
        from tools.web_tools import get_weather
        clima = get_weather()
        if clima and "error" not in clima.lower():
            parts.append(clima)
    except Exception as e:
        logger.debug(f"Briefing clima error: {e}")

    # 3. Agenda del día
    try:
        from tools.calendar_tools import get_today_events
        agenda = get_today_events()
        # Solo incluir si hay eventos reales
        if agenda and "no tenés eventos" not in agenda.lower():
            parts.append(agenda)
        else:
            parts.append("Hoy no tenés eventos agendados.")
    except Exception as e:
        logger.debug(f"Briefing agenda error: {e}")

    # 4. Recordatorios pendientes
    try:
        from tools.reminder_tools import list_reminders
        reminders = list_reminders()
        if reminders and "no hay" not in reminders.lower() and "sin recordatorios" not in reminders.lower():
            parts.append(reminders)
    except Exception as e:
        logger.debug(f"Briefing reminders error: {e}")

    # 5. Titular de noticias (1 noticia, breve)
    try:
        from tools.web_tools import get_news
        noticias = get_news()
        if noticias and "error" not in noticias.lower():
            # Solo primera línea / primer titular
            first = noticias.split(".")[0].strip()
            if first:
                parts.append(f"En noticias: {first}.")
    except Exception as e:
        logger.debug(f"Briefing noticias error: {e}")

    if len(parts) == 1:
        parts.append("Todo tranquilo por ahora.")

    return " ".join(parts)


def get_quick_status() -> str:
    """
    Estado rápido del sistema + clima. Versión corta del briefing.
    Comando: "cómo está todo" / "estado rápido".
    """
    parts = []

    # Sistema
    try:
        from tools.system_control import get_system_summary
        parts.append(get_system_summary())
    except Exception as e:
        logger.debug(f"quick_status sys error: {e}")

    # Clima breve
    try:
        from tools.web_tools import get_weather
        clima = get_weather()
        if clima and "error" not in clima.lower():
            parts.append(clima)
    except Exception as e:
        logger.debug(f"quick_status clima error: {e}")

    return " ".join(parts) if parts else "No pude obtener el estado del sistema."
