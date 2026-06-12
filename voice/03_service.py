"""
MATE Wake Word Service — Producción
=====================================
Escucha el micrófono continuamente. Al detectar "Oye MATE":
  1. Verifica que el hablante es Javier (resemblyzer, opcional)
  2. Graba el comando (hasta ~4s de silencio)
  3. Lo transcribe via Whisper en el servidor MATE
  4. Envía el texto al chat de MATE como si el usuario lo hubiera escrito
  5. Si la respuesta contiene [CONFIRM_EMAIL:...], lee el borrador en voz alta
     y espera confirmación oral antes de enviar.

Ejecutar:
    python 03_service.py

Requiere el modelo entrenado en: models/oye_mate.onnx
Perfil de hablante (opcional): speaker_profile/javier.npy
  → Generar con: python 00c_enroll_speaker.py
"""

import asyncio
import io
import json
import threading
import time
import sys
import wave
from pathlib import Path

import numpy as np
import requests
import sounddevice as sd
from openwakeword.model import Model

# resemblyzer — importación opcional (verificación de hablante)
try:
    from resemblyzer import VoiceEncoder, preprocess_wav as _resemble_preprocess_wav
    _RESEMBLYZER_AVAILABLE = True
except ImportError:
    _RESEMBLYZER_AVAILABLE = False

# edge_tts — importación opcional (TTS para confirmación de email)
try:
    import edge_tts as _edge_tts
    _EDGE_TTS_AVAILABLE = True
except ImportError:
    _EDGE_TTS_AVAILABLE = False

# ─── Configuración — EDITAR ANTES DE USAR ─────────────────────────────────────
MATE_URL       = "https://mate.local"         # o IP Tailscale: https://100.74.230.46
MATE_USER      = "javierjrmontero@outlook.com"
MATE_PASSWORD  = "Tomy#6358"   # se usa solo para obtener el token JWT

WAKEWORD_MODEL = str(Path(__file__).parent / "models" / "oye_mate.onnx")
THRESHOLD      = 0.90         # Calibrado tras reentrenar con ventanas deslizantes
SAMPLE_RATE    = 16000        # Hz — no cambiar (requerido por OpenWakeWord)
CHUNK          = 1280         # frames por chunk (~80ms a 16kHz)

# Grabación del comando tras el wake word
COMMAND_DURATION    = 5.0     # máx segundos de grabación
SILENCE_THRESHOLD   = 0.015   # amplitud RMS para detectar silencio
SILENCE_DURATION    = 1.5     # segundos de silencio antes de cortar

VERIFY_SSL     = False        # False: ignorar cert autofirmado de mate.local

# ─── Verificación de hablante (resemblyzer) ───────────────────────────────────
SPEAKER_VERIFICATION = True   # False: deshabilitar completamente la verificación
SPEAKER_PROFILE      = str(Path(__file__).parent / "speaker_profile" / "javier.npy")
SPEAKER_THRESHOLD    = 0.75   # similitud coseno mínima para aceptar el hablante
                               # - Si rechaza tu voz: bajar a 0.70
                               # - Si acepta otras voces: subir a 0.80

# ─── TTS para confirmación de email ───────────────────────────────────────────
TTS_VOICE      = "es-AR-ElenaNeural"   # voz edge_tts (es-AR, es-ES, es-MX…)
# ──────────────────────────────────────────────────────────────────────────────

_token: str | None = None
_voice_encoder: "VoiceEncoder | None" = None
_speaker_profile: "np.ndarray | None" = None


# ══════════════════════════════════════════════════════════════════════════════
# Auth
# ══════════════════════════════════════════════════════════════════════════════

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


# ══════════════════════════════════════════════════════════════════════════════
# Audio helpers
# ══════════════════════════════════════════════════════════════════════════════

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


# ══════════════════════════════════════════════════════════════════════════════
# TTS (edge_tts)
# ══════════════════════════════════════════════════════════════════════════════

async def _tts_generate(text: str) -> bytes:
    """Genera audio MP3 en memoria usando edge_tts."""
    communicate = _edge_tts.Communicate(text, voice=TTS_VOICE)
    chunks = []
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            chunks.append(chunk["data"])
    return b"".join(chunks)


def speak(text: str) -> None:
    """
    Lee texto en voz alta.
    Requiere: edge_tts, pydub (con ffmpeg), sounddevice.
    Si alguno falta, imprime el texto en consola como fallback.
    """
    if not _EDGE_TTS_AVAILABLE:
        print(f"   [tts] (sin audio) {text}")
        return
    try:
        mp3_bytes = asyncio.run(_tts_generate(text))

        from pydub import AudioSegment
        audio = AudioSegment.from_file(io.BytesIO(mp3_bytes), format="mp3")
        samples = np.array(audio.get_array_of_samples(), dtype=np.float32)
        samples /= 2 ** (8 * audio.sample_width - 1)   # normalizar a [-1, 1]
        if audio.channels == 2:
            samples = samples.reshape((-1, 2))

        sd.play(samples, samplerate=audio.frame_rate)
        sd.wait()
    except Exception as e:
        print(f"   [tts] Error: {e} — texto: {text[:80]}")


# ══════════════════════════════════════════════════════════════════════════════
# Confirmación por voz de email
# ══════════════════════════════════════════════════════════════════════════════

_CONFIRM_WORDS = {"sí", "si", "confirmo", "confirmar", "enviar", "envío", "ok", "dale", "yes"}
_CANCEL_WORDS  = {"cancelar", "no", "cancel", "descartar"}


def voice_confirm_email(draft: dict) -> None:
    """
    Lee el borrador de email en voz alta, escucha confirmación oral
    y llama a /api/v1/email/send-confirmed si se confirma.
    """
    to      = draft.get("to", "")
    subject = draft.get("subject", "")
    body    = draft.get("body", "")
    acct_id = draft.get("account_id")
    label   = draft.get("account_label", "")

    # ── Leer borrador en voz alta ─────────────────────────────────────────────
    body_preview = (body[:200] + "...") if len(body) > 200 else body
    tts_text = (
        f"Tenés un email listo para enviar. "
        f"Destinatario: {to}. "
        f"Asunto: {subject}. "
        f"Contenido: {body_preview}. "
        f"Cuenta: {label}. "
        f"Decí 'confirmo' para enviar o 'cancelar' para descartar."
    )

    notify_windows("MATE — Email pendiente", f"📧 {to} | {subject}")
    print(f"\n📧 Borrador de email:")
    print(f"   Para:   {to}")
    print(f"   Asunto: {subject}")
    print(f"   Cuerpo: {body[:100]}{'...' if len(body) > 100 else ''}")
    speak(tts_text)

    # ── Escuchar respuesta ────────────────────────────────────────────────────
    print("   🎤 Esperando confirmación...")
    wav = record_command()
    response = transcribe(wav)

    if not response:
        print("   ⚠️  Sin respuesta — email descartado.")
        speak("No entendí la respuesta. Email descartado.")
        return

    print(f"   🗣  Respondiste: '{response}'")
    words = set(response.lower().split())

    if words & _CONFIRM_WORDS:
        # ── Enviar ────────────────────────────────────────────────────────────
        try:
            payload: dict = {"to": to, "subject": subject, "body": body}
            if acct_id:
                payload["account_id"] = acct_id

            res = requests.post(
                f"{MATE_URL}/api/v1/email/send-confirmed",
                headers=auth_headers(),
                json=payload,
                verify=VERIFY_SSL,
                timeout=15,
            )
            res.raise_for_status()
            data = res.json()
            if data.get("sent"):
                print(f"   ✅ Email enviado a {to}")
                notify_windows("MATE", f"✅ Email enviado a {to}")
                speak(f"Email enviado correctamente a {to}.")
            else:
                err = data.get("error", "Error desconocido")
                print(f"   ❌ El servidor reportó error: {err}")
                speak("Hubo un error al enviar el email.")
        except Exception as e:
            print(f"   ❌ Error al confirmar email: {e}")
            speak("Hubo un error al enviar el email.")

    elif words & _CANCEL_WORDS:
        print("   🚫 Email cancelado por el usuario.")
        notify_windows("MATE", "🚫 Email cancelado")
        speak("Email cancelado.")

    else:
        print(f"   ❓ Respuesta no reconocida: '{response}' — email descartado.")
        speak("No reconocí la respuesta. Email descartado por seguridad.")


# ══════════════════════════════════════════════════════════════════════════════
# Speaker verification (resemblyzer)
# ══════════════════════════════════════════════════════════════════════════════

def load_speaker_profile() -> bool:
    global _voice_encoder, _speaker_profile

    if not SPEAKER_VERIFICATION:
        return False

    if not _RESEMBLYZER_AVAILABLE:
        print("⚠️  resemblyzer no instalado — verificación de hablante desactivada.")
        return False

    profile_path = Path(SPEAKER_PROFILE)
    if not profile_path.exists():
        print(f"⚠️  Perfil de hablante no encontrado: {profile_path}")
        print("   Para generarlo: python 00c_enroll_speaker.py")
        return False

    try:
        print("🔧 Cargando VoiceEncoder (resemblyzer)...")
        _voice_encoder = VoiceEncoder()
        _speaker_profile = np.load(str(profile_path))
        print(f"   ✓ Perfil cargado: {profile_path.name}")
        return True
    except Exception as e:
        print(f"⚠️  Error cargando perfil de hablante: {e}")
        return False


def verify_speaker(wav_bytes: bytes) -> tuple[bool, float]:
    if _voice_encoder is None or _speaker_profile is None:
        return True, 1.0

    try:
        with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
            frames = wf.readframes(wf.getnframes())
        audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0

        rms = float(np.sqrt(np.mean(audio ** 2)))
        if rms < 0.005:
            print("   [speaker] Señal insuficiente — omitiendo verificación")
            return True, 1.0

        wav_pre = _resemble_preprocess_wav(audio, SAMPLE_RATE)
        emb = _voice_encoder.embed_utterance(wav_pre)
        emb = emb / np.linalg.norm(emb)
        similarity = float(np.dot(_speaker_profile, emb))
        return similarity >= SPEAKER_THRESHOLD, similarity

    except Exception as e:
        print(f"   [speaker] Error: {e}")
        return True, 1.0


# ══════════════════════════════════════════════════════════════════════════════
# Windows notifications
# ══════════════════════════════════════════════════════════════════════════════

def notify_windows(title: str, message: str) -> None:
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
        pass


# ══════════════════════════════════════════════════════════════════════════════
# MATE chat
# ══════════════════════════════════════════════════════════════════════════════

def send_to_mate(text: str) -> None:
    """
    Envía el texto al endpoint de chat de MATE y consume el stream SSE.
    Si detecta [CONFIRM_EMAIL:...] en la respuesta, activa la confirmación
    por voz DESPUÉS de recibir la respuesta completa.
    """
    pending_draft: dict | None = None

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

        response_text = ""
        for line in res.iter_lines():
            if not line or not line.startswith(b"data: "):
                continue
            payload = line[6:].decode("utf-8")
            if payload == "[DONE]":
                break
            try:
                chunk = json.loads(payload)
                if not isinstance(chunk, str):
                    continue

                if chunk.startswith("[CONFIRM_EMAIL:"):
                    # Formato: [CONFIRM_EMAIL:{...json...}]
                    # Extraer el JSON interno (strip prefix + trailing ']')
                    try:
                        inner = chunk[len("[CONFIRM_EMAIL:"):-1]
                        pending_draft = json.loads(inner)
                    except Exception as e:
                        print(f"   [confirm] Error parseando borrador: {e}")

                elif not chunk.startswith("["):
                    response_text += chunk

            except Exception:
                pass

        if response_text:
            print(f"🤖 MATE: {response_text[:120]}{'...' if len(response_text) > 120 else ''}")

    except Exception as e:
        print(f"❌ Error enviando mensaje: {e}")
        return

    # ── Confirmación por voz (fuera del stream para no mezclar audio) ─────────
    if pending_draft:
        voice_confirm_email(pending_draft)


# ══════════════════════════════════════════════════════════════════════════════
# Main loop
# ══════════════════════════════════════════════════════════════════════════════

def listen_loop(oww: Model) -> None:
    print(f"\n🟢 MATE Wake Word Service activo")
    print(f"   Threshold: {THRESHOLD} | Escuchando 'Oye MATE'...\n")

    last_detection = 0.0
    COOLDOWN = 3.0

    CONSECUTIVE_FRAMES_REQUIRED = 4
    consecutive_high = 0

    DEBUG_SCORES = False
    _dbg_counter = 0

    with sd.InputStream(samplerate=SAMPLE_RATE, channels=1,
                        dtype="int16", blocksize=CHUNK) as stream:
        while True:
            chunk, _ = stream.read(CHUNK)
            audio_np = np.squeeze(chunk).astype(np.int16)
            oww.predict(audio_np)

            for model_name, scores in oww.prediction_buffer.items():
                if not scores:
                    continue
                score = scores[-1]

                if DEBUG_SCORES:
                    _dbg_counter += 1
                    if _dbg_counter % 10 == 0:
                        print(f"   [debug] score: {score:.3f}", flush=True)

                if score > THRESHOLD:
                    consecutive_high += 1
                else:
                    consecutive_high = 0

                if consecutive_high >= CONSECUTIVE_FRAMES_REQUIRED:
                    consecutive_high = 0

                    now = time.time()
                    if now - last_detection < COOLDOWN:
                        continue
                    last_detection = now

                    print(f"\n🔊 ¡Wake word detectado! (score: {score:.3f})")
                    notify_windows("MATE", "🎙️ Escuchando...")
                    oww.reset()

                    # Grabar comando
                    wav = record_command()

                    # Verificar hablante
                    matches, similarity = verify_speaker(wav)
                    if _speaker_profile is not None:
                        icon = "✅" if matches else "🚫"
                        print(f"   {icon} Hablante: {similarity:.3f} (th={SPEAKER_THRESHOLD})")

                    if not matches:
                        print("🚫 Hablante no reconocido — comando descartado.")
                        print(f"\n🟢 Escuchando 'Oye MATE'...")
                        continue

                    # Transcribir y enviar (la confirmación por voz ocurre dentro)
                    text = transcribe(wav)
                    if text:
                        print(f"📝 '{text}'")
                        notify_windows("MATE", f"📝 {text[:50]}")
                        send_to_mate(text)
                    else:
                        print("⚠️  No se detectó habla.")

                    print(f"\n🟢 Escuchando 'Oye MATE'...")


def main():
    global _token

    model_path = Path(WAKEWORD_MODEL)
    if not model_path.exists():
        print(f"❌ Modelo no encontrado: {model_path}")
        print("   Ejecutar primero: python 02_train_model.py")
        sys.exit(1)

    _token = login()
    if not _token:
        print("❌ No se pudo autenticar.")
        sys.exit(1)

    speaker_active = load_speaker_profile()
    print(f"   {'✓ Verificación de hablante: ACTIVA' if speaker_active else 'ℹ  Verificación de hablante: INACTIVA'}"
          f"{f' (threshold={SPEAKER_THRESHOLD})' if speaker_active else ''}")

    print(f"🔧 Cargando modelo: {Path(WAKEWORD_MODEL).name}")
    oww = Model(wakeword_models=[str(model_path)], inference_framework="onnx")
    print(f"   Modelos cargados: {list(oww.models.keys())}")

    try:
        listen_loop(oww)
    except KeyboardInterrupt:
        print("\n\n🔴 MATE Wake Word Service detenido.")


if __name__ == "__main__":
    main()
