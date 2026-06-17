#!/usr/bin/env python3
"""
MATE File Tools — F10-4
Gestión básica de archivos y carpetas por voz. Retorna strings listos para TTS.
Sin dependencias externas.
"""

import os
import shutil
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_HOME = Path.home()

_ALIASES: dict[str, Path] = {
    "escritorio":  _HOME / "Desktop",
    "desktop":     _HOME / "Desktop",
    "documentos":  _HOME / "Documents",
    "documents":   _HOME / "Documents",
    "descargas":   _HOME / "Downloads",
    "downloads":   _HOME / "Downloads",
    "imágenes":    _HOME / "Pictures",
    "imagenes":    _HOME / "Pictures",
    "pictures":    _HOME / "Pictures",
    "música":      _HOME / "Music",
    "musica":      _HOME / "Music",
    "videos":      _HOME / "Videos",
    "inicio":      _HOME,
    "home":        _HOME,
}

_READABLE_EXTENSIONS = {
    ".txt", ".md", ".log", ".csv", ".json",
    ".py", ".yaml", ".yml", ".ini", ".cfg", ".env", ".html", ".xml",
}


def _resolve(path_str: str) -> Path:
    """Convierte alias o ruta relativa a Path absoluto."""
    s = path_str.strip().lower()
    if s in _ALIASES:
        return _ALIASES[s]
    p = Path(path_str)
    if p.is_absolute():
        return p
    # relativo al home como fallback
    return _HOME / path_str


def list_directory(path_str: str) -> str:
    try:
        p = _resolve(path_str)
        if not p.exists():
            return f"No encontré la carpeta '{path_str}'."
        if not p.is_dir():
            return f"'{p.name}' no es una carpeta."
        items   = list(p.iterdir())
        folders = sorted(i.name for i in items if i.is_dir())
        files   = sorted(i.name for i in items if i.is_file())
        if not items:
            return f"La carpeta '{p.name}' está vacía."
        parts = []
        if folders:
            shown = ', '.join(folders[:5])
            extra = f" y {len(folders)-5} más" if len(folders) > 5 else ""
            parts.append(f"{len(folders)} subcarpeta{'s' if len(folders)>1 else ''}: {shown}{extra}")
        if files:
            shown = ', '.join(files[:5])
            extra = f" y {len(files)-5} más" if len(files) > 5 else ""
            parts.append(f"{len(files)} archivo{'s' if len(files)>1 else ''}: {shown}{extra}")
        return f"En {p.name}: " + ". ".join(parts) + "."
    except Exception as e:
        return f"Error al listar '{path_str}': {e}"


def read_file(path_str: str, max_lines: int = 15) -> str:
    try:
        p = _resolve(path_str)
        if not p.exists():
            return f"No encontré '{path_str}'."
        if p.is_dir():
            return list_directory(path_str)
        if p.suffix.lower() not in _READABLE_EXTENSIONS:
            return f"No sé leer archivos de tipo '{p.suffix}' por voz."
        text  = p.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()
        if len(lines) > max_lines:
            return f"Primeras {max_lines} líneas de {p.name}:\n" + "\n".join(lines[:max_lines]) + f"\n...({len(lines)-max_lines} líneas más)"
        return f"Contenido de {p.name}:\n{text}"
    except Exception as e:
        return f"Error al leer '{path_str}': {e}"


def create_directory(path_str: str) -> str:
    try:
        p = _resolve(path_str)
        if p.exists():
            return f"La carpeta '{p.name}' ya existe."
        p.mkdir(parents=True, exist_ok=True)
        return f"Carpeta '{p.name}' creada en {p.parent.name}."
    except Exception as e:
        return f"Error al crear la carpeta: {e}"


def create_file(path_str: str, content: str = "") -> str:
    try:
        p = _resolve(path_str)
        if p.exists():
            return f"El archivo '{p.name}' ya existe."
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return f"Archivo '{p.name}' creado en {p.parent.name}."
    except Exception as e:
        return f"Error al crear el archivo: {e}"


def copy_file(src_str: str, dst_str: str) -> str:
    try:
        src = _resolve(src_str)
        dst = _resolve(dst_str)
        if not src.exists():
            return f"No encontré '{src.name}'."
        if dst.is_dir():
            dst = dst / src.name
        shutil.copy2(str(src), str(dst))
        return f"'{src.name}' copiado a '{dst.parent.name}'."
    except Exception as e:
        return f"Error al copiar: {e}"


def move_file(src_str: str, dst_str: str) -> str:
    try:
        src = _resolve(src_str)
        dst = _resolve(dst_str)
        if not src.exists():
            return f"No encontré '{src.name}'."
        if dst.is_dir():
            dst = dst / src.name
        shutil.move(str(src), str(dst))
        return f"'{src.name}' movido a '{dst.parent.name}'."
    except Exception as e:
        return f"Error al mover: {e}"
