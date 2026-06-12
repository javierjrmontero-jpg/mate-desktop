"""
MATE — Monitor proactivo
========================
Corre en segundo plano y anuncia por TTS:
  - Emails nuevos (cuando aumenta el conteo de no leídos)
  - Eventos próximos (15 min antes de empezar)

Ejecutar en una terminal separada:
    python 07_monitor.py

Ctrl+C para detener.

Puede correr en paralelo con 03_service.py — usan el micrófono
en momentos distintos (el monitor solo habla, no escucha).
"""

import asyncio
import io
import time
import threading
from datetime import datetime, timedelta
from pathlib import Path

import requests

# ─── Configuración ────────────────────────────────────────────────────────────
MATE_URL      = "https://mate.local"
MATE_USER     = "javierjrmontero@outlook.com"
MATE_PASSWORD = "Tomy#6358"
TTS_VOICE     = "es-AR-ElenaNeural"
VERIFY_SSL    = False

POLL_INTERVAL       = 300    # segundos entre chequeos (5 min)
EVENT_WARN_MINUTES  = 15     # avisar X minutos antes de un evento
EMAIL_COOLDOWN      = 600    # no volver a anunciar emails por X segundos
# ──────────────────────────────────────────────────────────────────────────────

_token: str | None = None
_last_unread_count: int | None = None
_announced_events: set[str] = set()   # IDs de eventos ya anunciados
_last_email_announce: float = 0.0


# ══════════════════════════════════════════════════════════════════════════════
# Auth
# ══════════════════════════════════════════════════════════════════════════════

def login() -> str | None:
    try:
        res = requests.post(
            f"{MATE_URL}/api/v1/auth/login",
            json={"email": MATE_USER, "password": MATE_PASSWORD},
            verify=VERIFY_SSL, timeout=10,
        )
        res.raise_for_status()
        token = res.json().get("token")
        print(f"✅ Autenticado como {MATE_USER}")
        return token
    except Exception as e:
        print(f"❌ Error al autenticar: {e}")
        return None


def auth_headers() -> dict:
    return {"Authorization": f"Bearer {_token}"}


def refresh_token() -> None:
    """Renueva el token silenciosamente (el JWT expira en ~24h)."""
    global _token
    new = login()
    if new:
        _token = new


# ══════════════════════════════════════════════════════════════════════════════
# TTS
# ══════════════════════════════════════════════════════════════════════════════

async def _tts_generate(text: str) -> bytes:
    try:
        import edge_tts
    except ImportError:
        return b""
    communicate = edge_tts.Communicate(text, voice=TTS_VOICE)
    chunks = []
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            chunks.append(chunk["data"])
    return b"".join(chunks)


def speak(text: str) -> None:
    try:
        mp3 = asyncio.run(_tts_generate(text))
        if not mp3:
            print(f"   [tts] {text}")
            return
        from pydub import AudioSegment
        import sounddevice as sd
        import numpy as np
        audio = AudioSegment.from_file(io.BytesIO(mp3), format="mp3")
        samples = np.array(audio.get_array_of_samples(), dtype=np.float32)
        samples /= 2 ** (8 * audio.sample_width - 1)
        if audio.channels == 2:
            samples = samples.reshape((-1, 2))
        sd.play(samples, samplerate=audio.frame_rate)
        sd.wait()
    except Exception as e:
        print(f"   [tts] Error: {e}")


def notify_windows(title: str, msg: str) -> None:
    try:
        from win10toast import ToastNotifier
        ToastNotifier().show_toast(title, msg, duration=4, threaded=True)
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════════════════════
# Checks
# ══════════════════════════════════════════════════════════════════════════════

def check_emails() -> None:
    """Anuncia si hay más emails no leídos que en el último chequeo."""
    global _last_unread_count, _last_email_announce

    try:
        res = requests.get(
            f"{MATE_URL}/api/v1/email/unread",
            headers=auth_headers(),
            verify=VERIFY_SSL,
            timeout=20,
        )
        if res.status_code == 401:
            refresh_token()
            return
        res.raise_for_status()
        emails = res.json()
        count = len(emails)

        if _last_unread_count is None:
            _last_unread_count = count
            return   # primera vez, solo guardar baseline

        new_count = count - _last_unread_count
        now = time.time()

        if new_count > 0 and (now - _last_email_announce) > EMAIL_COOLDOWN:
            senders = list({
                e.get("from", "desconocido").split("<")[0].strip()
                for e in emails[:new_count]
            })[:3]
            msg = (
                f"Tenés {new_count} email{'s' if new_count > 1 else ''} nuevo{'s' if new_count > 1 else ''}. "
                f"De: {', '.join(senders)}."
            )
            print(f"📧 {msg}")
            notify_windows("MATE — Email nuevo", f"{new_count} email{'s' if new_count>1 else ''}")
            speak(msg)
            _last_email_announce = now

        _last_unread_count = count

    except Exception as e:
        print(f"   [monitor] Error chequeando emails: {e}")


def check_calendar() -> None:
    """Anuncia eventos que empiezan en los próximos EVENT_WARN_MINUTES minutos."""
    global _announced_events

    try:
        res = requests.get(
            f"{MATE_URL}/api/v1/calendar/events?days=1&limit=20",
            headers=auth_headers(),
            verify=VERIFY_SSL,
            timeout=20,
        )
        if res.status_code == 401:
            refresh_token()
            return
        if not res.ok:
            return
        events = res.json()

        now = datetime.now()
        warn_until = now + timedelta(minutes=EVENT_WARN_MINUTES)

        for ev in events:
            ev_id = ev.get("id") or ev.get("summary", "") + ev.get("start", "")
            if ev_id in _announced_events:
                continue

            start_str = ev.get("start", "")
            if not start_str or "T" not in start_str:
                continue   # evento de día completo, skip

            try:
                ev_start = datetime.fromisoformat(start_str.replace("Z", "+00:00")).replace(tzinfo=None)
            except Exception:
                continue

            if now <= ev_start <= warn_until:
                mins = int((ev_start - now).total_seconds() / 60)
                summary = ev.get("summary", "Evento sin título")
                msg = (
                    f"Recordatorio: en {mins} minuto{'s' if mins != 1 else ''} "
                    f"tenés '{summary}'."
                )
                print(f"📅 {msg}")
                notify_windows("MATE — Recordatorio", f"En {mins}min: {summary}")
                speak(msg)
                _announced_events.add(ev_id)

    except Exception as e:
        print(f"   [monitor] Error chequeando calendario: {e}")


def check_followups() -> None:
    """Anuncia emails enviados hace +48h sin respuesta."""
    global _announced_events

    try:
        res = requests.get(
            f"{MATE_URL}/api/v1/email/unanswered",
            headers=auth_headers(),
            verify=VERIFY_SSL,
            timeout=30,
        )
        if res.status_code == 401:
            refresh_token()
            return
        if not res.ok:
            return
        data = res.json()
        unanswered = data.get("unanswered", [])

        for email in unanswered:
            followup_id = f"followup_{email.get('subject','')[:40]}_{email.get('sent_date','')[:10]}"
            if followup_id in _announced_events:
                continue

            hours = email.get("hours_ago", 0)
            subject = email.get("subject", "email sin asunto")
            to = email.get("to", "").split("@")[0] if "@" in email.get("to", "") else email.get("to", "")
            msg = f"Seguimiento pendiente: enviaste un email a {to} hace {hours} horas sobre '{subject}' y no hay respuesta."
            print(f"📬 {msg}")
            notify_windows("MATE — Seguimiento", f"{hours}h sin respuesta: {subject[:40]}")
            speak(msg)
            _announced_events.add(followup_id)

    except Exception as e:
        print(f"   [monitor] Error chequeando seguimientos: {e}")



def check_rules() -> None:
    """Evalúa reglas autónomas y ejecuta acciones si se cumplen las condiciones."""
    try:
        res = requests.get(
            f"{MATE_URL}/api/v1/rules",
            headers=auth_headers(),
            verify=VERIFY_SSL,
            timeout=20,
        )
        if res.status_code == 401:
            refresh_token()
            return
        if not res.ok:
            return
        rules = [r for r in res.json() if r.get("enabled")]
    except Exception as e:
        print(f"   [rules] Error obteniendo reglas: {e}")
        return

    if not rules:
        return

    # Caché de datos para evitar múltiples llamadas
    _cache: dict = {}

    def _get_unread_count() -> int:
        if "unread" not in _cache:
            try:
                r = requests.get(f"{MATE_URL}/api/v1/email/unread",
                                 headers=auth_headers(), verify=VERIFY_SSL, timeout=20)
                _cache["unread"] = len(r.json()) if r.ok else 0
            except Exception:
                _cache["unread"] = 0
        return _cache["unread"]

    def _get_tasks() -> list:
        if "tasks" not in _cache:
            try:
                r = requests.get(f"{MATE_URL}/api/v1/tasks?completed=false",
                                 headers=auth_headers(), verify=VERIFY_SSL, timeout=20)
                _cache["tasks"] = r.json() if r.ok else []
            except Exception:
                _cache["tasks"] = []
        return _cache["tasks"]

    def _get_followups() -> int:
        if "followups" not in _cache:
            try:
                r = requests.get(f"{MATE_URL}/api/v1/email/unanswered",
                                 headers=auth_headers(), verify=VERIFY_SSL, timeout=20)
                _cache["followups"] = r.json().get("count", 0) if r.ok else 0
            except Exception:
                _cache["followups"] = 0
        return _cache["followups"]

    now = datetime.utcnow()

    for rule in rules:
        rid = rule["id"]
        ctype = rule["condition_type"]
        cparams = rule.get("condition_params", {})
        atype = rule["action_type"]
        aparams = rule.get("action_params", {})
        cooldown = rule.get("cooldown_minutes", 60)
        last_trig = rule.get("last_triggered")

        # Verificar cooldown
        if last_trig:
            try:
                lt = datetime.fromisoformat(last_trig.replace("Z", "+00:00")).replace(tzinfo=None)
                if (now - lt).total_seconds() < cooldown * 60:
                    continue
            except Exception:
                pass

        # Evaluar condición
        threshold = int(cparams.get("threshold", 1))
        triggered = False
        count = 0

        if ctype == "unread_gt":
            count = _get_unread_count()
            triggered = count > threshold

        elif ctype == "overdue_tasks_gt":
            tasks = _get_tasks()
            today = datetime.utcnow().date()
            overdue = [t for t in tasks
                       if t.get("due_date") and
                       datetime.fromisoformat(t["due_date"][:10]).date() < today]
            count = len(overdue)
            triggered = count > threshold

        elif ctype == "due_today_gt":
            tasks = _get_tasks()
            today = datetime.utcnow().date()
            due_today = [t for t in tasks
                         if t.get("due_date") and
                         datetime.fromisoformat(t["due_date"][:10]).date() == today]
            count = len(due_today)
            triggered = count > threshold

        elif ctype == "followups_pending":
            count = _get_followups()
            triggered = count > threshold

        if not triggered:
            continue

        # Ejecutar acción
        msg_template = aparams.get("message", rule["name"])
        msg = msg_template.replace("{count}", str(count))

        print(f"   [rules] Regla activada: {rule['name']} (count={count})")

        if atype == "tts":
            speak(msg)

        elif atype == "notify":
            title = aparams.get("title", "MATE — Alerta")
            notify_windows(title, msg[:80])

        elif atype == "create_task":
            task_title = aparams.get("title", rule["name"]).replace("{count}", str(count))
            try:
                requests.post(
                    f"{MATE_URL}/api/v1/tasks",
                    json={"title": task_title, "priority": aparams.get("priority", "high")},
                    headers=auth_headers(), verify=VERIFY_SSL, timeout=10,
                )
            except Exception as e:
                print(f"   [rules] Error creando tarea: {e}")

        # Marcar como disparada
        try:
            requests.patch(
                f"{MATE_URL}/api/v1/rules/{rid}/triggered",
                headers=auth_headers(), verify=VERIFY_SSL, timeout=10,
            )
        except Exception:
            pass

# ══════════════════════════════════════════════════════════════════════════════
# Loop principal
# ══════════════════════════════════════════════════════════════════════════════

def monitor_loop() -> None:
    print(f"\n🟢 Monitor proactivo activo")
    print(f"   Emails: cada {POLL_INTERVAL//60} min | Eventos: aviso {EVENT_WARN_MINUTES} min antes\n")

    # Primer chequeo inmediato para establecer baseline de emails
    check_emails()

    last_token_refresh = time.time()
    TOKEN_REFRESH_INTERVAL = 23 * 3600   # refrescar token cada 23h

    while True:
        time.sleep(POLL_INTERVAL)

        # Refrescar token si está por vencer
        if time.time() - last_token_refresh > TOKEN_REFRESH_INTERVAL:
            refresh_token()
            last_token_refresh = time.time()

        print(f"   [{datetime.now().strftime('%H:%M')}] Chequeando...")
        check_emails()
        check_calendar()
        check_followups()
        check_rules()


def main():
    global _token
    _token = login()
    if not _token:
        import sys; sys.exit(1)

    try:
        monitor_loop()
    except KeyboardInterrupt:
        print("\n\n🔴 Monitor detenido.")


if __name__ == "__main__":
    main()
