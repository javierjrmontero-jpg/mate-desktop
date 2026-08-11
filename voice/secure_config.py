#!/usr/bin/env python3
"""
MATE Secure Config — cifrado DPAPI para credenciales.
Windows DPAPI: solo el mismo usuario/PC puede descifrar.
"""
import os
import sys
import json
from pathlib import Path


def _data_dir() -> Path:
    return Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent


_CONFIG_FILE = _data_dir() / ".mate_config.bin"
_TOKEN_FILE  = _data_dir() / ".mate_token.bin"


def _encrypt(data: bytes) -> bytes:
    import win32crypt
    return win32crypt.CryptProtectData(data, "MATE", None, None, None, 0)


def _decrypt(data: bytes) -> bytes:
    import win32crypt
    _, plaintext = win32crypt.CryptUnprotectData(data, None, None, None, 0)
    return plaintext


# ─── Config ──────────────────────────────────────────────────────────────────

def save_config(cfg: dict):
    """Cifra y guarda el dict de configuración en .mate_config.bin."""
    raw = json.dumps(cfg, ensure_ascii=False).encode("utf-8")
    _CONFIG_FILE.write_bytes(_encrypt(raw))


def load_config() -> dict | None:
    """Descifra y retorna la configuración. None si no existe o falla."""
    if not _CONFIG_FILE.exists():
        return None
    try:
        return json.loads(_decrypt(_CONFIG_FILE.read_bytes()).decode("utf-8"))
    except Exception:
        return None


def inject_config_into_env() -> bool:
    """Inyecta la configuración cifrada en os.environ (setdefault). Retorna True si hubo config."""
    cfg = load_config()
    if cfg:
        for k, v in cfg.items():
            if v:
                os.environ.setdefault(k, str(v))
    return cfg is not None


def config_exists() -> bool:
    return _CONFIG_FILE.exists()


# ─── Token JWT ───────────────────────────────────────────────────────────────

def save_token(token: str):
    """Guarda el token JWT cifrado con DPAPI."""
    _TOKEN_FILE.write_bytes(_encrypt(token.encode("utf-8")))


def load_token() -> str | None:
    """Carga y descifra el token JWT. None si no existe o falla."""
    if _TOKEN_FILE.exists():
        try:
            return _decrypt(_TOKEN_FILE.read_bytes()).decode("utf-8")
        except Exception:
            pass
    # fallback: .mate_token en texto plano (instalaciones previas)
    plain = _data_dir() / ".mate_token"
    if plain.exists():
        try:
            token = plain.read_text(encoding="utf-8").strip()
            if token:
                # migrar a formato cifrado
                save_token(token)
                plain.unlink(missing_ok=True)
                return token
        except Exception:
            pass
    return None
