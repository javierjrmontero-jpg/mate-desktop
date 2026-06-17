#!/usr/bin/env python3
"""
MATE Reminder Tools — F11-2
Recordatorios con hora. Guardados en JSON; el orbe los anuncia por TTS cuando llega el momento.
Sin dependencias externas.
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

_REMINDERS_FILE = Path(__file__).parent.parent / ".mate_reminders.json"


def _load() -> list[dict]:
    if not _REMINDERS_FILE.exists():
        return []
    try:
        return json.loads(_REMINDERS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save(reminders: list[dict]) -> None:
    _REMINDERS_FILE.write_text(
        json.dumps(reminders, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def set_reminder(message: str, minutes: int = 0, at_time: str = "") -> str:
    """
    Agrega un recordatorio.
      minutes  — en cuántos minutos dispararlo (>0)
      at_time  — hora exacta "HH:MM" (si minutes == 0)
    """
    reminders = _load()
    now = datetime.now()

    if at_time:
        try:
            h, m    = map(int, at_time.split(":"))
            target  = now.replace(hour=h, minute=m, second=0, microsecond=0)
            if target <= now:
                target += timedelta(days=1)   # si ya pasó la hora, poner para mañana
        except Exception:
            return f"No entendí la hora '{at_time}'. Usá formato HH:MM."
    elif minutes > 0:
        target = now + timedelta(minutes=minutes)
    else:
        return "Especificá en cuántos minutos o a qué hora."

    reminder = {
        "id":      len(reminders) + 1,
        "message": message,
        "fire_at": target.isoformat(),
        "created": now.isoformat(),
        "fired":   False,
    }
    reminders.append(reminder)
    _save(reminders)

    if minutes > 0:
        return f"Recordatorio en {minutes} minuto{'s' if minutes > 1 else ''}: '{message}'."
    else:
        return f"Recordatorio a las {target.strftime('%H:%M')}: '{message}'."


def list_reminders() -> str:
    pending = [r for r in _load() if not r.get("fired")]
    if not pending:
        return "No tenés recordatorios pendientes."
    items = []
    for r in pending:
        fire_at = datetime.fromisoformat(r["fire_at"])
        items.append(f"'{r['message']}' a las {fire_at.strftime('%H:%M')}")
    return "Recordatorios pendientes: " + ". ".join(items) + "."


def check_and_fire() -> list[str]:
    """
    Llamado por el QTimer del orbe cada 60s.
    Retorna lista de mensajes a anunciar por TTS y marca los disparados.
    """
    reminders  = _load()
    now        = datetime.now()
    to_announce = []
    changed    = False

    for r in reminders:
        if r.get("fired"):
            continue
        if datetime.fromisoformat(r["fire_at"]) <= now:
            to_announce.append(f"Recordatorio: {r['message']}")
            r["fired"] = True
            changed    = True

    if changed:
        _save(reminders)

    return to_announce
