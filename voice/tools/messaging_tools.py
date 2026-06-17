#!/usr/bin/env python3
"""
MATE Messaging Tools — PRO
Envío de mensajes por Telegram y WhatsApp por voz.

Configuración en .env:
  TELEGRAM_BOT_TOKEN   — token del bot (BotFather)
  TELEGRAM_CHAT_ID     — ID de tu chat con el bot (obtener con /getUpdates)
  WHATSAPP_DEFAULT_NUMBER — número por defecto formato internacional sin + (ej: 541161234567)
"""

import os
import logging

logger = logging.getLogger(__name__)

_TELEGRAM_TOKEN   = os.environ.get("TELEGRAM_BOT_TOKEN", "")
_TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
_WA_DEFAULT_NUM   = os.environ.get("WHATSAPP_DEFAULT_NUMBER", "")


# ─── Telegram ────────────────────────────────────────────────────────────────

def send_telegram(message: str, chat_id: str = "") -> str:
    """Envía un mensaje de Telegram al chat configurado o al indicado."""
    token = _TELEGRAM_TOKEN
    chat  = chat_id or _TELEGRAM_CHAT_ID

    if not token:
        return (
            "Para usar Telegram necesitás agregar TELEGRAM_BOT_TOKEN al .env. "
            "Creá un bot con BotFather en Telegram y pegá el token."
        )
    if not chat:
        return (
            "Falta TELEGRAM_CHAT_ID en el .env. "
            "Escribile a tu bot y buscá el ID en https://api.telegram.org/bot<TOKEN>/getUpdates."
        )
    try:
        import requests
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        r   = requests.post(url, json={"chat_id": chat, "text": message}, timeout=10)
        if r.status_code == 200:
            logger.info(f"Telegram enviado: {message[:40]}")
            return f"Mensaje enviado por Telegram."
        logger.error(f"Telegram error {r.status_code}: {r.text}")
        return f"Error enviando Telegram: código {r.status_code}."
    except Exception as e:
        logger.error(f"Telegram exception: {e}")
        return f"No pude enviar el mensaje: {e}"


def get_telegram_messages() -> str:
    """Lee los últimos mensajes recibidos en el bot."""
    token = _TELEGRAM_TOKEN
    if not token:
        return "TELEGRAM_BOT_TOKEN no configurado."
    try:
        import requests
        url = f"https://api.telegram.org/bot{token}/getUpdates?limit=5&offset=-5"
        r   = requests.get(url, timeout=10)
        data = r.json()
        updates = data.get("result", [])
        if not updates:
            return "No hay mensajes nuevos."
        msgs = []
        for u in updates[-3:]:
            msg  = u.get("message", {})
            text = msg.get("text", "")
            fr   = msg.get("from", {}).get("first_name", "?")
            if text:
                msgs.append(f"{fr}: {text[:50]}")
        return " | ".join(msgs) if msgs else "Sin mensajes de texto recientes."
    except Exception as e:
        return f"Error leyendo Telegram: {e}"


# ─── WhatsApp ────────────────────────────────────────────────────────────────

def send_whatsapp(message: str, number: str = "") -> str:
    """
    Envía un mensaje de WhatsApp usando pywhatkit.
    Requiere Chrome con WhatsApp Web ya logueado.
    number: formato internacional sin + (ej: 541161234567).
             Si está vacío usa WHATSAPP_DEFAULT_NUMBER del .env.
    """
    num = number or _WA_DEFAULT_NUM
    if not num:
        return (
            "Indicá el número o configurá WHATSAPP_DEFAULT_NUMBER en el .env. "
            "Formato: código país + número sin espacios ni +."
        )
    try:
        import pywhatkit as kit
        import datetime
        now  = datetime.datetime.now()
        hour = now.hour
        minute = now.minute + 2  # 2 minutos de margen
        if minute >= 60:
            hour  += 1
            minute -= 60
        kit.sendwhatmsg(
            f"+{num}", message,
            hour, minute,
            wait_time=15, tab_close=True,
        )
        return f"WhatsApp programado para +{num}: {message[:40]}."
    except ImportError:
        return "Para WhatsApp instalá pywhatkit: pip install pywhatkit"
    except Exception as e:
        logger.error(f"WhatsApp error: {e}")
        return f"No pude enviar el WhatsApp: {e}"
