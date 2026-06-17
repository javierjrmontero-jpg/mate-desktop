#!/usr/bin/env python3
"""
mate_spotify_auth.py — Ejecutar UNA VEZ para autenticar MATE con Spotify.

Pasos:
  1. Configurar variables de entorno:
       $env:SPOTIFY_CLIENT_ID     = "tu_client_id"
       $env:SPOTIFY_CLIENT_SECRET = "tu_client_secret"
  2. Correr este script:
       python mate_spotify_auth.py
  3. Se abre el navegador → iniciá sesión → ingresá el código 2FA si aplica.
  4. El token queda guardado en .spotify_cache.
  5. MATE usa el token automáticamente desde ese momento. No vuelve a pedir login.

Requisito en Spotify Developer Dashboard:
  - Redirect URI: http://localhost:8888/callback
"""

import os
import sys
from pathlib import Path

CLIENT_ID     = os.environ.get("SPOTIFY_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("SPOTIFY_CLIENT_SECRET", "")
REDIRECT_URI  = "http://127.0.0.1:8888/callback"
SCOPE         = "user-read-playback-state user-modify-playback-state user-read-currently-playing"
CACHE_PATH    = str(Path(__file__).parent / ".spotify_cache")

if not CLIENT_ID or not CLIENT_SECRET:
    print("❌  Falta configurar las variables de entorno:")
    print("      $env:SPOTIFY_CLIENT_ID     = 'tu_client_id'")
    print("      $env:SPOTIFY_CLIENT_SECRET = 'tu_client_secret'")
    sys.exit(1)

try:
    import spotipy
    from spotipy.oauth2 import SpotifyOAuth
except ImportError:
    print("❌  Instalá spotipy primero:")
    print("      pip install spotipy")
    sys.exit(1)

print("🎵  Autenticando MATE con Spotify...")
print("    Se abrirá el navegador.")
print("    Iniciá sesión en Spotify (ingresá el código 2FA si te lo pide).")
print(f"    Token se guardará en: {CACHE_PATH}\n")

sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET,
    redirect_uri=REDIRECT_URI,
    scope=SCOPE,
    open_browser=True,
    cache_path=CACHE_PATH,
))

try:
    user = sp.current_user()
    print(f"\n✅  Autenticado como: {user['display_name']} ({user['id']})")
    print(f"    Token guardado en {CACHE_PATH}")
    print("    MATE puede controlar Spotify a partir de ahora. No volvés a ver este paso.")
except Exception as e:
    print(f"\n❌  Error al verificar autenticación: {e}")
    sys.exit(1)
