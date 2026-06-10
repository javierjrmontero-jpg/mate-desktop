"""
MATE Wake Word — Paso opcional: Agregar muestras de tu propia voz
=================================================================
Grabá ~50 muestras de "Oye MATE" con tu voz real.
Esto mejora significativamente la detección porque el modelo
aprende tu acento y entonación específicos.

Ejecutar:
    python 04_add_my_voice.py

Controles:
    ENTER  → grabar muestra (hablar dentro de los 3 segundos)
    q + ENTER → terminar
"""

import sounddevice as sd
import numpy as np
import io, wave
from pathlib import Path

OUTPUT_DIR = Path("samples/positive")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

SAMPLE_RATE    = 16000
RECORD_SECONDS = 2.5     # duración de cada grabación
TARGET_SAMPLES = 20


def record_sample() -> bytes:
    print("  🔴 Grabando... di 'Oye MATE' ahora", end="", flush=True)
    audio = sd.rec(
        int(RECORD_SECONDS * SAMPLE_RATE),
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="int16",
    )
    sd.wait()
    print(" ✓")

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(audio.tobytes())
    return buf.getvalue()


def main():
    # Detectar siguiente índice libre
    existing = list(OUTPUT_DIR.glob("voice_*.wav"))
    start_idx = len(existing)

    print(f"📢 Grabación de voz propia para 'Oye MATE'")
    print(f"   Ya tenés {start_idx} muestras propias. Objetivo: {TARGET_SAMPLES}")
    print(f"   ENTER para grabar | q + ENTER para salir\n")

    count = start_idx
    while count < start_idx + TARGET_SAMPLES:
        remaining = start_idx + TARGET_SAMPLES - count
        cmd = input(f"  [{count - start_idx + 1}/{TARGET_SAMPLES}] ENTER para grabar ({remaining} restantes): ")
        if cmd.strip().lower() == "q":
            break

        wav_bytes = record_sample()

        path = OUTPUT_DIR / f"voice_{count:04d}.wav"
        path.write_bytes(wav_bytes)
        count += 1

    total_own = count - start_idx
    print(f"\n✅ {total_own} muestras propias guardadas en '{OUTPUT_DIR}'")
    print(f"➡  Reejecutar 02_train_model.py para re-entrenar con tu voz incluida.")


if __name__ == "__main__":
    main()
