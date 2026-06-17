#!/usr/bin/env python3
"""
MATE Spotify Tools — F10-1
Control de Spotify por voz.
- Sin credenciales: usa teclas multimedia (play/pause/next/prev).
- Con SPOTIFY_CLIENT_ID + SPOTIFY_CLIENT_SECRET: búsqueda y reproducción por nombre.
"""

import os
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_CLIENT_ID     = os.environ.get("SPOTIFY_CLIENT_ID", "")
_CLIENT_SECRET = os.environ.get("SPOTIFY_CLIENT_SECRET", "")
_REDIRECT_URI  = "http://127.0.0.1:8888/callback"
_SCOPE         = "user-read-playback-state user-modify-playback-state user-read-currently-playing"
# Token cacheado por mate_spotify_auth.py — nunca pide login desde el orbe
_CACHE_PATH    = str(Path(__file__).parent.parent / ".spotify_cache")

_sp = None  # cliente spotipy — lazy init


def _get_spotipy():
    global _sp
    if _sp:
        return _sp
    if not _CLIENT_ID or not _CLIENT_SECRET:
        return None
    if not Path(_CACHE_PATH).exists():
        logger.warning("Spotify: no hay token cacheado. Corré mate_spotify_auth.py primero.")
        return None
    try:
        import spotipy
        from spotipy.oauth2 import SpotifyOAuth
        _sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
            client_id=_CLIENT_ID,
            client_secret=_CLIENT_SECRET,
            redirect_uri=_REDIRECT_URI,
            scope=_SCOPE,
            open_browser=False,   # nunca abrir browser desde el orbe
            cache_path=_CACHE_PATH,
        ))
        return _sp
    except Exception as e:
        logger.warning(f"Spotipy no disponible: {e}")
        return None


def _media_key(key: str) -> None:
    try:
        import pyautogui
        pyautogui.press(key)
    except Exception as e:
        logger.error(f"media_key {key}: {e}")


def play_pause() -> str:
    sp = _get_spotipy()
    if sp:
        try:
            pb = sp.current_playback()
            if pb and pb.get("is_playing"):
                sp.pause_playback()
                return "Música pausada."
            else:
                sp.start_playback()
                return "Reproduciendo."
        except Exception:
            pass
    _media_key("playpause")
    return "Play/Pause enviado."


def next_track() -> str:
    sp = _get_spotipy()
    if sp:
        try:
            sp.next_track()
            return "Siguiente canción."
        except Exception:
            pass
    _media_key("nexttrack")
    return "Siguiente canción."


def previous_track() -> str:
    sp = _get_spotipy()
    if sp:
        try:
            sp.previous_track()
            return "Canción anterior."
        except Exception:
            pass
    _media_key("prevtrack")
    return "Canción anterior."


def stop_playback() -> str:
    sp = _get_spotipy()
    if sp:
        try:
            sp.pause_playback()
            return "Spotify pausado."
        except Exception:
            pass
    _media_key("playpause")
    return "Stop enviado."


def now_playing() -> str:
    sp = _get_spotipy()
    if not sp:
        return "Para consultar Spotify corré mate_spotify_auth.py primero."
    try:
        pb = sp.current_playback()
        if pb and pb.get("item"):
            item    = pb["item"]
            track   = item["name"]
            artists = ", ".join(a["name"] for a in item["artists"])
            album   = item["album"]["name"]
            status  = "reproduciendo" if pb["is_playing"] else "pausado"
            return f"Está {status}: {track} de {artists}, del álbum {album}."
        return "No hay nada reproduciéndose en Spotify."
    except Exception as e:
        return f"No pude consultar Spotify: {e}"


def search_and_play(query: str) -> str:
    sp = _get_spotipy()
    if not sp:
        return (
            "Para buscar canciones en Spotify corré mate_spotify_auth.py primero "
            "y configurá SPOTIFY_CLIENT_ID y SPOTIFY_CLIENT_SECRET."
        )
    try:
        results = sp.search(q=query, type="track", limit=1)
        tracks  = results.get("tracks", {}).get("items", [])
        if not tracks:
            return f"No encontré '{query}' en Spotify."
        track   = tracks[0]
        name    = track["name"]
        artists = ", ".join(a["name"] for a in track["artists"])
        sp.start_playback(uris=[track["uri"]])
        return f"Reproduciendo {name} de {artists}."
    except Exception as e:
        return f"No pude reproducir '{query}': {e}"
