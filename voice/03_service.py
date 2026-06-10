"""
MATE Wake Word Service — Producción
=====================================
Escucha el micrófono continuamente. Al detectar "Oye MATE":
  1. Verifica que el hablante es Javier (resemblyzer, opcional)
  2. Graba el comando (hasta ~4s de silencio)
  3. Lo transcribe via Whisper en el servidor MATE
  4. Envía el texto al chat de MATE como si el usuario lo hubiera escrito

Ejecutar:
    python 03_service.py

Requiere el modelo entrenado en: models/oye_mate.onnx
Perfil de hablante (opcional): speaker_profile/javier.npy
  → Generar con: python 00c_enroll_speaker.py
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

# resemblyzer — importación opcional (verificación de hablante)
try:
    from resemblyzer import VoiceEncoder, preprocess_wav as _resemble_preprocess_wav
    _RESEMBLYZER_AVAILABLE = True
except ImportError:
    _RESEMBLYZER_AVAILABLE = False

# ─── Configuración — EDITAR ANTES DE USAR ─────────────────────────────────────
MATE_URL       = "https://mate.local"         # o IP Tailscale: https://100.74.230.46
MATE_USER      = "javierjrmontero@outlook.com"
MATE_PASSWORD  = "Tomy#6358"   # se usa solo para obtener el token JWT

WAKEWORD_MODEL = str(Path(__file__).parent / "models" / "oye_mate.onnx")
THRESHOLD      = 0.90         # Calibrado tras reentrenar con ventanas deslizantes
                              # reales (ver _sliding_windows en 02_train_model.py)
                              # + debounce de CONSECUTIVE_FRAMES_REQUIRED en
                              # listen_loop(). Picos de ruido en pruebas reales
                              # llegan hasta ~0.95 pero son de UN solo frame —
                              # el debounce los filtra. "Oye MATE" real disparó
                              # en pruebas con score ~0.98-0.99 sostenido.
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
# ──────────────────────────────────────────────────────────────────────────────

_token: str | None = None
_voice_encoder: "VoiceEncoder | None" = None
_speaker_profile: "np.ndarray | None" = None


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


def load_speaker_profile() -> bool:
    """
    Carga el encoder resemblyzer y el perfil de hablante.
    Retorna True si todo está disponible, False si hay que saltar la verificación.
    """
    global _voice_encoder, _speaker_profile

    if not SPEAKER_VERIFICATION:
        return False

    if not _RESEMBLYZER_AVAILABLE:
        print("⚠️  resemblyzer no instalado — verificación de hablante desactivada.")
        print("   Para activarla: pip install resemblyzer")
        print("   Luego ejecutar: python 00c_enroll_speaker.py")
        return False

    profile_path = Path(SPEAKER_PROFILE)
    if not profile_path.exists():
        print(f"⚠️  Perfil de hablante no encontrado: {profile_path}")
        print("   Para generarlo: python 00c_enroll_speaker.py")
        print("   Continuando sin verificación de hablante.")
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
    """
    Compara el audio grabado contra el perfil de hablante almacenado.
    Retorna (coincide: bool, similitud: float).
    Siempre retorna (True, 1.0) si la verificación está desactivada o sin perfil.
    """
    if _voice_encoder is None or _speaker_profile is None:
        return True, 1.0

    try:
        # Decodificar WAV a float32
        with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
            frames = wf.readframes(wf.getnframes())
        audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0

        # Necesitamos al menos 1 segundo de audio con señal
        rms = float(np.sqrt(np.mean(audio ** 2)))
        if rms < 0.005:
            print("   [speaker] Señal de audio insuficiente para verificar")
            return True, 1.0  # beneficio de la duda si no hay señal

        wav_preprocessed = _resemble_preprocess_wav(audio, SAMPLE_RATE)
        embedding = _voice_encoder.embed_utterance(wav_preprocessed)
        embedding = embedding / np.linalg.norm(embedding)

        similarity = float(np.dot(_speaker_profile, embedding))
        matches = similarity >= SPEAKER_THRESHOLD
        return matches, similarity

    except Exception as e:
        print(f"   [speaker] Error en verificación: {e}")
        return True, 1.0  # ante error, no bloquear


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

    # Debounce: exigir varios frames CONSECUTIVOS por encima del umbral antes
    # de disparar. Con los datos reales ya separados (silencio/ambiente ~0.00-
    # 0.05 vs. picos > 0.9), lo que queda son picos AISLADOS de un solo frame
    # (ruido transitorio: un click, un fragmento de palabra) que cruzan el
    # umbral por 80ms y vuelven a 0 — eso disparó las 3 falsas detecciones del
    # último log (todas con "No se detectó habla"). Decir "Oye MATE" sostiene
    # el score alto durante ~6-12 frames consecutivos (≈0.5-1s); el ruido no.
    CONSECUTIVE_FRAMES_REQUIRED = 4   # ≈320ms de score sostenido > THRESHOLD
    consecutive_high = 0

    # ── DIAGNÓSTICO TEMPORAL ──────────────────────────────────────────────────
    # Imprime el score crudo de cada ventana (cada ~0.8s). Tuning completado y
    # validado (separación clara silencio/ruido vs. "Oye MATE" + debounce
    # filtrando picos transitorios) — desactivado para uso normal. Reactivar
    # poniendo en True si hace falta volver a diagnosticar.
    DEBUG_SCORES = False
    _dbg_counter = 0
    # ──────────────────────────────────────────────────────────────────────────

    with sd.InputStream(samplerate=SAMPLE_RATE, channels=1,
                        dtype="int16", blocksize=CHUNK) as stream:
        while True:
            chunk, _ = stream.read(CHUNK)
            # openwakeword.Model.predict() espera PCM int16 CRUDO — igual que
            # AudioFeatures.embed_clips() en el entrenamiento (ver pcm16 en
            # 02_train_model.py). Normalizar a float [-1,1] aquí (como hacía
            # antes esta línea) reduce la señal ~32.000 veces antes de llegar
            # al extractor de melspectrograma: a esa escala, todo (silencio,
            # ruido, "Oye MATE") se ve igual de "silencioso" → score constante.
            # Esto explica el score fijo en 0.673 visto en el debug, sin
            # importar el audio real de entrada.
            audio_np = np.squeeze(chunk).astype(np.int16)

            oww.predict(audio_np)

            # Revisar scores de todos los modelos cargados
            for model_name, scores in oww.prediction_buffer.items():
                if not scores:
                    continue
                score = scores[-1]

                if DEBUG_SCORES:
                    _dbg_counter += 1
                    if _dbg_counter % 10 == 0:  # ~1 print por segundo (10 chunks × 80ms)
                        print(f"   [debug] score crudo: {score:.3f}", flush=True)

                if score > THRESHOLD:
                    consecutive_high += 1
                else:
                    consecutive_high = 0

                if consecutive_high >= CONSECUTIVE_FRAMES_REQUIRED:
                    consecutive_high = 0  # reiniciar contador para la próxima detección

                    now = time.time()
                    if now - last_detection < COOLDOWN:
                        continue  # evitar doble detección

                    last_detection = now
                    print(f"\n🔊 ¡Wake word detectado! (score: {score:.3f})")
                    notify_windows("MATE", "🎙️ Escuchando...")

                    oww.reset()  # resetear buffer para evitar eco

                    # Grabar el comando
                    wav = record_command()

                    # Verificar hablante (si hay perfil cargado)
                    matches, similarity = verify_speaker(wav)
                    if _speaker_profile is not None:
                        status_icon = "✅" if matches else "🚫"
                        print(f"   {status_icon} Hablante: similitud={similarity:.3f} "
                              f"(threshold={SPEAKER_THRESHOLD})")

                    if not matches:
                        print("🚫 Hablante no reconocido — comando descartado.")
                        print(f"\n🟢 Escuchando 'Oye MATE'...")
                        continue

                    # Transcribir y enviar
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

    # Cargar perfil de hablante (opcional)
    speaker_active = load_speaker_profile()
    if speaker_active:
        print(f"   ✓ Verificación de hablante: ACTIVA (threshold={SPEAKER_THRESHOLD})")
    else:
        print(f"   ℹ  Verificación de hablante: INACTIVA")

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
