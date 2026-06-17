#!/usr/bin/env python3
"""
MATE Dev Agent — PRO
Ejecutar código Python y comandos PowerShell por voz.
Scripts generados por MATE API se guardan en mate_scripts/.
"""

import sys
import os
import subprocess
import logging
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

_DATA_DIR    = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent.parent
_SCRIPTS_DIR = _DATA_DIR / "mate_scripts"
_LAST_SCRIPT = _DATA_DIR / ".last_script.py"


def _ensure_dir():
    _SCRIPTS_DIR.mkdir(exist_ok=True)


def run_python(code: str, name: str = "script") -> str:
    """
    Guarda y ejecuta un snippet de Python.
    Retorna las primeras 3 líneas de salida para TTS.
    """
    _ensure_dir()
    ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = _SCRIPTS_DIR / f"{name}_{ts}.py"
    path.write_text(code, encoding="utf-8")
    _LAST_SCRIPT.write_text(str(path), encoding="utf-8")

    try:
        result = subprocess.run(
            [sys.executable, str(path)],
            capture_output=True, text=True, timeout=30,
            cwd=str(_DATA_DIR),
        )
        out = (result.stdout or result.stderr or "").strip()
        lines = out.splitlines()[:3]
        summary = " | ".join(lines) if lines else "Script ejecutado sin salida visible."
        logger.info(f"Dev Agent Python [{path.name}]: {summary}")
        return summary
    except subprocess.TimeoutExpired:
        return "El script excedió el tiempo máximo de 30 segundos."
    except Exception as e:
        logger.error(f"Dev Agent run_python: {e}")
        return f"Error ejecutando el script: {e}"


def run_last_script() -> str:
    """Vuelve a ejecutar el último script guardado."""
    if not _LAST_SCRIPT.exists():
        return "No hay ningún script anterior guardado."
    path_str = _LAST_SCRIPT.read_text(encoding="utf-8").strip()
    path = Path(path_str)
    if not path.exists():
        return f"El script '{path.name}' ya no existe."
    try:
        result = subprocess.run(
            [sys.executable, str(path)],
            capture_output=True, text=True, timeout=30,
            cwd=str(_DATA_DIR),
        )
        out = (result.stdout or result.stderr or "").strip()
        lines = out.splitlines()[:3]
        return " | ".join(lines) if lines else "Ejecutado sin salida."
    except Exception as e:
        return f"Error: {e}"


def run_powershell(command: str) -> str:
    """Ejecuta un comando PowerShell y retorna la salida (máx 3 líneas)."""
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
            capture_output=True, text=True, timeout=30,
        )
        out = (result.stdout or result.stderr or "").strip()
        lines = out.splitlines()[:3]
        return " | ".join(lines) if lines else "Comando ejecutado sin salida."
    except subprocess.TimeoutExpired:
        return "Comando excedió 30 segundos."
    except Exception as e:
        return f"Error PowerShell: {e}"


def open_scripts_folder() -> str:
    """Abre la carpeta de scripts en el Explorador."""
    _ensure_dir()
    try:
        os.startfile(str(_SCRIPTS_DIR))
        return f"Abrí la carpeta de scripts."
    except Exception as e:
        return f"No pude abrir la carpeta: {e}"


def list_scripts() -> str:
    """Lista los últimos 5 scripts guardados."""
    _ensure_dir()
    scripts = sorted(_SCRIPTS_DIR.glob("*.py"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not scripts:
        return "No hay scripts guardados todavía."
    names = [s.name for s in scripts[:5]]
    return "Scripts recientes: " + ", ".join(names) + "."


def save_script(code: str, name: str = "script") -> str:
    """Guarda un script sin ejecutarlo."""
    _ensure_dir()
    ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = _SCRIPTS_DIR / f"{name}_{ts}.py"
    path.write_text(code, encoding="utf-8")
    _LAST_SCRIPT.write_text(str(path), encoding="utf-8")
    return f"Script guardado como {path.name}."
