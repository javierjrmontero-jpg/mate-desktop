#!/usr/bin/env python3
"""
MATE Obsidian Tools
Integración con Obsidian via Local REST API plugin.
https://github.com/coddingtonbear/obsidian-local-rest-api

Requiere:
  - Obsidian abierto con el plugin "Local REST API" habilitado
  - OBSIDIAN_API_KEY en .env (clave generada por el plugin en Settings → Local REST API)
  - OBSIDIAN_API_PORT en .env (default: 27123)
  - OBSIDIAN_VAULT_FOLDER en .env (carpeta raíz donde MATE crea notas, default: MATE)

Instalación del plugin:
  Obsidian → Settings → Community Plugins → Browse → "Local REST API" → Install → Enable
"""

import os
import json
import logging
import urllib.request
import urllib.parse
import urllib.error
import ssl
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Cargar .env
_here = Path(__file__).resolve().parent.parent
load_dotenv(_here / ".env")

_OBSIDIAN_HOST   = os.getenv("OBSIDIAN_HOST", "https://127.0.0.1")
_OBSIDIAN_PORT   = int(os.getenv("OBSIDIAN_API_PORT", "27123"))
_OBSIDIAN_KEY    = os.getenv("OBSIDIAN_API_KEY", "")
_VAULT_FOLDER    = os.getenv("OBSIDIAN_VAULT_FOLDER", "MATE")
_BASE_URL        = f"{_OBSIDIAN_HOST}:{_OBSIDIAN_PORT}"

# SSL sin verificación (plugin usa cert autofirmado por defecto)
_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE


def _check_config() -> str | None:
    if not _OBSIDIAN_KEY:
        return ("No tengo la API key de Obsidian. "
                "Agrega OBSIDIAN_API_KEY en el .env del MATE.")
    return None


def _request(method: str, path: str, body: bytes = b"",
             content_type: str = "text/markdown",
             params: dict | None = None) -> tuple[int, str]:
    """Hace una request HTTP al plugin de Obsidian. Retorna (status, body)."""
    url = f"{_BASE_URL}/{path.lstrip('/')}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    headers = {
        "Authorization": f"Bearer {_OBSIDIAN_KEY}",
        "Content-Type": content_type,
    }
    req = urllib.request.Request(url, data=body or None,
                                  headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, context=_SSL_CTX, timeout=6) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")
    except urllib.error.URLError:
        return 0, "conexión rechazada"
    except Exception as e:
        return -1, str(e)


# ─── API pública ──────────────────────────────────────────────────────────────

def obsidian_status() -> str:
    """Verifica si Obsidian está abierto y el plugin activo."""
    err = _check_config()
    if err:
        return err
    status, body = _request("GET", "/")
    if status == 200:
        try:
            data = json.loads(body)
            v = data.get("versions", {}).get("obsidian", "?")
            return f"Obsidian activo. Versión {v}."
        except Exception:
            return "Obsidian activo."
    if status == 0:
        return "Obsidian no está abierto o el plugin Local REST API no está activo."
    return f"Obsidian respondió con código {status}."


def create_note(title: str, content: str, folder: str | None = None) -> str:
    """Crea una nota nueva en la bóveda de Obsidian."""
    err = _check_config()
    if err:
        return err
    folder = folder or _VAULT_FOLDER
    title_clean = title.strip().replace("/", "-").replace("\\", "-")
    path = f"vault/{folder}/{title_clean}.md"
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    body = (
        f"---\ncreated: {now}\ntags: [mate]\n---\n\n"
        f"# {title_clean}\n\n{content}"
    ).encode("utf-8")
    status, _ = _request("PUT", path, body)
    if status in (200, 204):
        return f"Nota '{title_clean}' creada en Obsidian."
    return f"No pude crear la nota en Obsidian (código {status})."


def append_to_note(title: str, content: str, folder: str | None = None) -> str:
    """Agrega contenido al final de una nota existente (o la crea si no existe)."""
    err = _check_config()
    if err:
        return err
    folder = folder or _VAULT_FOLDER
    title_clean = title.strip().replace("/", "-").replace("\\", "-")
    path = f"vault/{folder}/{title_clean}.md"
    now = datetime.now().strftime("%H:%M")
    body = f"\n\n> [{now}] {content}".encode("utf-8")
    status, _ = _request("POST", path, body)
    if status in (200, 204):
        return f"Agregué eso a la nota '{title_clean}' en Obsidian."
    # Si la nota no existe, crearla
    return create_note(title, content, folder)


def append_to_daily_note(content: str) -> str:
    """Agrega una línea a la nota diaria de hoy en Obsidian."""
    err = _check_config()
    if err:
        return err
    now = datetime.now().strftime("%H:%M")
    body = f"\n- [{now}] {content}".encode("utf-8")
    status, _ = _request("POST", "/periodic/daily/", body)
    if status in (200, 204):
        return "Agregué eso a tu nota diaria en Obsidian."
    # Fallback: crear nota en carpeta MATE con fecha de hoy
    today = datetime.now().strftime("%Y-%m-%d")
    return create_note(today, content)


def log_conversation(user_text: str, mate_reply: str) -> bool:
    """
    Registra un intercambio de voz en la nota diaria.

    Pensado para llamarse en segundo plano tras cada turno que fue al backend.
    Silencioso: no habla ni interrumpe, solo retorna True/False.

    Filtra lo trivial: intercambios muy cortos (saludos, confirmaciones) no
    aportan como contexto posterior y solo ensucian la nota.
    """
    if not _OBSIDIAN_KEY:
        return False
    if not user_text or not mate_reply:
        return False
    # Umbral: respuestas breves suelen ser confirmaciones o saludos
    if len(mate_reply.strip()) < 80 and len(user_text.split()) < 6:
        return False

    now = datetime.now().strftime("%H:%M")
    clean_reply = mate_reply.strip().replace("\n", " ")
    entry = (
        f"\n\n**{now} — Vos:** {user_text.strip()}"
        f"\n**MATE:** {clean_reply}"
    )
    status, _ = _request("POST", "/periodic/daily/", entry.encode("utf-8"))
    if status in (200, 204):
        return True
    # Fallback si no hay plugin de notas periódicas: nota con la fecha de hoy
    today = datetime.now().strftime("%Y-%m-%d")
    folder = _VAULT_FOLDER
    path = f"vault/{folder}/{today}.md"
    status, _ = _request("POST", path, entry.encode("utf-8"))
    if status in (200, 204):
        return True
    create_note(today, entry.lstrip("\n"))
    return True


def read_note(title: str, folder: str | None = None) -> str:
    """Lee una nota y retorna un preview legible por TTS."""
    err = _check_config()
    if err:
        return err
    folder = folder or _VAULT_FOLDER
    title_clean = title.strip().replace("/", "-").replace("\\", "-")
    path = f"vault/{folder}/{title_clean}.md"
    status, body = _request("GET", path)
    if status == 200:
        # Strip YAML frontmatter
        text = body
        if text.startswith("---"):
            parts = text.split("---", 2)
            text = parts[2].strip() if len(parts) >= 3 else text
        # Eliminar encabezados markdown y líneas vacías
        lines = [l.lstrip("#").strip() for l in text.splitlines() if l.strip()]
        preview = " ".join(lines[:6])
        if len(preview) > 400:
            preview = preview[:400] + "..."
        return f"Nota '{title_clean}': {preview}"
    if status == 404:
        return f"No encontré una nota llamada '{title_clean}' en Obsidian."
    return f"Error leyendo la nota (código {status})."


def search_notes(query: str) -> str:
    """Busca notas en la bóveda de Obsidian."""
    err = _check_config()
    if err:
        return err
    body = json.dumps({"query": query}).encode("utf-8")
    status, resp = _request("POST", "/search/simple/",
                             body, content_type="application/json",
                             params={"contextLength": "80"})
    if status == 200:
        try:
            results = json.loads(resp)
        except Exception:
            results = []
        if not results:
            return f"No encontré notas sobre '{query}' en Obsidian."
        lines = []
        for item in results[:5]:
            fname = item.get("filename", "").replace(".md", "").split("/")[-1]
            lines.append(f"- {fname}")
        return (f"Encontré {len(results)} nota(s) sobre '{query}': "
                + ", ".join(l.lstrip("- ") for l in lines) + ".")
    return f"Error buscando en Obsidian (código {status})."


def list_notes(folder: str | None = None) -> str:
    """Lista las notas de una carpeta de la bóveda."""
    err = _check_config()
    if err:
        return err
    folder = folder or _VAULT_FOLDER
    path = f"vault/{folder}/"
    status, resp = _request("GET", path)
    if status == 200:
        try:
            data = json.loads(resp)
            files = [f for f in data.get("files", []) if f.endswith(".md")]
        except Exception:
            files = []
        if not files:
            return f"No hay notas en la carpeta '{folder}' de Obsidian."
        names = [f.replace(".md", "").split("/")[-1] for f in files[:8]]
        return f"Notas en '{folder}': {', '.join(names)}."
    return f"Error listando notas (código {status})."


def get_daily_note() -> str:
    """Lee la nota diaria de hoy."""
    err = _check_config()
    if err:
        return err
    status, body = _request("GET", "/periodic/daily/")
    if status == 200:
        text = body
        if text.startswith("---"):
            parts = text.split("---", 2)
            text = parts[2].strip() if len(parts) >= 3 else text
        lines = [l.lstrip("#").strip() for l in text.splitlines() if l.strip()]
        if not lines:
            return "Tu nota diaria de hoy está vacía."
        preview = " ".join(lines[:8])
        if len(preview) > 500:
            preview = preview[:500] + "..."
        return f"Nota de hoy: {preview}"
    if status == 404:
        return "No hay nota diaria para hoy. Obsidian no la creó aún."
    return f"Error leyendo nota diaria (código {status})."


def ingest_note_to_memory(title: str, folder: str | None = None) -> str:
    """Lee una nota de Obsidian y la registra en la memoria local de MATE."""
    err = _check_config()
    if err:
        return err
    folder = folder or _VAULT_FOLDER
    title_clean = title.strip().replace("/", "-").replace("\\", "-")
    path = f"vault/{folder}/{title_clean}.md"
    status, body = _request("GET", path)
    if status != 200:
        return f"No pude leer la nota '{title_clean}' para ingresarla."
    # Extraer texto
    text = body
    if text.startswith("---"):
        parts = text.split("---", 2)
        text = parts[2].strip() if len(parts) >= 3 else text
    summary = " ".join(text.split()[:80])  # ~80 palabras
    # Guardar en memoria de MATE
    try:
        from tools.memory_tools import remember
        remember(f"obsidian:{title_clean}", summary)
        return f"Ingresé la nota '{title_clean}' a la memoria de MATE."
    except Exception as e:
        return f"Leí la nota pero no pude guardarla en memoria: {e}"
