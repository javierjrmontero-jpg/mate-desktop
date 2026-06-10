"""
MATE Wake Word — Paso 1: Generar muestras de audio
===================================================
Genera ~500 variaciones sintéticas de "Oye MATE" usando edge-tts
(voces Microsoft, sin costo, buena calidad en español).

Las muestras se guardan como WAV 16kHz mono, listo para OpenWakeWord.

Ejecutar:
    python 01_generate_samples.py

Requiere: edge-tts, ffmpeg en el PATH (NO requiere pydub)
    pip install edge-tts
    winget install ffmpeg   (o desde https://ffmpeg.org/download.html)
"""

import asyncio
import io
import os
import subprocess
import tempfile
from pathlib import Path
import edge_tts

# ─── Configuración ────────────────────────────────────────────────────────────
POSITIVE_DIR = Path("samples/positive")   # muestras del wake word
POSITIVE_DIR.mkdir(parents=True, exist_ok=True)

# Variaciones ortográficas y fonéticas del wake word
# Incluir variaciones comunes de pronunciación natural
PHRASES = [
    "Oye MATE",
    "Oye Mate",
    "oye mate",
    "Ey MATE",
    "Ey Mate",
    "ey mate",
    "Oye, MATE",
    "Che MATE",       # variación rioplatense
    "Hola MATE",
    "MATE",           # invocación directa sin prefijo
]

# Voces en español disponibles en edge-tts
# El modelo entrenado con múltiples voces generaliza mejor
VOICES = [
    "es-AR-ElenaNeural",    # Argentina femenino  ← acento de Javier
    "es-AR-TomasNeural",    # Argentina masculino ← acento de Javier
    "es-ES-AlvaroNeural",   # España masculino
    "es-ES-ElviraNeural",   # España femenino
    "es-MX-DaliaNeural",    # México femenino
    "es-MX-JorgeNeural",    # México masculino
    "es-US-AlonsoNeural",   # EE.UU. masculino
    "es-US-PalomaNeural",   # EE.UU. femenino
]

# Variaciones de velocidad (simula distintos ritmos de habla)
RATES = ["-20%", "-10%", "+0%", "+10%", "+20%", "+30%"]
# ──────────────────────────────────────────────────────────────────────────────


def mp3_bytes_to_wav_16k(mp3_bytes: bytes) -> bytes | None:
    """
    Convierte MP3 (en memoria) a WAV 16kHz mono usando ffmpeg via subprocess.
    No requiere pydub — funciona en Python 3.13+.
    """
    try:
        # Escribir MP3 a archivo temporal
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f_in:
            f_in.write(mp3_bytes)
            tmp_in = f_in.name

        tmp_out = tmp_in.replace(".mp3", ".wav")

        subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", tmp_in,
                "-ar", "16000",   # 16kHz
                "-ac", "1",       # mono
                "-f", "wav",
                tmp_out,
            ],
            capture_output=True,
            check=True,
        )

        wav_bytes = Path(tmp_out).read_bytes()
        return wav_bytes

    except FileNotFoundError:
        raise RuntimeError(
            "ffmpeg no encontrado. Instalá con: winget install ffmpeg\n"
            "Luego cerrá y volvé a abrir PowerShell."
        )
    except subprocess.CalledProcessError as e:
        print(f"  ⚠️  ffmpeg error: {e.stderr.decode()[:200]}")
        return None
    finally:
        for p in [tmp_in, tmp_out]:
            try:
                os.unlink(p)
            except Exception:
                pass


async def tts_to_wav_bytes(phrase: str, voice: str, rate: str) -> bytes | None:
    """Genera audio con edge-tts y retorna bytes WAV 16kHz mono."""
    try:
        communicate = edge_tts.Communicate(phrase, voice, rate=rate)
        mp3_buffer = io.BytesIO()

        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                mp3_buffer.write(chunk["data"])

        if mp3_buffer.tell() == 0:
            return None

        return mp3_bytes_to_wav_16k(mp3_buffer.getvalue())

    except RuntimeError:
        raise  # propagar el error de ffmpeg no encontrado
    except Exception as e:
        print(f"  ⚠️  Error con '{phrase}' / {voice} / {rate}: {e}")
        return None


async def main():
    count = 0
    errors = 0
    combos = [(p, v, r) for p in PHRASES for v in VOICES for r in RATES]
    total = len(combos)

    print(f"📦 Generando {total} muestras para 'Oye MATE'...")
    print(f"   Frases: {len(PHRASES)} | Voces: {len(VOICES)} | Velocidades: {len(RATES)}\n")

    # Procesar en lotes para no saturar edge-tts
    batch_size = 8
    for i in range(0, total, batch_size):
        batch = combos[i:i + batch_size]

        results = await asyncio.gather(*[
            tts_to_wav_bytes(phrase, voice, rate)
            for phrase, voice, rate in batch
        ])

        for (phrase, voice, rate), wav_bytes in zip(batch, results):
            if wav_bytes is None:
                errors += 1
                continue

            path = POSITIVE_DIR / f"sample_{count:04d}.wav"
            path.write_bytes(wav_bytes)
            count += 1

        progress = min(i + batch_size, total)
        print(f"  ✓ {progress}/{total} combinaciones | {count} archivos generados", end="\r")

    print(f"\n\n✅ Generación completa: {count} muestras WAV en '{POSITIVE_DIR}'")
    if errors:
        print(f"   ⚠️  {errors} errores (reintentar si hay muchos)")
    print(f"\n➡  Siguiente paso: python 02_train_model.py")


if __name__ == "__main__":
    asyncio.run(main())
