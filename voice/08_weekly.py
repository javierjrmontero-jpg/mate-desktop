"""
MATE — Resumen semanal automático
===================================
Llama a GET /api/v1/briefing/weekly, lee el resumen por TTS
y lo envía por email (el backend hace el envío).

Ejecutar manualmente o via Scheduled Task (lunes 08:00):
    python 08_weekly.py

Para probar sin enviar email:
    python 08_weekly.py --no-mail
"""
import asyncio
import io
import sys
import shutil
import requests

MATE_URL      = "https://mate.local"
MATE_USER     = "javierjrmontero@outlook.com"
MATE_PASSWORD = "Tomy#6358"
TTS_VOICE     = "es-AR-ElenaNeural"
VERIFY_SSL    = False


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


async def _tts(text: str) -> bytes:
    try:
        import edge_tts
        communicate = edge_tts.Communicate(text, voice=TTS_VOICE)
        chunks = []
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                chunks.append(chunk["data"])
        return b"".join(chunks)
    except ImportError:
        return b""


def speak(text: str) -> None:
    try:
        mp3 = asyncio.run(_tts(text))
        if not mp3:
            print(f"   [tts] {text}")
            return
        from pydub import AudioSegment
        import sounddevice as sd
        import numpy as np

        # Asegurar que pydub encuentre ffmpeg
        ffmpeg = shutil.which("ffmpeg") or shutil.which("ffmpeg.exe")
        if ffmpeg:
            AudioSegment.converter = ffmpeg

        audio = AudioSegment.from_file(io.BytesIO(mp3), format="mp3")
        samples = np.array(audio.get_array_of_samples(), dtype=np.float32)
        samples /= 2 ** (8 * audio.sample_width - 1)
        if audio.channels == 2:
            samples = samples.reshape((-1, 2))
        sd.play(samples, samplerate=audio.frame_rate)
        sd.wait()
    except Exception as e:
        print(f"   [tts] Error: {e}")


def main():
    send_mail = "--no-mail" not in sys.argv

    token = login()
    if not token:
        sys.exit(1)

    print("📊 Generando resumen semanal...")
    try:
        res = requests.get(
            f"{MATE_URL}/api/v1/briefing/weekly",
            params={"send_mail": "true" if send_mail else "false"},
            headers={"Authorization": f"Bearer {token}"},
            verify=VERIFY_SSL,
            timeout=60,
        )
        res.raise_for_status()
        data = res.json()
    except Exception as e:
        print(f"❌ Error al obtener resumen: {e}")
        sys.exit(1)

    text = data.get("text", "No se pudo generar el resumen.")
    print(f"\n📝 Resumen:\n{text}\n")

    if data.get("email_sent"):
        print("✅ Resumen enviado por email.")
    elif send_mail:
        print("⚠️  No se pudo enviar el email (revisar config SMTP).")

    speak(text)
    print("✅ Briefing semanal completado.")


if __name__ == "__main__":
    main()
