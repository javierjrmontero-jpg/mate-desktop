#!/usr/bin/env python3
"""
Guarda el token de MATE en .mate_token para que mate_orb.py lo use.
Uso: python mate_login.py
"""
import os, getpass, json
import urllib.request, urllib.error, ssl

MATE_URL   = os.getenv("MATE_URL", "https://mate.local")
TOKEN_FILE = os.path.join(os.path.dirname(__file__), ".mate_token")

def login(email: str, password: str) -> str:
    payload = json.dumps({"email": email, "password": password}).encode()
    ctx = ssl._create_unverified_context()
    req = urllib.request.Request(
        f"{MATE_URL}/api/v1/auth/login",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, context=ctx, timeout=15) as r:
        data = json.loads(r.read())
    return data["token"]

def main():
    print(f"=== Login MATE ({MATE_URL}) ===")
    email    = input("Email: ").strip()
    password = getpass.getpass("Contraseña: ")
    try:
        token = login(email, password)
        with open(TOKEN_FILE, "w") as f:
            f.write(token)
        print(f"✓ Token guardado en {TOKEN_FILE}")
        print(f"  Token: {token[:40]}…")
    except Exception as e:
        print(f"✗ Error: {e}")

if __name__ == "__main__":
    main()
