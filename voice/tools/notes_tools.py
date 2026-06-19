#!/usr/bin/env python3
"""
MATE Notes Tools — F11-1/F11-3
Base de conocimiento personal: notas y metas locales en JSON.
Sin dependencias externas.
"""

import sys
import json
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

_DATA_DIR = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent.parent
_NOTES_FILE = _DATA_DIR / ".mate_notes.json"


def _load() -> list[dict]:
    if not _NOTES_FILE.exists():
        return []
    try:
        return json.loads(_NOTES_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save(notes: list[dict]) -> None:
    _NOTES_FILE.write_text(
        json.dumps(notes, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# ─── NOTAS ────────────────────────────────────────────────────────────────────

def save_note(content: str, tag: str = "nota") -> str:
    notes = _load()
    now   = datetime.now()
    title = content[:50].strip() + ("…" if len(content) > 50 else "")
    note  = {
        "id":      len(notes) + 1,
        "tag":     tag,
        "title":   title,
        "content": content,
        "created": now.strftime("%Y-%m-%d %H:%M"),
    }
    notes.append(note)
    _save(notes)
    return f"Nota guardada: '{title}'."


def list_notes(n: int = 5, tag: str = "") -> str:
    notes = _load()
    if tag:
        notes = [x for x in notes if x.get("tag") == tag]
    if not notes:
        label = "metas" if tag == "meta" else "notas"
        return f"No tenés {label} guardadas."
    recent = notes[-n:][::-1]
    label  = "meta" if tag == "meta" else "nota"
    items  = ". ".join(
        f"{i+1}: {n['title']} ({n['created'][:10]})"
        for i, n in enumerate(recent)
    )
    total = len(notes)
    return f"Tenés {total} {label}{'s' if total > 1 else ''}. Las más recientes: {items}."


def search_notes(query: str, tag: str = "") -> str:
    notes = _load()
    if tag:
        notes = [x for x in notes if x.get("tag") == tag]
    if not notes:
        return "No tenés notas guardadas."
    q       = query.lower()
    matches = [n for n in notes if q in n["title"].lower() or q in n["content"].lower()]
    if not matches:
        return f"No encontré notas sobre '{query}'."
    items = ". ".join(
        f"{n['title']}: {n['content'][:80]}{'…' if len(n['content']) > 80 else ''}"
        for n in matches[:3]
    )
    return f"Encontré {len(matches)} nota{'s' if len(matches) > 1 else ''} sobre '{query}': {items}."


def read_note(query: str) -> str:
    notes = _load()
    if not notes:
        return "No tenés notas guardadas."
    q = query.lower()
    for n in reversed(notes):
        if q in n["title"].lower() or q in n["content"].lower():
            return f"{n['title']} ({n['created'][:10]}): {n['content']}"
    return f"No encontré una nota sobre '{query}'."


def delete_note(query: str) -> str:
    notes  = _load()
    q      = query.lower()
    before = len(notes)
    notes  = [n for n in notes if q not in n["title"].lower()]
    if len(notes) == before:
        return f"No encontré una nota llamada '{query}'."
    _save(notes)
    return f"Nota '{query}' eliminada."


# ─── METAS ────────────────────────────────────────────────────────────────────

def save_goal(content: str) -> str:
    return save_note(content, tag="meta")


def list_goals() -> str:
    return list_notes(tag="meta")


def search_goals(query: str) -> str:
    return search_notes(query, tag="meta")
