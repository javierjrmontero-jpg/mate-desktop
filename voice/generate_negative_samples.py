import asyncio
from pathlib import Path
import edge_tts

NEGATIVE_PHRASES = [
    "hola",
    "buen día",
    "qué hora es",
    "abrir navegador",
    "enciende la luz",
    "apagar la luz",
    "cómo está el clima",
    "iniciar sistema",
    "cerrar ventana",
    "subir volumen",
    "bajar volumen",
    "vamos a probar",
    "esto es una prueba",
    "necesito ayuda",
    "abrir calendario",
    "leer mensajes",
    "activar música",
    "detener reproducción",
    "modo silencio",
    "buscar información",
]

VOICES = [
    "es-AR-ElenaNeural",
    "es-AR-TomasNeural",
    "es-MX-DaliaNeural",
    "es-MX-JorgeNeural",
    "es-ES-ElviraNeural",
    "es-ES-AlvaroNeural",
]

RATES = ["-20%", "-10%", "+0%", "+10%", "+20%"]

OUT_DIR = Path("samples/negative")
OUT_DIR.mkdir(parents=True, exist_ok=True)

async def generate():
    count = 0

    for phrase in NEGATIVE_PHRASES:
        for voice in VOICES:
            for rate in RATES:
                count += 1
                filename = OUT_DIR / f"neg_{count:04d}.mp3"

                communicate = edge_tts.Communicate(
                    text=phrase,
                    voice=voice,
                    rate=rate
                )

                await communicate.save(str(filename))
                print(f"Generado: {filename}")

    print(f"\nListo. Muestras negativas generadas: {count}")

asyncio.run(generate())