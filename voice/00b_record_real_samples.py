"""
MATE Wake Word — Paso 0b: Grabar muestras reales (tu mic, tu ambiente)
======================================================================
Complementa las muestras sintéticas (TTS) y los negativos genéricos del
paso 1 con grabaciones hechas con tu propio micrófono y en tu ambiente
real — es el cambio que más reduce los falsos positivos en producción.

Modos:
    python 00b_record_real_samples.py positivo
    python 00b_record_real_samples.py negativo

Ejecutar desde wakeword/ con el entorno mate-wakeword-env activo.
"""

import sys
import wave
import numpy as np
import sounddevice as sd
from pathlib import Path

SAMPLE_RATE = 16000
POSITIVE_DIR = Path("samples/positive")
NEGATIVE_DIR = Path("samples/negative")
POSITIVE_DIR.mkdir(parents=True, exist_ok=True)
NEGATIVE_DIR.mkdir(parents=True, exist_ok=True)

CLIP_SECONDS_POS         = 2.0    # duración de cada grabación positiva
NEGATIVE_SESSION_SECONDS = 120    # duración de la grabación continua de ambiente
# Clips LARGOS (no ~1.5s): cada clip de 20s ≈ 250 frames de embeddings, lo que
# permite a _sliding_windows() del entrenamiento generar ~59 ventanas reales
# por clip (vs. ~1 con clips de 1.5s). Esto es lo que de verdad le da al
# clasificador el volumen de "ventanas intermedias" que necesita para dejar
# de derivar hacia score alto en silencio/ambiente continuo.
NEGATIVE_CLIP_SECONDS    = 20.0   # tamaño de cada clip trozado
NEGATIVE_CLIP_STRIDE     = 10.0   # paso entre clips (overlap 50% → más diversidad)


def save_wav(path: Path, audio_int16: np.ndarray) -> None:
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(audio_int16.tobytes())


def record_seconds(seconds: float) -> np.ndarray:
    audio = sd.rec(int(seconds * SAMPLE_RATE), samplerate=SAMPLE_RATE, channels=1, dtype="int16")
    sd.wait()
    return np.squeeze(audio)


def grabar_positivas() -> None:
    existentes = len(list(POSITIVE_DIR.glob("real_*.wav")))
    print("📌 Modo POSITIVO — decí '¡Oye MATE!' con tu voz y tu micrófono real.")
    print(f"   Recomendado: 30-50 grabaciones, variando distancia, volumen y momento del día.")
    print(f"   Ya existen {existentes} grabaciones reales positivas.\n")
    i = existentes
    while True:
        cmd = input(f"[{i + 1}] Enter para grabar {CLIP_SECONDS_POS:.0f}s (o 'q' para salir): ").strip().lower()
        if cmd == "q":
            break
        print("   🔴 Grabando...", end="", flush=True)
        audio = record_seconds(CLIP_SECONDS_POS)
        path = POSITIVE_DIR / f"real_{i:03d}.wav"
        save_wav(path, audio)
        print(f" guardado → {path.name}")
        i += 1
    print(f"\n✅ Total grabaciones reales positivas: {i}")


def grabar_negativas() -> None:
    existentes = len(list(NEGATIVE_DIR.glob("real_*.wav")))
    print("📌 Modo NEGATIVO — grabación continua de tu ambiente real.")
    print(f"   Se grabarán {NEGATIVE_SESSION_SECONDS:.0f}s de corrido y se trocearán en clips de {NEGATIVE_CLIP_SECONDS:.1f}s.")
    print("   Sugerencia: hablá de otra cosa, poné música/TV, tipeá, movete por la habitación —")
    print("   todo MENOS decir 'Oye MATE'.")
    print(f"   Ya existen {existentes} clips reales negativos.\n")
    input("Presioná Enter para empezar a grabar...")
    print(f"   🔴 Grabando {NEGATIVE_SESSION_SECONDS:.0f}s...", end="", flush=True)
    audio = record_seconds(NEGATIVE_SESSION_SECONDS)
    print(" listo. Troceando...")

    clip_len = int(NEGATIVE_CLIP_SECONDS * SAMPLE_RATE)
    stride = int(NEGATIVE_CLIP_STRIDE * SAMPLE_RATE)
    i = existentes
    pos = 0
    while pos + clip_len <= len(audio):
        save_wav(NEGATIVE_DIR / f"real_{i:03d}.wav", audio[pos:pos + clip_len])
        pos += stride
        i += 1
    print(f"✅ Generados {i - existentes} clips reales nuevos (total: {i})")


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] not in ("positivo", "negativo"):
        print("Uso:")
        print("  python 00b_record_real_samples.py positivo")
        print("  python 00b_record_real_samples.py negativo")
        sys.exit(1)

    if sys.argv[1] == "positivo":
        grabar_positivas()
    else:
        grabar_negativas()


if __name__ == "__main__":
    main()
