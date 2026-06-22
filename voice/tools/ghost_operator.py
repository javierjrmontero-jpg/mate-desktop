#!/usr/bin/env python3
"""
MATE Ghost Operator — PRO
Control de mouse, teclado y pantalla por voz.
Requiere: pyautogui (ya incluido en el proyecto).
"""

import re
import time
import logging

logger = logging.getLogger(__name__)


# ─── Mouse ───────────────────────────────────────────────────────────────────

def click(x: int, y: int) -> str:
    """Click izquierdo en coordenadas absolutas de pantalla."""
    try:
        import pyautogui
        pyautogui.click(x, y)
        return f"Click en {x}, {y}."
    except Exception as e:
        return f"No pude hacer click: {e}"


def right_click(x: int, y: int) -> str:
    try:
        import pyautogui
        pyautogui.rightClick(x, y)
        return f"Click derecho en {x}, {y}."
    except Exception as e:
        return f"Error en click derecho: {e}"


def double_click(x: int, y: int) -> str:
    try:
        import pyautogui
        pyautogui.doubleClick(x, y)
        return f"Doble click en {x}, {y}."
    except Exception as e:
        return f"Error en doble click: {e}"


def scroll_down(amount: int = 5) -> str:
    try:
        import pyautogui
        pyautogui.scroll(-amount)
        return f"Scroll hacia abajo."
    except Exception as e:
        return f"Error en scroll: {e}"


def scroll_up(amount: int = 5) -> str:
    try:
        import pyautogui
        pyautogui.scroll(amount)
        return f"Scroll hacia arriba."
    except Exception as e:
        return f"Error en scroll: {e}"


# ─── Teclado ─────────────────────────────────────────────────────────────────

def type_text(text: str) -> str:
    """Escribe texto como si fuera del teclado físico."""
    try:
        import pyautogui
        time.sleep(0.15)
        pyautogui.write(text, interval=0.03)
        return f"Texto escrito."
    except Exception as e:
        return f"No pude escribir: {e}"


def press_key(key: str) -> str:
    """
    Presiona una tecla o atajo.
    Ejemplos: 'enter', 'tab', 'ctrl+c', 'ctrl+shift+t', 'win+d'.
    """
    try:
        import pyautogui
        keys = [k.strip() for k in key.lower().split("+")]
        if len(keys) == 1:
            pyautogui.press(keys[0])
        else:
            pyautogui.hotkey(*keys)
        return f"Tecla {key} ejecutada."
    except Exception as e:
        return f"Error presionando {key}: {e}"


# ─── Portapapeles ─────────────────────────────────────────────────────────────

def copy() -> str:
    try:
        import pyautogui
        pyautogui.hotkey("ctrl", "c")
        time.sleep(0.2)
        return "Copiado."
    except Exception as e:
        return f"Error copiando: {e}"


def paste() -> str:
    try:
        import pyautogui
        pyautogui.hotkey("ctrl", "v")
        return "Pegado."
    except Exception as e:
        return f"Error pegando: {e}"


def cut() -> str:
    try:
        import pyautogui
        pyautogui.hotkey("ctrl", "x")
        return "Cortado."
    except Exception as e:
        return f"Error cortando: {e}"


def select_all() -> str:
    try:
        import pyautogui
        pyautogui.hotkey("ctrl", "a")
        return "Todo seleccionado."
    except Exception as e:
        return f"Error: {e}"


def undo() -> str:
    try:
        import pyautogui
        pyautogui.hotkey("ctrl", "z")
        return "Deshacer."
    except Exception as e:
        return f"Error: {e}"


def redo() -> str:
    try:
        import pyautogui
        pyautogui.hotkey("ctrl", "y")
        return "Rehacer."
    except Exception as e:
        return f"Error: {e}"


# ─── Navegador / Pestañas ─────────────────────────────────────────────────────

def new_tab() -> str:
    try:
        import pyautogui
        pyautogui.hotkey("ctrl", "t")
        return "Nueva pestaña abierta."
    except Exception as e:
        return f"Error: {e}"


def close_tab() -> str:
    try:
        import pyautogui
        pyautogui.hotkey("ctrl", "w")
        return "Pestaña cerrada."
    except Exception as e:
        return f"Error: {e}"


def next_tab() -> str:
    try:
        import pyautogui
        pyautogui.hotkey("ctrl", "tab")
        return "Siguiente pestaña."
    except Exception as e:
        return f"Error: {e}"


def prev_tab() -> str:
    try:
        import pyautogui
        pyautogui.hotkey("ctrl", "shift", "tab")
        return "Pestaña anterior."
    except Exception as e:
        return f"Error: {e}"


def reopen_tab() -> str:
    """Reabre la última pestaña cerrada."""
    try:
        import pyautogui
        pyautogui.hotkey("ctrl", "shift", "t")
        return "Pestaña reabierta."
    except Exception as e:
        return f"Error: {e}"


def navigate_to(url: str) -> str:
    """Abre una URL en el navegador activo (foco en barra de dirección)."""
    try:
        import pyautogui
        pyautogui.hotkey("ctrl", "l")
        time.sleep(0.3)
        pyautogui.write(url, interval=0.02)
        pyautogui.press("enter")
        return f"Navegando a {url}."
    except Exception as e:
        return f"Error: {e}"


def browser_search(query: str) -> str:
    """Abre nueva pestaña y busca en Google."""
    try:
        import pyautogui
        pyautogui.hotkey("ctrl", "t")
        time.sleep(0.4)
        pyautogui.write(query, interval=0.02)
        pyautogui.press("enter")
        return f"Buscando '{query[:30]}' en el navegador."
    except Exception as e:
        return f"Error: {e}"


def go_back() -> str:
    try:
        import pyautogui
        pyautogui.hotkey("alt", "left")
        return "Volviendo atrás."
    except Exception as e:
        return f"Error: {e}"


def go_forward() -> str:
    try:
        import pyautogui
        pyautogui.hotkey("alt", "right")
        return "Avanzando."
    except Exception as e:
        return f"Error: {e}"


def refresh_page() -> str:
    try:
        import pyautogui
        pyautogui.press("f5")
        return "Página recargada."
    except Exception as e:
        return f"Error: {e}"


# ─── Sistema ──────────────────────────────────────────────────────────────────

def show_desktop() -> str:
    try:
        import pyautogui
        pyautogui.hotkey("win", "d")
        return "Escritorio mostrado."
    except Exception as e:
        return f"Error: {e}"


def lock_screen() -> str:
    try:
        import pyautogui
        pyautogui.hotkey("win", "l")
        return "Pantalla bloqueada."
    except Exception as e:
        return f"Error: {e}"


def task_view() -> str:
    try:
        import pyautogui
        pyautogui.hotkey("win", "tab")
        return "Vista de tareas."
    except Exception as e:
        return f"Error: {e}"


def get_cursor_position() -> str:
    """Retorna la posición actual del cursor."""
    try:
        import pyautogui
        x, y = pyautogui.position()
        return f"El cursor está en {x}, {y}."
    except Exception as e:
        return f"Error: {e}"


# ─── Vision Click ────────────────────────────────────────────────────────────

def click_element(element_name: str) -> str:
    """Captura la pantalla, usa Claude Vision para encontrar el elemento y hace click."""
    try:
        import os, json, base64, anthropic, pyautogui
        from io import BytesIO

        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            return "ANTHROPIC_API_KEY no configurado en .env."

        img = pyautogui.screenshot()
        buf = BytesIO()
        img.save(buf, format="PNG")
        img_b64 = base64.standard_b64encode(buf.getvalue()).decode()

        client = anthropic.Anthropic(api_key=api_key)
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=64,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": img_b64}},
                    {"type": "text", "text": (
                        f"Find the UI element described as '{element_name}'. "
                        "Reply ONLY with JSON: {\"x\": int, \"y\": int} using screen pixel coordinates. "
                        "If not found, reply {\"x\": -1, \"y\": -1}."
                    )},
                ],
            }],
        )

        raw = resp.content[0].text.strip()
        m = re.search(r'\{[^}]+\}', raw)
        if not m:
            return f"No pude localizar '{element_name}' en pantalla."
        coords = json.loads(m.group())
        x, y = int(coords.get("x", -1)), int(coords.get("y", -1))
        if x < 0 or y < 0:
            return f"No encontré '{element_name}' en la pantalla."

        pyautogui.click(x, y)
        return f"Click en '{element_name}'."
    except Exception as e:
        logger.error(f"click_element error: {e}")
        return f"Error haciendo click en '{element_name}': {e}"


# ─── Escritorios Virtuales ────────────────────────────────────────────────────

def new_virtual_desktop() -> str:
    try:
        import pyautogui
        pyautogui.hotkey("win", "ctrl", "d")
        return "Nuevo escritorio virtual creado."
    except Exception as e:
        return f"Error: {e}"


def switch_virtual_desktop(direction: str = "right") -> str:
    try:
        import pyautogui
        key = "right" if direction.lower() in ("right", "derecha", "siguiente") else "left"
        pyautogui.hotkey("win", "ctrl", key)
        label = "siguiente" if key == "right" else "anterior"
        return f"Cambiado al escritorio virtual {label}."
    except Exception as e:
        return f"Error: {e}"


def close_virtual_desktop() -> str:
    try:
        import pyautogui
        pyautogui.hotkey("win", "ctrl", "f4")
        return "Escritorio virtual cerrado."
    except Exception as e:
        return f"Error: {e}"
