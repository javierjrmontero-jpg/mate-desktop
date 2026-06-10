"""
MATE Wake Word Service — Producción
=====================================
Escucha el micrófono continuamente. Al detectar "Oye MATE":
  1. Graba el comando (hasta ~4s de silencio)
  2. Lo transcribe via Whisper en el servidor MATE
  3. Envía el texto al chat de MATE como si el usuario lo hubiera escrito

Ejecutar:
    python 03_service.py

Requiere el modelo entrenado en: models/oye_mate.onnx
"""

import numpy as np
import sounddevice as sd
import requests
import json
import io
import wave
import time
import threading
import sys
from pathlib import Path
from openwakeword.model import Model

# ─── Configuración — EDITAR ANTES DE USAR ─────────────────────────────────────
MATE_URL       = "https://mate.local"         # o IP Tailscale: https://100.74.230.46
MATE_USER      = "javierjrmontero@outlook.com"
MATE_PASSWORD  = "Tomy#6358"           # se usa solo para obtener el token JWT

WAKEWORD_MODEL = str(Path(__file__).parent / "models" / "oye_mate.onnx")
THRESHOLD      = 0.5          # sensibilidad (0.0–1.0). Bajar si hay falsos negativos.
SAMPLE_RATE    = 16000        # Hz — no cambiar (requerido por OpenWakeWord)
CHUNK          = 1280         # frames por chunk (~80ms a 16kHz)

# Grabación del comando tras el wake word
COMMAND_DURATION    = 5.0     # máx segundos de grabación
SILENCE_THRESHOLD   = 0.015   # amplitud RMS para detectar silencio
SILENCE_DURATION    = 1.5     # segundos de silencio antes de cortar

VERIFY_SSL     = False        # False: ignorar cert autofirmado de mate.local
# ──────────────────────────────────────────────────────────────────────────────

_token: str | None = None


def login() -> str | None:
    """Obtiene JWT del servidor MATE."""
    try:
        res = requests.post(
            f"{MATE_URL}/api/v1/auth/login",
            json={"email": MATE_USER, "password": MATE_PASSWORD},
            verify=VERIFY_SSL,
            timeout=10,
        )
        res.raise_for_status()
        # El backend de MATE responde {"token": "...", "name": "...", "email": "..."}
        # — la clave del JWT es "token", NO "access_token".
        token = res.json().get("token")
        if not token:
            print(f"❌ Login OK pero la respuesta no trae 'token': {res.json()}")
            return None
        print(f"✅ Autenticado como {MATE_USER}")
        return token
    except Exception as e:
        print(f"❌ Error al autenticar: {e}")
        return None


def auth_headers() -> dict:
    return {
        "Authorization": f"Bearer {_token}",
        "Content-Type": "application/json",
    }


def record_command() -> bytes:
    """
    Graba audio hasta detectar silencio o alcanzar COMMAND_DURATION.
    Retorna bytes WAV 16kHz mono.
    """
    frames = []
    silent_chunks = 0
    silence_chunks_needed = int(SILENCE_DURATION * SAMPLE_RATE / CHUNK)
    max_chunks = int(COMMAND_DURATION * SAMPLE_RATE / CHUNK)

    print("🎙  Escuchando comando...", end="", flush=True)

    with sd.InputStream(samplerate=SAMPLE_RATE, channels=1,
                        dtype="int16", blocksize=CHUNK) as stream:
        for _ in range(max_chunks):
            chunk, _ = stream.read(CHUNK)
            frames.append(chunk.copy())

            rms = np.sqrt(np.mean(chunk.astype(np.float32) ** 2)) / 32768.0
            if rms < SILENCE_THRESHOLD:
                silent_chunks += 1
                if silent_chunks >= silence_chunks_needed:
                    break
            else:
                silent_chunks = 0

    print(f" {len(frames) * CHUNK / SAMPLE_RATE:.1f}s grabados")

    # Construir WAV en memoria
    audio_data = np.concatenate(frames, axis=0)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(audio_data.tobytes())
    return buf.getvalue()


def transcribe(wav_bytes: bytes) -> str | None:
    """Envía el audio a /api/v1/transcribe y retorna el texto."""
    try:
        res = requests.post(
            f"{MATE_URL}/api/v1/transcribe",
            headers={"Authorization": f"Bearer {_token}"},
            files={"file": ("audio.wav", wav_bytes, "audio/wav")},
            verify=VERIFY_SSL,
            timeout=20,
        )
        res.raise_for_status()
        text = res.json().get("text", "").strip()
        return text if text else None
    except Exception as e:
        print(f"❌ Error transcribiendo: {e}")
        return None


def send_to_mate(text: str) -> None:
    """Envía el texto al endpoint de chat de MATE (fire-and-forget)."""
    try:
        res = requests.post(
            f"{MATE_URL}/api/v1/chat",
            headers=auth_headers(),
            json={"messages": [{"role": "user", "content": text}], "conversation_id": None},
            verify=VERIFY_SSL,
            timeout=60,
            stream=True,
        )
        res.raise_for_status()
        # Consumir el stream para que el servidor lo procese completo
        response_text = ""
        for line in res.iter_lines():
            if line and line.startswith(b"data: "):
                payload = line[6:].decode("utf-8")
                if payload == "[DONE]":
                    break
                try:
                    chunk = json.loads(payload)
                    if isinstance(chunk, str) and not chunk.startswith("["):
                        response_text += chunk
                except Exception:
                    pass

        if response_text:
            print(f"🤖 MATE: {response_text[:120]}{'...' if len(response_text) > 120 else ''}")

    except Exception as e:
        print(f"❌ Error enviando mensaje: {e}")


def notify_windows(title: str, message: str) -> None:
    """Notificación nativa de Windows (no bloquea)."""
    try:
        from win10toast import ToastNotifier
        notifier = ToastNotifier()
        threading.Thread(
            target=notifier.show_toast,
            args=(title, message),
            kwargs={"duration": 3, "threaded": True},
            daemon=True,
        ).start()
    except ImportError:
        pass  # win10toast no instalada — ignorar


def listen_loop(oww: Model) -> None:
    """Loop principal: escucha micrófono y actúa al detectar el wake word."""
    print(f"\n🟢 MATE Wake Word Service activo")
    print(f"   Threshold: {THRESHOLD} | Escuchando 'Oye MATE'...\n")

    last_detection = 0.0
    COOLDOWN = 3.0  # segundos mínimos entre detecciones

    with sd.InputStream(samplerate=SAMPLE_RATE, channels=1,
                        dtype="int16", blocksize=CHUNK) as stream:
        while True:
            chunk, _ = stream.read(CHUNK)
            audio_np = np.squeeze(chunk).astype(np.float32) / 32768.0

            oww.predict(audio_np)

            # Revisar scores de todos los modelos cargados
            for model_name, scores in oww.prediction_buffer.items():
                if not scores:
                    continue
                score = scores[-1]
                if score > THRESHOLD:
                    now = time.time()
                    if now - last_detection < COOLDOWN:
                        continue  # evitar doble detección

                    last_detection = now
                    print(f"\n🔊 ¡Wake word detectado! (score: {score:.3f})")
                    notify_windows("MATE", "🎙️ Escuchando...")

                    oww.reset()  # resetear buffer para evitar eco

                    # Grabar y procesar el comando
                    wav = record_command()
                    text = transcribe(wav)

                    if text:
                        print(f"📝 '{text}'")
                        notify_windows("MATE", f"📝 {text[:50]}")
                        send_to_mate(text)
                    else:
                        print("⚠️  No se detectó habla en el audio grabado.")

                    print(f"\n🟢 Escuchando 'Oye MATE'...")


def main():
    global _token

    # Verificar modelo
    model_path = Path(WAKEWORD_MODEL)
    if not model_path.exists():
        print(f"❌ Modelo no encontrado: {model_path}")
        print("   Ejecutar primero: python 02_train_model.py")
        sys.exit(1)

    # Autenticar
    _token = login()
    if not _token:
        print("❌ No se pudo autenticar. Verificar MATE_USER y MATE_PASSWORD.")
        sys.exit(1)

    # Cargar modelo de wake word
    print(f"🔧 Cargando modelo: {model_path.name}")
    oww = Model(
        wakeword_models=[str(model_path)],
        inference_framework="onnx",
    )
    print(f"   Modelos cargados: {list(oww.models.keys())}")

    # Iniciar loop (Ctrl+C para salir)
    try:
        listen_loop(oww)
    except KeyboardInterrupt:
        print("\n\n🔴 MATE Wake Word Service detenido.")


if __name__ == "__main__":
    main()
