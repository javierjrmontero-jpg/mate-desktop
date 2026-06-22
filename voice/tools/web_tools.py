#!/usr/bin/env python3
"""
MATE Web Tools — F9/F10
Clima, noticias, búsqueda web, YouTube y visión de pantalla.
Todas las funciones retornan strings listos para TTS.
"""

import logging
import os
import re
from urllib.parse import quote_plus

logger = logging.getLogger(__name__)

# ─── WMO weather codes → descripción en español ──────────────────────────────

_WMO = {
    0: "cielo despejado",
    1: "mayormente despejado",
    2: "parcialmente nublado",
    3: "nublado",
    45: "neblina",
    48: "neblina con escarcha",
    51: "llovizna leve",
    53: "llovizna moderada",
    55: "llovizna intensa",
    61: "lluvia leve",
    63: "lluvia moderada",
    65: "lluvia intensa",
    71: "nevada leve",
    73: "nevada moderada",
    75: "nevada intensa",
    77: "granizo fino",
    80: "chaparrones leves",
    81: "chaparrones moderados",
    82: "chaparrones intensos",
    85: "nieve con chaparrones",
    86: "nieve intensa con chaparrones",
    95: "tormenta eléctrica",
    96: "tormenta con granizo",
    99: "tormenta con granizo intenso",
}


# ─── CLIMA ────────────────────────────────────────────────────────────────────

def get_weather() -> str:
    """Clima actual usando ip-api.com para ubicación y Open-Meteo para datos."""
    try:
        import requests

        # Ubicación por IP (fallback: Buenos Aires)
        try:
            loc = requests.get("https://ipapi.co/json/", timeout=5).json()
            lat   = loc["lat"]
            lon   = loc["lon"]
            city  = loc.get("city", "tu ciudad")
        except Exception:
            lat, lon, city = -34.6037, -58.3816, "Buenos Aires"

        url = (
            f"https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat}&longitude={lon}"
            f"&current=temperature_2m,apparent_temperature,weathercode,"
            f"windspeed_10m,relativehumidity_2m"
            f"&daily=temperature_2m_max,temperature_2m_min"
            f"&timezone=auto&forecast_days=1"
        )
        data  = requests.get(url, timeout=10).json()
        curr  = data["current"]
        daily = data.get("daily", {})

        temp    = round(curr["temperature_2m"])
        feels   = round(curr["apparent_temperature"])
        code    = int(curr["weathercode"])
        wind    = round(curr["windspeed_10m"])
        hum     = curr["relativehumidity_2m"]
        cond    = _WMO.get(code, "condiciones variables")

        parts = [f"En {city} el cielo está {cond}.",
                 f"Temperatura {temp}°C, sensación térmica {feels}°C.",
                 f"Humedad {hum}%, viento a {wind} km/h."]

        max_t = daily.get("temperature_2m_max", [None])[0]
        min_t = daily.get("temperature_2m_min", [None])[0]
        if max_t is not None and min_t is not None:
            parts.append(f"Máxima {round(max_t)}°C, mínima {round(min_t)}°C.")

        return " ".join(parts)

    except Exception as e:
        logger.error(f"get_weather: {e}")
        return "No pude obtener el clima en este momento."


# ─── NOTICIAS ─────────────────────────────────────────────────────────────────

_NEWS_FEEDS = [
    ("Infobae",   "https://www.infobae.com/feeds/rss/"),
    ("La Nación", "https://www.lanacion.com.ar/arc/outboundfeeds/rss/"),
    ("BBC Mundo",  "https://feeds.bbci.co.uk/mundo/rss.xml"),
]


def get_news(n: int = 5) -> str:
    """Titulares más recientes de fuentes en español (RSS, sin API key)."""
    try:
        import feedparser

        for source_name, url in _NEWS_FEEDS:
            try:
                feed = feedparser.parse(url)
                if feed.entries:
                    headlines = [e.title.strip() for e in feed.entries[:n] if e.get("title")]
                    if headlines:
                        items = ". ".join(f"{i+1}: {h}" for i, h in enumerate(headlines))
                        return f"Los {len(headlines)} titulares más recientes de {source_name}: {items}."
            except Exception:
                continue

        return "No pude obtener noticias en este momento."

    except ImportError:
        return "Para noticias necesitás instalar feedparser: pip install feedparser."
    except Exception as e:
        logger.error(f"get_news: {e}")
        return "No pude obtener noticias en este momento."


# ─── BÚSQUEDA WEB ─────────────────────────────────────────────────────────────

def search_web(query: str) -> str:
    """
    Busca en DuckDuckGo y retorna un resumen hablable.
    Intenta DuckDuckGo Instant Answer primero; cae en duckduckgo_search si es necesario.
    """
    query = query.strip()
    if not query:
        return "¿Qué querés que busque?"

    try:
        import requests

        # 1. DuckDuckGo Instant Answer API (sin pip extra, funciona para hechos concretos)
        ia_url = f"https://api.duckduckgo.com/?q={quote_plus(query)}&format=json&no_redirect=1&no_html=1&skip_disambig=1"
        data   = requests.get(ia_url, timeout=8).json()

        abstract = data.get("AbstractText", "").strip()
        if abstract:
            if len(abstract) > 400:
                abstract = abstract[:400].rsplit(" ", 1)[0] + "."
            source = data.get("AbstractSource", "")
            return (f"Según {source}: {abstract}" if source else abstract)

        answer = data.get("Answer", "").strip()
        if answer:
            return answer

        # 2. Fallback: duckduckgo_search (resultados de texto completos)
        try:
            from duckduckgo_search import DDGS
            results = list(DDGS().text(query, max_results=3))
            if results:
                # Tomar el snippet más largo entre los primeros 3
                best = max(results, key=lambda r: len(r.get("body", "")))
                body = best.get("body", "").strip()
                if body:
                    if len(body) > 350:
                        body = body[:350].rsplit(" ", 1)[0] + "."
                    title = best.get("title", "")
                    return (f"{title}: {body}" if title else body)
        except ImportError:
            pass  # duckduckgo_search no está instalado — no es crítico

        return f"No encontré resultados directos para '{query}'. Podés buscar en el navegador."

    except Exception as e:
        logger.error(f"search_web: {e}")
        return f"Error al buscar '{query}'."


# ─── YOUTUBE ──────────────────────────────────────────────────────────────────

def open_youtube(query: str = "") -> str:
    """Abre YouTube en el navegador default, con o sin búsqueda."""
    import webbrowser
    query = query.strip()
    if not query:
        webbrowser.open("https://www.youtube.com")
        return "Abrí YouTube."
    url = f"https://www.youtube.com/results?search_query={quote_plus(query)}"
    webbrowser.open(url)
    return f"Buscando '{query}' en YouTube."


# ─── VISIÓN DE PANTALLA ───────────────────────────────────────────────────────

def describe_screen() -> str:
    """
    Captura la pantalla y pide a Claude Haiku que la describa.
    Requiere ANTHROPIC_API_KEY como variable de entorno.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return (
            "Para describir la pantalla necesito la variable "
            "ANTHROPIC_API_KEY configurada."
        )

    # 1. Captura
    try:
        import pyautogui
        import io
        import base64
        from PIL import Image

        img = pyautogui.screenshot()
        img.thumbnail((1280, 720), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode()
    except Exception as e:
        return f"No pude capturar la pantalla: {e}"

    # 2. Descripción via Claude Haiku
    try:
        import requests as _req
        resp = _req.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-haiku-4-5-20251001",
                "max_tokens": 256,
                "messages": [{
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": b64,
                            },
                        },
                        {
                            "type": "text",
                            "text": (
                                "Describí brevemente qué hay en esta pantalla, en español. "
                                "Sé conciso, máximo 3 oraciones."
                            ),
                        },
                    ],
                }],
            },
            timeout=20,
        )
        resp.raise_for_status()
        return resp.json()["content"][0]["text"]
    except Exception as e:
        logger.error(f"describe_screen: {e}")
        return f"No pude describir la pantalla: {e}"
