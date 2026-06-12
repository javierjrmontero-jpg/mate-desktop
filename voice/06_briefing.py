"""
MATE — Briefing matutino
========================
Llama a /api/v1/briefing y lee el resumen del día en voz alta.

Ejecutar manualmente:
    python 06_briefing.py

O programarlo para ejecutarse cada mañana (ej: 8:00):
    Usar el scheduler de Cowork o el Programador de tareas de Windows.

Requiere el venv activado:
    .\\mate-wakeword-env\\Scripts\\Activate.ps1
    python 06_briefing.py
"""

import asyncio
import io
import sys
from pathlib import Path

import requests

# ─── Configuración (mismo que 03_service.py) ──────────────────────────────────
MATE_URL    = "https://mate.local"
MATE_USER   = "javierjrmontero@outlook.com"
MATE_PASSWORD = "Tomy#6358"
TTS_VOICE   = "es-AR-ElenaNeural"
VERIFY_SSL  = False
# ──────────────────────────────────────────────────────────────────────────────


def login() -> str | None:
    try:
        res = requests.post(
            f"{MATE_URL}/api/v1/auth/login",
            json={"email": MATE_USER, "password": MATE_PASSWORD},
            verify=VERIFY_SSL, timeout=10,
        )
        res.raise_for_status()
        return res.json().get("token")
    except Exception as e:
        print(f"❌ Error al autenticar: {e}")
        return None


async def _tts_generate(text: str) -> bytes:
    try:
        import edge_tts
    except ImportError:
        print("⚠️  edge_tts no instalado — pip install edge-tts")
        return b""
    communicate = edge_tts.Communicate(text, voice=TTS_VOICE)
    chunks = []
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            chunks.append(chunk["data"])
    return b"".join(chunks)


def speak(text: str) -> None:
    """Lee texto en voz alta (edge_tts → pydub → sounddevice)."""
    try:
        mp3_bytes = asyncio.run(_tts_generate(text))
        if not mp3_bytes:
            return

        from pydub import AudioSegment
        import sounddevice as sd
        import numpy as np

        audio = AudioSegment.from_file(io.BytesIO(mp3_bytes), format="mp3")
        samples = np.array(audio.get_array_of_samples(), dtype=np.float32)
        samples /= 2 ** (8 * audio.sample_width - 1)
        if audio.channels == 2:
            samples = samples.reshape((-1, 2))

        sd.play(samples, samplerate=audio.frame_rate)
        sd.wait()
    except Exception as e:
        print(f"   [tts] Error: {e}")


def main():
    print("☀️  MATE — Briefing matutino")
    print("─" * 40)

    token = login()
    if not token:
        sys.exit(1)

    try:
        res = requests.get(
            f"{MATE_URL}/api/v1/briefing",
            headers={"Authorization": f"Bearer {token}"},
            verify=VERIFY_SSL,
            timeout=30,
        )
        res.raise_for_status()
        data = res.json()
    except Exception as e:
        print(f"❌ Error obteniendo briefing: {e}")
        sys.exit(1)

    text = data.get("text", "")
    sections = data.get("sections", {})

    print(f"\n📋 Briefing:\n{text}\n")

    # Mostrar datos estructurados
    cal = sections.get("calendar") or {}
    today_events = cal.get("today", [])
    if today_events:
        print(f"📅 Eventos hoy ({len(today_events)}):")
        for ev in today_events:
            print(f"   • {ev.get('summary')} — {ev.get('start', '')[:16]}")

    email_sec = sections.get("email") or {}
    print(f"\n📧 Emails no leídos: {email_sec.get('unread_count', 0)}")

    tasks_sec = sections.get("tasks") or {}
    print(f"✅ Tareas pendientes: {tasks_sec.get('pending_count', 0)}")

    print("\n🔊 Leyendo en voz alta...")
    speak(text)
    print("✓ Briefing completado.")


if __name__ == "__main__":
    main()
