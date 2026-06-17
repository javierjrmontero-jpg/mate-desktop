#!/usr/bin/env python3
"""
MATE Calendar Auth — PRO
Script standalone para autorizar Google Calendar OAuth.
Ejecutar UNA VEZ en la PC que tenga el cliente secrets.

Uso:
  1. Crear proyecto en https://console.cloud.google.com
  2. Habilitar Google Calendar API
  3. Crear credenciales OAuth 2.0 (tipo: Desktop app)
  4. Descargar client_secret.json
  5. En el .env: GOOGLE_CREDENTIALS_PATH=C:\\ruta\\a\\client_secret.json
  6. Ejecutar: python mate_calendar_auth.py
  7. Autorizar en el navegador que se abre
  8. El token queda guardado en .gcal_token.json junto al .env

Una vez autorizado, el token se renueva automáticamente — no hace falta volver a correr esto.
"""

import os
import sys
from pathlib import Path

# Determinar directorio de trabajo (igual que en frozen)
_BASE = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent

# Cargar .env local
_env_file = _BASE / ".env"
if _env_file.exists():
    for line in _env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

_GCAL_CREDS = os.environ.get("GOOGLE_CREDENTIALS_PATH", "")
_TOKEN_PATH = str(_BASE / ".gcal_token.json")
_TZ         = os.environ.get("MATE_TIMEZONE", "America/Argentina/Buenos_Aires")

SCOPES = ["https://www.googleapis.com/auth/calendar"]


def main():
    print("=" * 60)
    print("  MATE — Google Calendar Auth")
    print("=" * 60)

    if not _GCAL_CREDS:
        print("\nERROR: GOOGLE_CREDENTIALS_PATH no está definido en el .env.")
        print("  Pasos:")
        print("  1. Ir a https://console.cloud.google.com")
        print("  2. Crear proyecto → Habilitar 'Google Calendar API'")
        print("  3. Credenciales → OAuth 2.0 → Desktop app → Descargar JSON")
        print("  4. Agregar al .env: GOOGLE_CREDENTIALS_PATH=C:\\ruta\\client_secret.json")
        print("  5. Volver a ejecutar este script")
        input("\nPresioná Enter para salir...")
        return

    if not os.path.exists(_GCAL_CREDS):
        print(f"\nERROR: No se encontró el archivo: {_GCAL_CREDS}")
        input("\nPresioná Enter para salir...")
        return

    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
    except ImportError:
        print("\nERROR: Faltan dependencias. Ejecutá:")
        print("  pip install google-auth-oauthlib google-auth-httplib2 google-api-python-client")
        input("\nPresioná Enter para salir...")
        return

    creds = None
    if os.path.exists(_TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(_TOKEN_PATH, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("Renovando token existente...")
            creds.refresh(Request())
        else:
            print("\nAbriendo navegador para autorizar Google Calendar...")
            print("(Si no se abre, copiá la URL que aparece en la consola)\n")
            flow  = InstalledAppFlow.from_client_secrets_file(_GCAL_CREDS, SCOPES)
            creds = flow.run_local_server(port=0)

        Path(_TOKEN_PATH).write_text(creds.to_json(), encoding="utf-8")
        print(f"\nToken guardado en: {_TOKEN_PATH}")

    # Verificar acceso
    try:
        service = build("calendar", "v3", credentials=creds)
        cal     = service.calendars().get(calendarId="primary").execute()
        print(f"\n✓ Autorizado correctamente.")
        print(f"  Calendario: {cal.get('summary', 'primary')}")
        print(f"  Zona horaria detectada: {cal.get('timeZone', _TZ)}")
        print(f"\n  MATE ahora puede crear y leer eventos en tu Google Calendar.")
    except Exception as e:
        print(f"\nERROR verificando acceso: {e}")

    input("\nPresioná Enter para salir...")


if __name__ == "__main__":
    main()
