# mate_orb.spec
block_cipher = None

import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_all, collect_submodules, collect_data_files

VOICE_DIR  = Path(SPECPATH)
TOOLS_DIR  = VOICE_DIR / "tools"
MODELS_DIR = VOICE_DIR / "models"

# Recolectar paquetes con dependencias internas complejas
# en lugar de adivinar submodulos manualmente.
ow_datas,  ow_bins,  ow_hidden  = collect_all("openwakeword")
sp_hidden                        = collect_submodules("scipy")
sk_hidden                        = collect_submodules("sklearn")

a = Analysis(
    [str(VOICE_DIR / "mate_orb.py")],
    pathex=[str(VOICE_DIR)],
    binaries=ow_bins,
    datas=[
        (str(MODELS_DIR / "oye_mate.onnx"), "models"),
        (str(TOOLS_DIR / "*.py"), "tools"),
        (str(VOICE_DIR / "secure_config.py"), "."),
        (str(VOICE_DIR / "mate_setup.py"), "."),
        (str(VOICE_DIR / ".env.example"), "."),
        *ow_datas,
    ],
    hiddenimports=[
        *ow_hidden,
        *sp_hidden,
        *sk_hidden,
        # Qt
        "PyQt6.QtCore", "PyQt6.QtWidgets", "PyQt6.QtGui", "PyQt6.sip",
        # Audio
        "sounddevice", "numpy",
        # STT / wake word
        "faster_whisper", "ctranslate2",
        "onnxruntime", "onnxruntime.capi",
        "onnxruntime.capi.onnxruntime_inference_collection",
        # TTS
        "pyttsx3", "pyttsx3.drivers", "pyttsx3.drivers.sapi5",
        "win32com", "win32com.client", "pythoncom",
        # Windows
        "win32gui", "win32con", "win32api", "win32process",
        "win32crypt", "win32security",
        "pywintypes", "winreg", "winsound",
        "comtypes", "comtypes.client",
        "pycaw", "pycaw.pycaw",
        # System
        "pyautogui", "pygetwindow", "pygetwindow._pygetwindow_win",
        "screen_brightness_control", "screen_brightness_control.windows",
        "psutil",
        # PIL
        "PIL", "PIL.Image", "PIL.ImageGrab",
        # Web / feeds
        "requests", "feedparser", "duckduckgo_search",
        # Spotify
        "spotipy", "spotipy.oauth2", "spotipy.util",
        # Setup y config cifrada
        "secure_config", "mate_setup",
        # Tools (imports lazy — PyInstaller no los detecta)
        "tools", "tools.system_control", "tools.web_tools",
        "tools.spotify_tools", "tools.file_tools",
        "tools.notes_tools", "tools.reminder_tools",
        # PRO tools
        "tools.memory_tools", "tools.dev_agent_tools",
        "tools.ghost_operator", "tools.messaging_tools",
        "tools.calendar_tools", "tools.briefing_tools",
        # Calendar (Google API — opcional, no falla si no está instalado)
        "google.oauth2", "google.oauth2.credentials",
        "google_auth_oauthlib", "google_auth_oauthlib.flow",
        "google.auth.transport.requests",
        "googleapiclient", "googleapiclient.discovery",
        # Stdlib que PyInstaller puede omitir en windowed mode
        "webbrowser", "base64", "urllib.parse", "queue", "shutil",
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "IPython", "jupyter", "torch"],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="MATE",
    debug=False,
    strip=False,
    upx=True,
    console=False,
    icon=None,
)

coll = COLLECT(
    exe, a.binaries, a.zipfiles, a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="MATE",
)
