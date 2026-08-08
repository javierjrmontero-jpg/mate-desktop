#!/usr/bin/env python3
"""
MATE Graphiti Tools — Orbe Local
Consulta el grafo de memoria temporal de MATE via el backend API.
El procesamiento pesado (Neo4j + Graphiti) corre en la VM; el orbe
solo hace requests HTTP a los endpoints /api/v1/memory/graph*.

Requiere:
  - Backend MATE con Neo4j y graphiti-core corriendo (Bloque B)
  - .mate_token válido (mismo que usa el orbe para chat)
"""

import os
import json
import logging
import urllib.request
import urllib.parse
import urllib.error
from pathlib import Path
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Cargar .env
_here = Path(__file__).resolve().parent.parent
load_dotenv(_here / ".env")

_MATE_URL = os.getenv("MATE_URL", "https://molmont.duckdns.org")

# Token JWT del orbe (mismo archivo que usa _call_mate en mate_orb.py)
_TOKEN_FILE = _here / ".mate_token"


def _get_token() -> str:
    try:
        return _TOKEN_FILE.read_text().strip()
    except Exception:
        return ""


def _api_get(path: str, params: dict | None = None) -> tuple[int, dict]:
    """GET al backend de MATE con autenticación JWT."""
    token = _get_token()
    if not token:
        return 401, {"error": "No hay token de sesión. Iniciá sesión con MATE primero."}
    url = f"{_MATE_URL}/api/v1{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    import ssl
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=8) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, {"error": e.read().decode("utf-8", errors="replace")}
    except urllib.error.URLError as e:
        return 0, {"error": f"No pude conectar al backend: {e.reason}"}
    except Exception as e:
        return -1, {"error": str(e)}


# ─── API pública ──────────────────────────────────────────────────────────────

def graphiti_status() -> str:
    """Verifica si el grafo de memoria Graphiti está disponible."""
    status, data = _api_get("/memory/graph/status")
    if status != 200:
        return f"No pude verificar el estado del grafo ({status})."
    if data.get("available"):
        return "El grafo de memoria Graphiti está activo en el backend."
    return "El grafo de memoria Graphiti no está disponible. Neo4j puede estar iniciando."


def query_graph(query: str = "", limit: int = 5) -> str:
    """Consulta el grafo de memoria con una pregunta."""
    status, data = _api_get("/memory/graph", params={"q": query, "limit": limit})
    if status == 401:
        return "No estoy autenticado en el backend. Reiniciá MATE para iniciar sesión."
    if status != 200 or data.get("error"):
        return f"Error consultando el grafo: {data.get('error', status)}."
    if not data.get("available"):
        return "El grafo Graphiti no está disponible ahora mismo."
    facts = data.get("facts", [])
    if not facts:
        return f"No encontré nada sobre '{query}' en el grafo de memoria."
    lines = [f"- {f['fact']}" for f in facts]
    return f"Del grafo de memoria:\n" + "\n".join(lines)


def what_do_you_know_about(topic: str) -> str:
    """Consulta el grafo sobre un tema específico."""
    return query_graph(topic, limit=5)


def recent_memory(limit: int = 5) -> str:
    """Recupera los hechos más recientes del grafo."""
    status, data = _api_get("/memory/graph", params={
        "q": "usuario reciente conversación",
        "limit": limit
    })
    if status != 200 or not data.get("available"):
        return "El grafo no está disponible ahora mismo."
    facts = data.get("facts", [])
    if not facts:
        return "El grafo de memoria está vacío todavía."
    lines = [f"- {f['fact']}" for f in facts]
    return f"Tengo {len(facts)} hecho(s) en el grafo:\n" + "\n".join(lines)
