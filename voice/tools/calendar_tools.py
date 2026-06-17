#!/usr/bin/env python3
"""
MATE Calendar Tools — PRO
Gestión de agenda: Google Calendar + fallback JSON local.

Configuración en .env (opcional para Google Calendar):
  GOOGLE_CREDENTIALS_PATH — ruta al client_secret.json descargado de Google Cloud Console
  MATE_TIMEZONE            — zona horaria (default: America/Argentina/Buenos_Aires)
"""

import os
import sys
import json
import logging
from pathlib import Path
from datetime import datetime, timedelta, date

logger = logging.getLogger(__name__)

_DATA_DIR   = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent.parent
_LOCAL_CAL  = _DATA_DIR / ".mate_calendar.json"
_GCAL_CREDS = os.environ.get("GOOGLE_CREDENTIALS_PATH", "")
_TOKEN_PATH = str(_DATA_DIR / ".gcal_token.json")
_TZ         = os.environ.get("MATE_TIMEZONE", "America/Argentina/Buenos_Aires")

_DIAS  = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
_MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio",
          "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


# ─── Calendario local (siempre disponible) ───────────────────────────────────

def _load_local() -> list:
    if _LOCAL_CAL.exists():
        try:
            return json.loads(_LOCAL_CAL.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []


def _save_local(events: list):
    _LOCAL_CAL.write_text(json.dumps(events, ensure_ascii=False, indent=2), encoding="utf-8")


def _fmt_dt(dt: datetime) -> str:
    dia  = _DIAS[dt.weekday()]
    mes  = _MESES[dt.month - 1]
    return f"{dia} {dt.day} de {mes} a las {dt.hour}:{dt.minute:02d}"


# ─── Google Calendar (si hay credenciales) ────────────────────────────────────

def _get_gcal_service():
    if not _GCAL_CREDS or not os.path.exists(_GCAL_CREDS):
        return None
    try:
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build

        SCOPES = ["https://www.googleapis.com/auth/calendar"]
        creds  = None
        if os.path.exists(_TOKEN_PATH):
            creds = Credentials.from_authorized_user_file(_TOKEN_PATH, SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow  = InstalledAppFlow.from_client_secrets_file(_GCAL_CREDS, SCOPES)
                creds = flow.run_local_server(port=0)
            Path(_TOKEN_PATH).write_text(creds.to_json(), encoding="utf-8")
        return build("calendar", "v3", credentials=creds)
    except Exception as e:
        logger.warning(f"Google Calendar no disponible: {e}")
        return None


# ─── Parseo de fecha/hora desde voz ──────────────────────────────────────────

def _parse_datetime(date_hint: str, time_hint: str) -> datetime:
    """
    Intenta parsear fecha y hora desde strings de voz.
    Fallback: hoy + 1 hora redondeada.
    """
    now = datetime.now()
    event_date = now.date()

    if date_hint:
        d = date_hint.lower().strip()
        if "mañana" in d:
            event_date = (now + timedelta(days=1)).date()
        elif "pasado" in d:
            event_date = (now + timedelta(days=2)).date()
        else:
            for fmt in ("%d/%m/%Y", "%d/%m", "%d-%m-%Y", "%d-%m"):
                try:
                    parsed = datetime.strptime(d, fmt)
                    event_date = parsed.replace(year=now.year).date()
                    break
                except ValueError:
                    continue

    event_time = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    if time_hint:
        for fmt in ("%H:%M", "%H"):
            try:
                t = datetime.strptime(time_hint.replace("h", ":").replace(".", ":"), fmt)
                event_time = event_time.replace(hour=t.hour, minute=t.minute if fmt == "%H:%M" else 0)
                break
            except ValueError:
                continue

    return datetime.combine(event_date, event_time.time())


# ─── API pública ─────────────────────────────────────────────────────────────

def create_event(title: str, date_hint: str = "", time_hint: str = "", duration_min: int = 60) -> str:
    """Crea un evento. Intenta Google Calendar, fallback a local."""
    start_dt = _parse_datetime(date_hint, time_hint)
    end_dt   = start_dt + timedelta(minutes=duration_min)

    svc = _get_gcal_service()
    if svc:
        try:
            event = {
                "summary": title,
                "start":   {"dateTime": start_dt.isoformat(), "timeZone": _TZ},
                "end":     {"dateTime": end_dt.isoformat(),   "timeZone": _TZ},
            }
            svc.events().insert(calendarId="primary", body=event).execute()
            return f"Evento '{title}' creado en Google Calendar para el {_fmt_dt(start_dt)}."
        except Exception as e:
            logger.warning(f"Google Calendar insert error: {e}")

    # Fallback local
    events = _load_local()
    events.append({
        "title":   title,
        "start":   start_dt.isoformat(),
        "end":     end_dt.isoformat(),
        "created": datetime.now().isoformat(),
    })
    _save_local(events)
    return f"Evento '{title}' agendado para el {_fmt_dt(start_dt)}."


def get_today_events() -> str:
    """Retorna los eventos de hoy."""
    today = datetime.now().date()

    svc = _get_gcal_service()
    if svc:
        try:
            t_min = datetime.combine(today, datetime.min.time()).isoformat() + "Z"
            t_max = datetime.combine(today + timedelta(days=1), datetime.min.time()).isoformat() + "Z"
            res   = svc.events().list(
                calendarId="primary", timeMin=t_min, timeMax=t_max,
                singleEvents=True, orderBy="startTime",
            ).execute()
            items = res.get("items", [])
            if not items:
                return "No tenés eventos hoy en Google Calendar."
            parts = []
            for item in items[:5]:
                start = item["start"].get("dateTime", item["start"].get("date", ""))
                try:
                    dt       = datetime.fromisoformat(start.replace("Z", ""))
                    time_str = f"{dt.hour}:{dt.minute:02d}"
                except Exception:
                    time_str = start[:5]
                parts.append(f"{time_str}: {item['summary']}")
            return "Hoy tenés: " + ". ".join(parts) + "."
        except Exception as e:
            logger.warning(f"Google Calendar list error: {e}")

    # Fallback local
    events = _load_local()
    today_events = []
    for ev in events:
        try:
            dt = datetime.fromisoformat(ev["start"])
            if dt.date() == today:
                today_events.append(f"{dt.hour}:{dt.minute:02d}: {ev['title']}")
        except Exception:
            pass
    if not today_events:
        return "No tenés eventos agendados para hoy."
    return "Hoy tenés: " + ". ".join(today_events) + "."


def get_week_events() -> str:
    """Retorna eventos de los próximos 7 días."""
    now = datetime.now()
    end = now + timedelta(days=7)

    svc = _get_gcal_service()
    if svc:
        try:
            t_min = now.isoformat() + "Z"
            t_max = end.isoformat() + "Z"
            res   = svc.events().list(
                calendarId="primary", timeMin=t_min, timeMax=t_max,
                singleEvents=True, orderBy="startTime",
            ).execute()
            items = res.get("items", [])
            if not items:
                return "No tenés eventos en los próximos 7 días."
            parts = []
            for item in items[:6]:
                start = item["start"].get("dateTime", item["start"].get("date", ""))
                try:
                    dt       = datetime.fromisoformat(start.replace("Z", ""))
                    date_str = f"{_DIAS[dt.weekday()]} {dt.day}/{dt.month} {dt.hour}:{dt.minute:02d}"
                except Exception:
                    date_str = start[:10]
                parts.append(f"{date_str}: {item['summary']}")
            return "Esta semana: " + ". ".join(parts) + "."
        except Exception as e:
            logger.warning(f"Google Calendar week error: {e}")

    # Fallback local
    events = _load_local()
    week_events = []
    for ev in events:
        try:
            dt = datetime.fromisoformat(ev["start"])
            if now.date() <= dt.date() <= end.date():
                week_events.append(f"{_DIAS[dt.weekday()]} {dt.day} a las {dt.hour}:{dt.minute:02d}: {ev['title']}")
        except Exception:
            pass
    if not week_events:
        return "No tenés eventos agendados esta semana."
    return "Esta semana: " + ". ".join(week_events[:6]) + "."


def delete_event(title_fragment: str) -> str:
    """Elimina el primer evento local cuyo título contenga el fragmento dado."""
    events = _load_local()
    for i, ev in enumerate(events):
        if title_fragment.lower() in ev.get("title", "").lower():
            removed = events.pop(i)
            _save_local(events)
            return f"Evento '{removed['title']}' eliminado de la agenda."
    return f"No encontré ningún evento con '{title_fragment}' en la agenda local."
