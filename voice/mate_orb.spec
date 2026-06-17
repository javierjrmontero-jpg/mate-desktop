# mate_orb.spec — PyInstaller spec para empaquetar MATE como EXE standalone
#
# Uso (desde voice/ con el venv activo):
#   pip install pyinstaller
#   pyinstaller mate_orb.spec
#
# Output: dist/MATE/MATE.exe  +  todas las DLLs necesarias
# Tamaño estimado: 400-700 MB (incluye Python runtime + modelos)
#
# IMPORTANTE: El modelo STT (Whisper medium, ~1.5 GB) NO se incluye en el EXE.
# Se descarga una vez en el primer arranque a %USERPROFILE%\.cache\huggingface\
# Para pre-bundlear el modelo, ver comentario en la sección datas.

block_cipher = None

import sys
from pathlib import Path

# Rutas
VOICE_DIR  = Path(SPECPATH)
TOOLS_DIR  = VOICE_DIR / "tools"
MODELS_DIR = VOICE_DIR / "models"

a = Analysis(
    [str(VOICE_DIR / "mate_orb.py")],
    pathex=[str(VOICE_DIR)],
    binaries=[],
    datas=[
        # Modelo de wake word custom — obligatorio
        (str(MODELS_DIR / "oye_mate.onnx"), "models"),

        # Archivos de tools
        (str(TOOLS_DIR / "*.py"), "tools"),

        # Template de configuración
        (str(VOICE_DIR / ".env.example"), "."),

        # Sonidos del sistema — fallback si Windows Media no está disponible
        # (str(VOICE_DIR / "sounds"), "sounds"),

        # Para pre-bundlear Whisper medium (descomenta y ajusta la ruta):
        # (r"C:\Users\jmontero\.cache\huggingface\hub\models--Systran--faster-whisper-medium",
        #  r"huggingface\hub\models--Systran--faster-whisper-medium"),
    ],
    hiddenimports=[
        # Qt
        "PyQt6.QtCore",
        "PyQt6.QtWidgets",
        "PyQt6.QtGui",
        "PyQt6.sip",
        # Audio
        "sounddevice",
        "numpy",
        # Wake word
        "openwakeword",
        "openwakeword.model",
        "openwakeword.utils",
        "onnxruntime",
        # STT
        "faster_whisper",
        "ctranslate2",
        # TTS
        "pyttsx3",
        "pyttsx3.drivers",
        "pyttsx3.drivers.sapi5",
        # Windows
        "win32gui",
        "win32con",
        "win32api",
        "pywintypes",
        "comtypes",
        "comtypes.client",
        "pycaw",
        "pycaw.pycaw",
        # System control
        "pyautogui",
        "pygetwindow",
        "screen_brightness_control",
        "psutil",
        # Imagen / visión
        "PIL",
        "PIL.Image",
        "PIL.ImageGrab",
        # Web tools
        "requests",
        "feedparser",
        "duckduckgo_search",
        # Spotify
        "spotipy",
        "spotipy.oauth2",
        # Notes / reminders
        "json",
        "pathlib",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "matplotlib",
        "IPython",
        "jupyter",
        "scipy",          # pesado, no requerido en runtime
        "sklearn",
        "torch",          # si resemblyzer no se incluye en el exe
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="MATE",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,          # sin ventana negra de consola
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,              # reemplazar con "mate_icon.ico" si existe
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="MATE",
)
