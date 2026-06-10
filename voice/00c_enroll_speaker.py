"""
MATE Wake Word — Paso 00c: Enrolamiento de hablante con resemblyzer
====================================================================
Graba segmentos de tu voz, genera un embedding promedio y lo guarda
como perfil de hablante. El servicio (03_service.py) usa este perfil
para verificar que el comando viene de vos antes de procesarlo.

Prerequisito:
    pip install resemblyzer

Ejecutar:
    python 00c_enroll_speaker.py

El perfil se guarda en: speaker_profile/javier.npy

Notas:
  - Hablar con naturalidad, no forzar la voz.
  - El threshold predeterminado en el servicio es 0.75.
    Si genera falsos negativos (rechaza tu voz), bajar a 0.70.
    Si genera falsos positivos (acepta otras voces), subir a 0.80.
"""

import sys
import io
import wave
import time
from pathlib import Path

import numpy as np
import sounddevice as sd

try:
    from resemblyzer import VoiceEncoder, preprocess_wav
except ImportError:
    print("❌ resemblyzer no instalado. Ejecutar:")
    print("   pip install resemblyzer")
    sys.exit(1)

# ─── Configuración ────────────────────────────────────────────────────────────
PROFILE_DIR     = Path(__file__).parent / "speaker_profile"
PROFILE_NAME    = "javier"
SAMPLE_RATE     = 16000
SEGMENT_SECONDS = 5.0    # duración de cada segmento a grabar
NUM_SEGMENTS    = 5      # segmentos para promediar el embedding
# ──────────────────────────────────────────────────────────────────────────────

PROFILE_DIR.mkdir(exist_ok=True)
PROFILE_PATH = PROFILE_DIR / f"{PROFILE_NAME}.npy"


def record_segment(idx: int) -> np.ndarray:
    """Graba un segmento y retorna array float32 normalizado."""
    print(f"\n  [{idx}/{NUM_SEGMENTS}] Preparate... grabando en 2s", end="", flush=True)
    time.sleep(2)
    print(f"\r  [{idx}/{NUM_SEGMENTS}] 🔴 Grabando {SEGMENT_SECONDS:.0f}s — hablá normalmente...    ", end="", flush=True)

    audio = sd.rec(
        int(SEGMENT_SECONDS * SAMPLE_RATE),
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="int16",
    )
    sd.wait()
    print(f"\r  [{idx}/{NUM_SEGMENTS}] ✓ Capturado                                              ")

    samples = np.squeeze(audio).astype(np.float32) / 32768.0
    return samples


def wav_float_to_bytes(audio: np.ndarray) -> bytes:
    """Convierte float32 a bytes WAV 16kHz mono."""
    pcm = (audio * 32768.0).clip(-32768, 32767).astype(np.int16)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(pcm.tobytes())
    return buf.getvalue()


def main():
    print("=" * 60)
    print("  MATE — Enrolamiento de hablante (resemblyzer)")
    print("=" * 60)
    print(f"\n  Se grabarán {NUM_SEGMENTS} segmentos de {SEGMENT_SECONDS:.0f}s.")
    print("  Hablá con naturalidad durante cada grabación.")
    print("  Podés contar, leer en voz alta o simplemente hablar.")

    if PROFILE_PATH.exists():
        print(f"\n⚠️  Ya existe un perfil en: {PROFILE_PATH}")
        ans = input("  ¿Sobreescribir? [s/N]: ").strip().lower()
        if ans != "s":
            print("  Operación cancelada.")
            sys.exit(0)

    print("\n  Cargando VoiceEncoder...")
    encoder = VoiceEncoder()
    print("  ✓ Encoder listo\n")

    embeddings = []
    for i in range(1, NUM_SEGMENTS + 1):
        input(f"  Presioná ENTER cuando estés listo para el segmento {i}/{NUM_SEGMENTS}")
        audio = record_segment(i)

        # Verificar que hay señal de audio
        rms = float(np.sqrt(np.mean(audio ** 2)))
        if rms < 0.005:
            print(f"  ⚠️  Señal muy baja (RMS={rms:.4f}) — repetir segmento recomendado.")
        else:
            print(f"     RMS: {rms:.4f} — señal OK")

        # Generar embedding
        wav_preprocessed = preprocess_wav(audio, SAMPLE_RATE)
        emb = encoder.embed_utterance(wav_preprocessed)
        embeddings.append(emb)

    # Promediar embeddings y renormalizar
    profile = np.mean(embeddings, axis=0)
    profile = profile / np.linalg.norm(profile)

    # Verificar consistencia entre segmentos
    similarities = [
        float(np.dot(profile, e / np.linalg.norm(e)))
        for e in embeddings
    ]
    print(f"\n📊 Similitud de cada segmento vs. perfil promedio:")
    for i, sim in enumerate(similarities, 1):
        bar = "█" * int(sim * 40)
        print(f"   Seg {i}: {sim:.4f}  {bar}")
    print(f"   Promedio: {np.mean(similarities):.4f}  |  Mín: {np.min(similarities):.4f}")

    if np.min(similarities) < 0.70:
        print("\n⚠️  Algunos segmentos tienen baja similitud. Considerar re-enrolar.")
    else:
        print("\n✅ Consistencia del perfil: buena")

    # Guardar
    np.save(PROFILE_PATH, profile)
    print(f"\n💾 Perfil guardado en: {PROFILE_PATH}")
    print(f"\nThreshold recomendado en 03_service.py: SPEAKER_THRESHOLD = 0.75")
    print(f"  - Si rechaza tu voz: bajarlo a 0.70")
    print(f"  - Si acepta otras voces: subirlo a 0.80")


if __name__ == "__main__":
    main()
