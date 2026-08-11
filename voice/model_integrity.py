#!/usr/bin/env python3
"""
MED-7: Verificación de integridad del modelo Whisper.
Calcula SHA256 de los archivos del modelo en el primer uso y lo almacena.
En usos posteriores verifica que los archivos no hayan cambiado.
"""
import sys
import json
import hashlib
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_DATA_DIR   = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent
_HASH_FILE  = _DATA_DIR / ".mate_model_hashes.json"
# Archivos clave del modelo Whisper (faster-whisper usa CTranslate2 format)
_MODEL_FILES = ["model.bin", "config.json", "tokenizer.json", "vocabulary.txt"]


def _whisper_model_dir(model_size: str = "medium") -> Path | None:
    """Localiza el directorio del modelo Whisper del tamaño indicado."""
    try:
        import os
        cache = Path(os.environ.get("HF_HOME", Path.home() / ".cache" / "huggingface"))
        candidates = [
            cache / "hub" / f"models--Systran--faster-whisper-{model_size}" / "snapshots",
            cache / "hub" / f"models--guillaumekln--faster-whisper-{model_size}" / "snapshots",
        ]
        for base in candidates:
            if base.exists():
                snaps = list(base.iterdir())
                if snaps:
                    return snaps[-1]
    except Exception:
        pass
    return None


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(65536), b""):
            h.update(block)
    return h.hexdigest()


def verify_or_register(model_size: str = "medium") -> bool:
    """
    Primera llamada: calcula y guarda los hashes.
    Llamadas posteriores: verifica que coincidan.
    Retorna True si todo OK, False si hay discrepancia (posible tampering).
    Los hashes se guardan por tamaño de modelo, así cambiar de modelo no
    dispara un falso positivo de tampering.
    """
    model_dir = _whisper_model_dir(model_size)
    if model_dir is None:
        logger.debug("MED-7: directorio del modelo no encontrado, saltando verificación.")
        return True

    current: dict[str, str] = {}
    for name in _MODEL_FILES:
        p = model_dir / name
        if p.exists():
            current[name] = _sha256(p)

    if not current:
        return True

    if _HASH_FILE.exists():
        try:
            all_stored = json.loads(_HASH_FILE.read_text(encoding="utf-8"))
            stored = all_stored.get(model_size, {})
            if not stored:                      # modelo nuevo: registrar
                all_stored[model_size] = current
                _HASH_FILE.write_text(json.dumps(all_stored, indent=2), encoding="utf-8")
                logger.info(f"MED-7: hashes registrados para '{model_size}'.")
                return True
            mismatches = [k for k in stored if k in current and current[k] != stored[k]]
            if mismatches:
                logger.error(f"MED-7: integridad del modelo FALLIDA para: {mismatches}")
                return False
            logger.debug(f"MED-7: integridad del modelo '{model_size}' OK.")
            return True
        except Exception:
            pass

    # Primera vez: guardar hashes
    _HASH_FILE.write_text(json.dumps({model_size: current}, indent=2), encoding="utf-8")
    logger.info(f"MED-7: hashes de '{model_size}' registrados ({len(current)} archivos).")
    return True
