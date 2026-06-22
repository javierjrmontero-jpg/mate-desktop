#!/usr/bin/env python3
"""
MATE Memory Tools — PRO
Memoria persistente entre sesiones: facts, preferencias, historial.
Almacena en .mate_memory.json junto al ejecutable.
"""

import os
import sys
import json
import logging
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

_DATA_DIR = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent.parent


def _resolve_storage_dir() -> Path:
    """Usa OneDrive/MATE-Sync si está disponible, si no el directorio local."""
    od_env = os.environ.get("ONEDRIVE_PATH", "")
    candidates = [Path(od_env)] if od_env else []
    candidates += [
        Path.home() / "OneDrive",
        Path.home() / "OneDrive - Personal",
        Path(os.environ.get("USERPROFILE", "")) / "OneDrive",
    ]
    for p in candidates:
        if p.exists():
            sync = p / "MATE-Sync"
            sync.mkdir(exist_ok=True)
            return sync
    return _DATA_DIR


_STORAGE_DIR = _resolve_storage_dir()
_MEM_FILE = _STORAGE_DIR / ".mate_memory.json"


def _load() -> dict:
    if _MEM_FILE.exists():
        try:
            return json.loads(_MEM_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"facts": {}, "preferences": {}}


def _save(data: dict):
    _MEM_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def remember(key: str, value: str) -> str:
    """Guarda un hecho o dato del usuario."""
    data = _load()
    data["facts"][key.lower().strip()] = {
        "value": value,
        "saved_at": datetime.now().isoformat(),
    }
    _save(data)
    return f"Anotado: {key} es {value}."


def recall(key: str) -> str:
    """Recupera un hecho guardado. Búsqueda parcial si no hay match exacto."""
    data = _load()
    k = key.lower().strip()
    entry = data["facts"].get(k)
    if entry:
        return f"{key.capitalize()}: {entry['value']}."
    # Búsqueda parcial
    matches = [(fk, fv) for fk, fv in data["facts"].items() if k in fk or fk in k]
    if matches:
        fk, fv = matches[0]
        return f"{fk.capitalize()}: {fv['value']}."
    return f"No tengo nada anotado sobre '{key}'."


def forget(key: str) -> str:
    """Olvida un hecho guardado."""
    data = _load()
    k = key.lower().strip()
    if k in data["facts"]:
        del data["facts"][k]
        _save(data)
        return f"Olvidé lo que sabía sobre '{key}'."
    return f"No tenía nada guardado sobre '{key}'."


def list_memories() -> str:
    """Lista todos los hechos recordados."""
    data = _load()
    if not data["facts"]:
        return "No tengo ningún dato guardado todavía. Podés decirme 'recuerda que...' para guardar algo."
    items = [f"{k}: {v['value']}" for k, v in data["facts"].items()]
    top = items[:8]
    extra = f" y {len(items) - 8} más" if len(items) > 8 else ""
    return "Recuerdo: " + ". ".join(top) + extra + "."


def set_preference(pref: str, value: str) -> str:
    """Guarda una preferencia del usuario."""
    data = _load()
    data["preferences"][pref.lower().strip()] = value
    _save(data)
    return f"Preferencia guardada: {pref} = {value}."


def _sanitize_for_prompt(s: str) -> str:
    """HIGH-3: elimina marcadores de protocolo MATE y limita longitud para evitar prompt injection."""
    import re
    s = re.sub(r'\[RUN_PY:.+?\]', '[BLOQUEADO]', s, flags=re.DOTALL)
    s = re.sub(r'\[(STATUS|CONV|CONFIRM_EMAIL):', '[', s)
    return s[:200]


def get_context_summary() -> str:
    """
    Retorna un resumen del contexto del usuario para inyectar en prompts del API.
    Vacío si no hay datos.
    """
    data = _load()
    if not data["facts"] and not data["preferences"]:
        return ""
    parts = []
    if data["facts"]:
        facts_str = ", ".join(
            f"{k}: {_sanitize_for_prompt(v['value'])}"
            for k, v in list(data["facts"].items())[:6]
        )
        parts.append(f"Datos del usuario: {facts_str}")
    if data["preferences"]:
        prefs_str = ", ".join(
            f"{k}: {_sanitize_for_prompt(str(v))}"
            for k, v in data["preferences"].items()
        )
        parts.append(f"Preferencias: {prefs_str}")
    return " | ".join(parts)
