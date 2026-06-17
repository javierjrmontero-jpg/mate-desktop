#!/usr/bin/env python3
"""
MATE System Control Tools — F6-2
Herramientas de control del sistema operativo: apps, sistema, audio, pantalla, ventanas.
Todas las funciones retornan strings listos para TTS.
"""

import os
import re
import subprocess
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

# ─── TIEMPO Y FECHA LOCAL ────────────────────────────────────────────────────

_DIAS    = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
_MESES   = ["enero", "febrero", "marzo", "abril", "mayo", "junio",
            "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]

def get_time() -> str:
    now = datetime.now()
    h, m = now.hour, now.minute
    if m == 0:
        return f"Son las {h} en punto."
    elif m == 1:
        return f"Es la {h} y un minuto."
    else:
        return f"Son las {h}:{m:02d}."

def get_date() -> str:
    now = datetime.now()
    dia_sem  = _DIAS[now.weekday()]
    dia_num  = now.day
    mes      = _MESES[now.month - 1]
    anio     = now.year
    return f"Hoy es {dia_sem} {dia_num} de {mes} de {anio}."

def get_time_and_date() -> str:
    return f"{get_time()} {get_date()}"


# ─── APP ALIASES ─────────────────────────────────────────────────────────────

APP_ALIASES: dict[str, str] = {
    # Navegadores
    "chrome":            "chrome.exe",
    "google chrome":     "chrome.exe",
    "google":            "chrome.exe",
    "firefox":           "firefox.exe",
    "edge":              "msedge.exe",
    "microsoft edge":    "msedge.exe",
    # Office
    "word":              "winword.exe",
    "excel":             "excel.exe",
    "powerpoint":        "powerpnt.exe",
    "outlook":           "outlook.exe",
    "teams":             "ms-teams.exe",
    "microsoft teams":   "ms-teams.exe",
    # Sistema
    "explorador":        "explorer.exe",
    "explorador de archivos": "explorer.exe",
    "calculadora":       "calc.exe",
    "notepad":           "notepad.exe",
    "bloc de notas":     "notepad.exe",
    "bloc":              "notepad.exe",
    "terminal":          "wt.exe",
    "windows terminal":  "wt.exe",
    "cmd":               "cmd.exe",
    "powershell":        "powershell.exe",
    "panel de control":  "control.exe",
    "configuración":     "ms-settings:",
    "configuracion":     "ms-settings:",
    "administrador de tareas": "taskmgr.exe",
    "task manager":      "taskmgr.exe",
    # Dev
    "vscode":            "code.exe",
    "vs code":           "code.exe",
    "visual studio code": "code.exe",
    "visual studio":     "devenv.exe",
    # Navegadores
    "navegador":         "browser:",
    "chrome":            "browser:chrome",
    "google chrome":     "browser:chrome",
    "firefox":           "browser:firefox",
    "edge":              "browser:edge",
    "microsoft edge":    "browser:edge",
    # Media
    "spotify":           "spotify:",
    "vlc":               "vlc.exe",
    "reproductor":       "wmplayer.exe",
    # Otros
    "paint":             "mspaint.exe",
    "snip":              "SnippingTool.exe",
    "recortes":          "SnippingTool.exe",
}


# ─── APP CONTROL ─────────────────────────────────────────────────────────────

def open_app(name: str) -> str:
    n = name.lower().strip()
    exe = APP_ALIASES.get(n)
    try:
        if exe:
            if exe.startswith("browser:"):
                import webbrowser
                browser = exe.split(":", 1)[1]  # "" = default, "chrome", "edge", "firefox"
                if browser:
                    try:
                        webbrowser.get(browser).open("about:newtab")
                    except Exception:
                        webbrowser.open("about:blank")
                else:
                    webbrowser.open("about:blank")
            elif exe.endswith(":"):
                import os
                os.startfile(exe)
            else:
                subprocess.Popen(exe, shell=True)
            return f"Abriendo {name}."
        else:
            subprocess.Popen(f'start "" "{name}"', shell=True)
            return f"Intentando abrir {name}."
    except Exception as e:
        logger.error(f"open_app error: {e}")
        return f"No pude abrir {name}."


def close_app(name: str) -> str:
    n = name.lower().strip()
    exe = APP_ALIASES.get(n, name)
    if not exe.endswith(".exe"):
        exe = exe + ".exe"
    try:
        result = subprocess.run(
            ["taskkill", "/F", "/IM", exe],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            return f"Cerré {name}."
        else:
            return f"No encontré {name} corriendo."
    except Exception as e:
        logger.error(f"close_app error: {e}")
        return f"Error cerrando {name}."


def list_running_apps() -> str:
    try:
        result = subprocess.run(
            ["tasklist", "/FO", "CSV", "/NH"],
            capture_output=True, text=True
        )
        lines = result.stdout.strip().split("\n")
        apps = set()
        skip = {"system", "idle", "registry", "smss.exe", "csrss.exe",
                "wininit.exe", "winlogon.exe", "services.exe", "lsass.exe",
                "svchost.exe", "dwm.exe", "conhost.exe", "fontdrvhost.exe"}
        for line in lines:
            parts = line.strip('"').split('","')
            if parts and parts[0].lower() not in skip:
                name = parts[0].replace(".exe", "")
                if len(name) > 2:
                    apps.add(name)
        top = sorted(apps)[:10]
        return "Procesos activos: " + ", ".join(top) + "."
    except Exception as e:
        return f"No pude listar procesos: {e}"


# ─── SYSTEM INFO ─────────────────────────────────────────────────────────────

def get_cpu_info() -> str:
    try:
        import psutil
        cpu = psutil.cpu_percent(interval=0.8)
        freq = psutil.cpu_freq()
        cores = psutil.cpu_count(logical=False)
        freq_str = f" a {freq.current:.0f} MHz" if freq else ""
        return f"CPU al {cpu}%{freq_str}, {cores} núcleos físicos."
    except ImportError:
        return "psutil no instalado. Ejecutá: pip install psutil"
    except Exception as e:
        return f"No pude leer el CPU: {e}"


def get_ram_info() -> str:
    try:
        import psutil
        mem = psutil.virtual_memory()
        used  = mem.used  / (1024 ** 3)
        total = mem.total / (1024 ** 3)
        return f"RAM: {used:.1f} de {total:.1f} GB usados ({mem.percent}%)."
    except Exception as e:
        return f"No pude leer la RAM: {e}"


def get_disk_info() -> str:
    try:
        import psutil
        parts = []
        for dp in psutil.disk_partitions():
            try:
                u = psutil.disk_usage(dp.mountpoint)
                free  = u.free  / (1024 ** 3)
                total = u.total / (1024 ** 3)
                parts.append(f"{dp.device.rstrip(chr(92))} libre {free:.0f} de {total:.0f} GB")
            except PermissionError:
                pass
        return (". ".join(parts[:3]) + ".") if parts else "Sin información de disco."
    except Exception as e:
        return f"No pude leer el disco: {e}"


def get_battery_info() -> str:
    try:
        import psutil
        bat = psutil.sensors_battery()
        if not bat:
            return "No se detectó batería (equipo de escritorio)."
        status = "cargando" if bat.power_plugged else "descargando"
        if bat.secsleft > 0 and not bat.power_plugged:
            mins = int(bat.secsleft / 60)
            time_str = f", {mins} min restantes"
        else:
            time_str = ""
        return f"Batería al {bat.percent:.0f}%, {status}{time_str}."
    except Exception as e:
        return f"No pude leer la batería: {e}"


def get_gpu_info() -> str:
    # Intentar GPUtil (NVIDIA)
    try:
        import GPUtil
        gpus = GPUtil.getGPUs()
        if gpus:
            g = gpus[0]
            return (f"GPU {g.name}: carga {g.load*100:.0f}%, "
                    f"VRAM {g.memoryUsed:.0f}/{g.memoryTotal:.0f} MB, "
                    f"temperatura {g.temperature}°C.")
    except ImportError:
        pass
    except Exception as e:
        logger.debug(f"GPUtil error: {e}")

    # Fallback: WMI (cualquier GPU)
    try:
        import wmi
        c = wmi.WMI()
        gpus = c.Win32_VideoController()
        if gpus:
            g = gpus[0]
            vram_mb = (g.AdapterRAM or 0) // (1024 * 1024)
            return f"GPU: {g.Name}, {vram_mb} MB VRAM."
    except ImportError:
        pass
    except Exception as e:
        logger.debug(f"WMI GPU error: {e}")

    return "GPU: información no disponible. Instalá GPUtil para NVIDIA."


def get_system_summary() -> str:
    try:
        import psutil
        cpu  = psutil.cpu_percent(interval=0.5)
        mem  = psutil.virtual_memory()
        used = mem.used  / (1024 ** 3)
        tot  = mem.total / (1024 ** 3)
        bat  = psutil.sensors_battery()
        bat_str = f" Batería al {bat.percent:.0f}%." if bat else ""
        return (f"CPU al {cpu}%, RAM {used:.1f} de {tot:.1f} GB "
                f"({mem.percent}%).{bat_str}")
    except Exception as e:
        return f"Error leyendo sistema: {e}"


# ─── AUDIO ───────────────────────────────────────────────────────────────────

def _get_volume_iface():
    """Retorna el interfaz IAudioEndpointVolume de pycaw."""
    from ctypes import cast, POINTER
    from comtypes import CLSCTX_ALL
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    devices = AudioUtilities.GetSpeakers()
    iface   = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    return cast(iface, POINTER(IAudioEndpointVolume))


def _volume_keys(action: str, reps: int = 5):
    """Fallback via teclas de medios."""
    import pyautogui
    for _ in range(reps):
        pyautogui.press(action)


def volume_up(step: int = 10) -> str:
    try:
        vol = _get_volume_iface()
        current = int(vol.GetMasterVolumeLevelScalar() * 100)
        new_vol = min(100, current + step)
        vol.SetMasterVolumeLevelScalar(new_vol / 100, None)
        return f"Volumen subido al {new_vol}%."
    except Exception:
        try:
            _volume_keys("volumeup", step // 2)
            return "Volumen subido."
        except Exception as e:
            return f"No pude subir el volumen: {e}"


def volume_down(step: int = 10) -> str:
    try:
        vol = _get_volume_iface()
        current = int(vol.GetMasterVolumeLevelScalar() * 100)
        new_vol = max(0, current - step)
        vol.SetMasterVolumeLevelScalar(new_vol / 100, None)
        return f"Volumen bajado al {new_vol}%."
    except Exception:
        try:
            _volume_keys("volumedown", step // 2)
            return "Volumen bajado."
        except Exception as e:
            return f"No pude bajar el volumen: {e}"


def volume_mute() -> str:
    try:
        vol = _get_volume_iface()
        muted = vol.GetMute()
        vol.SetMute(not muted, None)
        return "Audio silenciado." if not muted else "Audio activado."
    except Exception:
        try:
            import pyautogui
            pyautogui.press("volumemute")
            return "Silenciado."
        except Exception as e:
            return f"No pude silenciar: {e}"


def get_volume() -> str:
    try:
        vol = _get_volume_iface()
        level = int(vol.GetMasterVolumeLevelScalar() * 100)
        muted = vol.GetMute()
        return f"Volumen al {level}%{', silenciado' if muted else ''}."
    except Exception as e:
        return f"No pude leer el volumen: {e}"


def volume_set(level: int) -> str:
    """Establece el volumen a un nivel específico (0-100)."""
    level = max(0, min(100, level))
    try:
        vol = _get_volume_iface()
        vol.SetMasterVolumeLevelScalar(level / 100, None)
        return f"Volumen ajustado al {level}%."
    except Exception as e:
        return f"No pude ajustar el volumen: {e}"


# ─── SCREEN ──────────────────────────────────────────────────────────────────

def take_screenshot(dest: str = "Desktop") -> str:
    try:
        import pyautogui
        ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
        base = os.path.join(os.path.expanduser("~"), dest)
        os.makedirs(base, exist_ok=True)
        path = os.path.join(base, f"screenshot_{ts}.png")
        img  = pyautogui.screenshot()
        img.save(path)
        return f"Captura guardada como screenshot_{ts}.png."
    except Exception as e:
        return f"No pude capturar la pantalla: {e}"


def set_brightness(level: int) -> str:
    level = max(0, min(100, level))
    try:
        import screen_brightness_control as sbc
        sbc.set_brightness(level)
        return f"Brillo ajustado al {level}%."
    except ImportError:
        return "Instalá screen-brightness-control: pip install screen-brightness-control"
    except Exception as e:
        return f"No pude ajustar el brillo: {e}"


def get_brightness() -> str:
    try:
        import screen_brightness_control as sbc
        val = sbc.get_brightness(display=0)
        if isinstance(val, list):
            val = val[0]
        return f"Brillo al {val}%."
    except ImportError:
        return "screen-brightness-control no instalado."
    except Exception as e:
        return f"No pude leer el brillo: {e}"


def brightness_up(step: int = 20) -> str:
    try:
        import screen_brightness_control as sbc
        cur = sbc.get_brightness(display=0)
        if isinstance(cur, list):
            cur = cur[0]
        return set_brightness(min(100, cur + step))
    except Exception as e:
        return f"No pude subir el brillo: {e}"


def brightness_down(step: int = 20) -> str:
    try:
        import screen_brightness_control as sbc
        cur = sbc.get_brightness(display=0)
        if isinstance(cur, list):
            cur = cur[0]
        return set_brightness(max(0, cur - step))
    except Exception as e:
        return f"No pude bajar el brillo: {e}"


# ─── MODO OSCURO / FONDO DE PANTALLA ─────────────────────────────────────────

def _apply_windows_theme(dark: bool) -> None:
    import winreg, ctypes
    key = winreg.OpenKey(
        winreg.HKEY_CURRENT_USER,
        r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        0, winreg.KEY_SET_VALUE,
    )
    val = 0 if dark else 1
    winreg.SetValueEx(key, "AppsUseLightTheme",    0, winreg.REG_DWORD, val)
    winreg.SetValueEx(key, "SystemUsesLightTheme", 0, winreg.REG_DWORD, val)
    winreg.CloseKey(key)
    # Notificar a Windows del cambio sin cerrar sesión
    ctypes.windll.user32.SendMessageW(0xFFFF, 0x001A, 0, "ImmersiveColorSet")


def set_dark_mode() -> str:
    try:
        _apply_windows_theme(dark=True)
        return "Modo oscuro activado."
    except Exception as e:
        return f"No pude activar el modo oscuro: {e}"


def set_light_mode() -> str:
    try:
        _apply_windows_theme(dark=False)
        return "Modo claro activado."
    except Exception as e:
        return f"No pude activar el modo claro: {e}"


def set_wallpaper(path: str) -> str:
    try:
        import ctypes
        from pathlib import Path
        p = Path(path)
        if not p.exists():
            return f"No encontré el archivo '{path}'."
        if p.suffix.lower() not in {".jpg", ".jpeg", ".png", ".bmp"}:
            return "El fondo debe ser una imagen JPG, PNG o BMP."
        SPI_SETDESKWALLPAPER = 20
        ok = ctypes.windll.user32.SystemParametersInfoW(
            SPI_SETDESKWALLPAPER, 0, str(p.resolve()), 3
        )
        return "Fondo de pantalla actualizado." if ok else "No pude cambiar el fondo de pantalla."
    except Exception as e:
        return f"No pude cambiar el fondo de pantalla: {e}"


# ─── WINDOWS ─────────────────────────────────────────────────────────────────

def minimize_window() -> str:
    try:
        import pygetwindow as gw
        win = gw.getActiveWindow()
        if win:
            win.minimize()
            return f"Minimicé '{win.title}'."
        return "No hay ventana activa."
    except Exception as e:
        return f"No pude minimizar: {e}"


def maximize_window() -> str:
    try:
        import pygetwindow as gw
        win = gw.getActiveWindow()
        if win:
            win.maximize()
            return f"Maximicé '{win.title}'."
        return "No hay ventana activa."
    except Exception as e:
        return f"No pude maximizar: {e}"


def list_windows() -> str:
    try:
        import pygetwindow as gw
        titles = [w.title for w in gw.getAllWindows() if w.title.strip()]
        if not titles:
            return "No hay ventanas abiertas."
        shown = titles[:6]
        extra = f" y {len(titles)-6} más" if len(titles) > 6 else ""
        return "Ventanas abiertas: " + ", ".join(shown) + extra + "."
    except Exception as e:
        return f"No pude listar ventanas: {e}"


def focus_window(name: str) -> str:
    try:
        import pygetwindow as gw
        matches = [w for w in gw.getAllWindows()
                   if name.lower() in w.title.lower() and w.title.strip()]
        if not matches:
            return f"No encontré ventana con '{name}'."
        matches[0].activate()
        return f"Cambié a '{matches[0].title}'."
    except Exception as e:
        return f"No pude cambiar la ventana: {e}"


def close_window() -> str:
    """Cierra la ventana activa con Alt+F4."""
    try:
        import pyautogui
        pyautogui.hotkey("alt", "f4")
        return "Ventana cerrada."
    except Exception as e:
        return f"No pude cerrar la ventana: {e}"


# ─── INTENT ROUTER ───────────────────────────────────────────────────────────

def detect_and_execute(text: str) -> Optional[str]:
    """
    Analiza el texto transcripto y ejecuta el comando local correspondiente.
    Retorna la respuesta TTS si fue un comando local, None si debe ir al API.
    """
    t = text.lower().strip()

    # ── Tiempo y fecha (respuesta instantánea local) ──────────────────────────
    if re.search(r'\b(qu[eé] hora|qu[eé] horas|hora (es|son|actual|tiene)|son las|dime la hora)\b', t):
        return get_time()

    if re.search(r'\b(qu[eé] d[íi]a|fecha (de hoy|actual|es)|hoy es qu[eé]|d[íi]a de hoy|qu[eé] fecha)\b', t):
        return get_date()

    if re.search(r'\b(qu[eé] (hora y )?d[íi]a|hora y fecha|fecha y hora)\b', t):
        return get_time_and_date()

    # ── Sistema info ──────────────────────────────────────────────────────────
    if re.search(r'\b(cpu|procesador|uso del procesador)\b', t):
        return get_cpu_info()

    if re.search(r'\b(ram|memoria ram|memoria del sistema|memoria disponible)\b', t):
        return get_ram_info()

    if re.search(r'\b(disco|almacenamiento|espacio (libre|disponible)|storage)\b', t):
        return get_disk_info()

    if re.search(r'\b(bater[íi]a|porcentaje de carga|est[áa]s enchufad)\b', t):
        return get_battery_info()

    if re.search(r'\b(gpu|tarjeta (de )?video|gr[áa]fica|vram)\b', t):
        return get_gpu_info()

    if re.search(r'\b(estado (del )?(equipo|sistema|computadora|pc)|c[óo]mo est[áa] (el )?(equipo|la compu|el sistema))\b', t):
        return get_system_summary()

    # ── Audio ─────────────────────────────────────────────────────────────────
    # Volumen a porcentaje específico: "pon el volumen al 60"
    m = re.search(r'\b(pon[eé]|ajust[aá]|set|subi|baj[aá]).{0,20}volumen.{0,10}(\d+)', t)
    if m:
        return volume_set(int(m.group(2)))
    m = re.search(r'\b(volumen|audio).{0,10}(\d+)\s*%', t)
    if m:
        return volume_set(int(m.group(2)))

    if re.search(r'\b(sub[ií]|sube|aumenta|m[áa]s).{0,15}(volumen|audio|sonido)\b', t):
        return volume_up()

    if re.search(r'\b(baj[aá]|disminuy[eé]|menos).{0,15}(volumen|audio|sonido)\b', t):
        return volume_down()

    if re.search(r'\b(silenci[aá]|mutea|callate el audio|sin sonido|mute)\b', t):
        return volume_mute()

    if re.search(r'\b(cu[áa]nto (est[áa]|tiene) (el )?volumen|nivel de audio|volumen actual)\b', t):
        return get_volume()

    # ── Pantalla / brillo ─────────────────────────────────────────────────────
    if re.search(r'\b(captura|screenshot|foto de (la )?pantalla|captur[áa])\b', t):
        return take_screenshot()

    m = re.search(r'\bbrillo.{0,15}(\d+)', t)
    if m:
        return set_brightness(int(m.group(1)))
    m = re.search(r'(\d+).{0,10}(de )?brillo\b', t)
    if m:
        return set_brightness(int(m.group(1)))

    if re.search(r'\b(sub[ií]|sube|aumenta|m[áa]s).{0,15}(brillo|iluminaci[óo]n|pantalla)\b', t):
        return brightness_up()

    if re.search(r'\b(baj[aá]|disminuy[eé]|menos|oscurece).{0,15}(brillo|iluminaci[óo]n|pantalla)\b', t):
        return brightness_down()

    if re.search(r'\b(cu[áa]nto (est[áa]|tiene) (el )?brillo|brillo actual)\b', t):
        return get_brightness()

    # ── Ventanas ──────────────────────────────────────────────────────────────
    if re.search(r'\b(minimiz[aá]|minimiza la ventana|pone (la ventana )?abajo)\b', t):
        return minimize_window()

    if re.search(r'\b(maximiz[aá]|maximiza|pantalla completa|agranda la ventana)\b', t):
        return maximize_window()

    if re.search(r'\b(qu[eé] ventanas|ventanas abiertas|qu[eé] tengo abierto|list[aá] ventanas)\b', t):
        return list_windows()

    if re.search(r'\b(cerr[áa]? la ventana|cierra (la ventana )?actual|alt f4)\b', t):
        return close_window()

    m = re.search(r'\b(cambi[aá]|pas[aá]|ir? [aá]|switch)\s+[aá]?\s+(.+?)(?:\s+por favor|$)', t)
    if m:
        target = m.group(2).strip()
        # Evitar falsos positivos con frases como "cambiar de tema"
        if len(target) > 2 and not re.search(r'\b(tema|idioma|modo|color)\b', target):
            return focus_window(target)

    # ── Abrir apps ────────────────────────────────────────────────────────────
    m = re.search(r'\b(abr[íi]|abre|abrí|lanz[aá]|lanza|ejecut[aá]|ejecuta|inici[aá])\s+(.+?)(?:\s+por favor|$)', t)
    if m:
        return open_app(m.group(2).strip())

    # ── Cerrar apps ───────────────────────────────────────────────────────────
    m = re.search(r'\b(cerr[áa]|cierra|cerrá|mat[aá]|mata|apag[aá]|kill)\s+(.+?)(?:\s+por favor|$)', t)
    if m:
        target = m.group(2).strip()
        # Evitar "cierra la ventana" que está manejado arriba
        if "ventana" not in target:
            return close_app(target)

    # ── Procesos activos ──────────────────────────────────────────────────────
    if re.search(r'\b(qu[eé] (programas|procesos|apps) (corren|est[áa]n|hay)|lista de procesos)\b', t):
        return list_running_apps()

    # ── Modo oscuro / claro ───────────────────────────────────────────────────
    if re.search(r'\b(modo oscuro|tema oscuro|pon[eé] oscuro|activ[aá] (el )?modo oscuro|dark mode)\b', t):
        return set_dark_mode()

    if re.search(r'\b(modo claro|tema claro|pon[eé] claro|activ[aá] (el )?modo claro|light mode)\b', t):
        return set_light_mode()

    # ── Fondo de pantalla ─────────────────────────────────────────────────────
    m = re.search(r'\b(?:cambi[aá]|pon[eé]|configur[aá])\s+(?:el\s+)?fondo\s+(?:de\s+pantalla\s+)?(?:a\s+|con\s+)?(.+)', t)
    if m and re.search(r'\bfondo\b', t):
        from tools.file_tools import _resolve
        path = str(_resolve(m.group(1).strip()))
        return set_wallpaper(path)

    # ── Clima ─────────────────────────────────────────────────────────────────
    if re.search(r'\b(clima|tiempo|temperatura|lluv|pronóstico|pron[oó]stico|va a llover|va a nevar|calor|fr[íi]o|nublado|despejado|c[óo]mo est[áa] (el tiempo|el clima))\b', t):
        from tools.web_tools import get_weather
        return get_weather()

    # ── Noticias ──────────────────────────────────────────────────────────────
    if re.search(r'\b(noticias|titulares|novedades|qu[eé] pas[oó] hoy|actualidad|noticias del d[íi]a)\b', t):
        from tools.web_tools import get_news
        return get_news()

    # ── YouTube (antes de Spotify para capturar "X en YouTube") ──────────────
    m = re.search(r'\b(?:reproducí|busc[aá](?:me)?|pon[eé]|mir[áa])\s+(.+?)\s+en youtube\b', t)
    if m:
        from tools.web_tools import open_youtube
        return open_youtube(m.group(1).strip())

    if re.search(r'\b(abr[íi]|abre|entr[áa])\s+(?:a\s+)?youtube\b', t):
        from tools.web_tools import open_youtube
        return open_youtube()

    m = re.search(r'\bbusc[aá](?:me)?\s+en\s+youtube\s+(.+)', t)
    if m:
        from tools.web_tools import open_youtube
        return open_youtube(m.group(1).strip())

    # ── Spotify ───────────────────────────────────────────────────────────────
    m = re.search(r'\b(?:reproducí|reprod[uú]ceme|pon[eé]|toc[aá])\s+(.+?)(?:\s+por favor|$)', t)
    if m and not re.search(r'\b(youtube|yt|la ventana|chrome|app)\b', t):
        from tools.spotify_tools import search_and_play
        return search_and_play(m.group(1).strip())

    if re.search(r'\b(paus[aá]( la música)?|stop( la música| spotify)?|para( la música)?)\b', t):
        from tools.spotify_tools import stop_playback
        return stop_playback()

    if re.search(r'\b(siguiente( canci[oó]n)?|skip|salte[aá])\b', t) and not re.search(r'\b(ventana|paso|tema)\b', t):
        from tools.spotify_tools import next_track
        return next_track()

    if re.search(r'\b(anterior|canci[oó]n anterior|volvé a la anterior)\b', t):
        from tools.spotify_tools import previous_track
        return previous_track()

    if re.search(r'\b(qu[eé] (est[áa] sonando|suena|canci[oó]n (suena|es|est[áa]))|qu[eé] m[uú]sica|qu[eé] toca|qu[eé] est[áa] (tocando|reproduciendo))\b', t):
        from tools.spotify_tools import now_playing
        return now_playing()

    # ── Visión de pantalla ────────────────────────────────────────────────────
    if re.search(r'\b(qu[eé] hay en la pantalla|describi[r]? la pantalla|qu[eé] ves|mir[áa] la pantalla|analiz[aá] la pantalla|qu[eé] se ve)\b', t):
        from tools.web_tools import describe_screen
        return describe_screen()

    # ── Búsqueda web ──────────────────────────────────────────────────────────
    m = re.search(r'\b(?:busc[aá](?:me)?|buscar|qu[eé] es|qui[eé]n es|cu[áa]nto cuesta|c[oó]mo se hace|explic[aá]me|contame sobre)\s+(.+)', t)
    if m:
        from tools.web_tools import search_web
        return search_web(m.group(1).strip())

    # ── Archivos y carpetas ───────────────────────────────────────────────────
    if re.search(r'\b(list[aá]|qu[eé] hay en|mostr[aá] (el contenido|la carpeta))\b', t):
        m = re.search(r'\b(?:list[aá]|qu[eé] hay en|mostr[aá](?:\s+(?:el contenido|la carpeta))?)\s+(?:la carpeta\s+)?(.+?)(?:\s+por favor|$)', t)
        if m:
            from tools.file_tools import list_directory
            return list_directory(m.group(1).strip())

    if re.search(r'\bleé\s+(?:el\s+)?archivo\s+', t):
        m = re.search(r'\bleé\s+(?:el\s+)?archivo\s+(.+?)(?:\s+por favor|$)', t)
        if m:
            from tools.file_tools import read_file
            return read_file(m.group(1).strip())

    m = re.search(r'\bcre[aá](?:me)?\s+(?:una?\s+)?carpeta\s+(?:llamad[ao]\s+)?(.+?)(?:\s+en\s+(.+?))?(?:\s+por favor|$)', t)
    if m:
        folder = m.group(1).strip()
        location = (m.group(2) or "escritorio").strip()
        from tools.file_tools import create_directory, _resolve
        return create_directory(str(_resolve(location) / folder))

    m = re.search(r'\bcopi[aá](?:me)?\s+(.+?)\s+(?:a|hacia|en)\s+(.+?)(?:\s+por favor|$)', t)
    if m and re.search(r'\b(copi[aá])\b', t):
        from tools.file_tools import copy_file
        return copy_file(m.group(1).strip(), m.group(2).strip())

    m = re.search(r'\bmov[eé](?:me)?\s+(.+?)\s+(?:a|hacia)\s+(.+?)(?:\s+por favor|$)', t)
    if m and re.search(r'\b(mov[eé])\b', t):
        from tools.file_tools import move_file
        return move_file(m.group(1).strip(), m.group(2).strip())

    # ── Recordatorios ─────────────────────────────────────────────────────────
    # "recordame en X minutos que Y" / "en X minutos recordame Y"
    m = re.search(r'\brecord[aá]me\b.{0,20}en\s+(\d+)\s+minutos?\s+(?:que\s+)?(.+)', t)
    if not m:
        m = re.search(r'\ben\s+(\d+)\s+minutos?\s+record[aá]me\s+(?:que\s+)?(.+)', t)
    if m:
        from tools.reminder_tools import set_reminder
        return set_reminder(m.group(2).strip(), minutes=int(m.group(1)))

    # "recordame en media hora que Y"
    m = re.search(r'\brecord[aá]me\b.{0,20}en\s+media\s+hora\s+(?:que\s+)?(.+)', t)
    if m:
        from tools.reminder_tools import set_reminder
        return set_reminder(m.group(1).strip(), minutes=30)

    # "recordame en una hora que Y"
    m = re.search(r'\brecord[aá]me\b.{0,20}en\s+una?\s+hora\s+(?:que\s+)?(.+)', t)
    if m:
        from tools.reminder_tools import set_reminder
        return set_reminder(m.group(1).strip(), minutes=60)

    # "recordame a las HH:MM que Y"
    m = re.search(r'\brecord[aá]me\b.{0,20}a\s+las?\s+(\d{1,2}[:.]\d{2})\s+(?:que\s+)?(.+)', t)
    if m:
        from tools.reminder_tools import set_reminder
        at = m.group(1).replace(".", ":")
        return set_reminder(m.group(2).strip(), at_time=at)

    if re.search(r'\b(qu[eé] recordatorios|mis recordatorios|recordatorios pendientes)\b', t):
        from tools.reminder_tools import list_reminders
        return list_reminders()

    # ── Notas ─────────────────────────────────────────────────────────────────
    m = re.search(r'\b(?:anot[aá](?:me)?|guard[aá](?:me)?\s+(?:una?\s+)?nota[:\s])\s*(.+)', t)
    if m:
        from tools.notes_tools import save_note
        return save_note(m.group(1).strip())

    if re.search(r'\b(qu[eé] notas tengo|mis notas|le[eé] mis notas|list[aá] (mis )?notas)\b', t):
        from tools.notes_tools import list_notes
        return list_notes()

    m = re.search(r'\b(?:busc[aá](?:me)?\s+(?:una?\s+)?nota|tengo (alguna )?nota)\s+(?:sobre\s+)?(.+)', t)
    if m:
        from tools.notes_tools import search_notes
        return search_notes(m.group(m.lastindex).strip())

    m = re.search(r'\b(?:le[eé]|mostr[aá])\s+(?:la\s+)?nota\s+(?:sobre\s+)?(.+)', t)
    if m:
        from tools.notes_tools import read_note
        return read_note(m.group(1).strip())

    m = re.search(r'\b(?:borr[aá]|elimin[aá])\s+(?:la\s+)?nota\s+(.+)', t)
    if m:
        from tools.notes_tools import delete_note
        return delete_note(m.group(1).strip())

    # ── Metas ─────────────────────────────────────────────────────────────────
    m = re.search(r'\b(?:cre[aá](?:me)?|guard[aá](?:me)?|agre[gá](?:me)?)\s+(?:una?\s+)?meta\s+(?:para\s+|de\s+)?(.+)', t)
    if m:
        from tools.notes_tools import save_goal
        return save_goal(m.group(1).strip())

    if re.search(r'\b(mis metas|cu[aá]les son mis metas|qu[eé] metas tengo|list[aá] (mis )?metas)\b', t):
        from tools.notes_tools import list_goals
        return list_goals()

    # ── Memoria persistente (PRO) ─────────────────────────────────────────────
    # "recuerda que mi nombre es Javier" / "anota que trabajo en IT"
    m = re.search(r'\b(?:recuerda|anot[aá]|guard[aá])\s+que\s+(.+?)\s+es\s+(.+)', t)
    if m:
        from tools.memory_tools import remember
        return remember(m.group(1).strip(), m.group(2).strip())

    m = re.search(r'\b(?:recuerda|anot[aá]|guard[aá])\s+que\s+(?:me\s+llamo|mi\s+nombre\s+es)\s+(.+)', t)
    if m:
        from tools.memory_tools import remember
        return remember("nombre", m.group(1).strip())

    # "¿qué sabes de mí?" / "qué recuerdas"
    if re.search(r'\b(qu[eé] (sabes|recuerdas|ten[eé]s anotado)|mis datos|qu[eé] s[eé] sobre m[íi]|lo que sab[eé]s)\b', t):
        from tools.memory_tools import list_memories
        return list_memories()

    # "¿qué sabes de mi nombre?" / "recuérdame mi..."
    m = re.search(r'\b(?:qu[eé] sabes de|recuérdame|cu[aá]l es mi)\s+(.+?)(?:\s*\?|$)', t)
    if m and not re.search(r'\b(nombre de la canci[oó]n|de la app|del archivo)\b', t):
        from tools.memory_tools import recall
        return recall(m.group(1).strip())

    # "olvida que / olvida mi nombre"
    m = re.search(r'\b(?:olv[íi]da|borra (que|mi|el|la)?)\s+(.+)', t)
    if m:
        from tools.memory_tools import forget
        return forget(m.group(m.lastindex).strip())

    # ── Dev Agent (PRO) ───────────────────────────────────────────────────────
    # "ejecutá el último script" / "corrí el script anterior"
    if re.search(r'\b(ejecut[aá]|corr[íi])\s+(el\s+)?(último|anterior|último\s+script|script\s+anterior)\b', t):
        from tools.dev_agent_tools import run_last_script
        return run_last_script()

    # "listá los scripts" / "qué scripts tengo"
    if re.search(r'\b(list[aá]|qu[eé] (scripts|código|programas)\s+(guard[aé]|tengo))\b', t) and re.search(r'\bscripts?\b', t):
        from tools.dev_agent_tools import list_scripts
        return list_scripts()

    # "abrí la carpeta de scripts"
    if re.search(r'\b(abr[íi]|mostr[aá])\s+(la\s+)?carpeta\s+de\s+scripts?\b', t):
        from tools.dev_agent_tools import open_scripts_folder
        return open_scripts_folder()

    # "ejecutá PowerShell [comando]"
    m = re.search(r'\b(?:ejecut[aá]|corr[íi])\s+(?:en\s+)?powershell\s+(.+)', t)
    if m:
        from tools.dev_agent_tools import run_powershell
        return run_powershell(m.group(1).strip())

    # ── Ghost Operator (PRO) — control de teclado/mouse ──────────────────────
    # Scroll
    if re.search(r'\b(scrolle[aá]|hace\s+scroll|bajá\s+la\s+página|scroll\s+abajo)\b', t):
        from tools.ghost_operator import scroll_down
        return scroll_down()

    if re.search(r'\b(scroll\s+arriba|subí\s+la\s+página|bajá\s+el\s+scroll)\b', t):
        from tools.ghost_operator import scroll_up
        return scroll_up()

    # Portapapeles
    if re.search(r'\b(copi[aá]\s+todo|seleccion[aá]\s+todo|ctrl\s*\+\s*a)\b', t):
        from tools.ghost_operator import select_all
        return select_all()

    if re.search(r'\b(peg[aá](\s+eso)?|ctrl\s*\+\s*v)\b', t) and not re.search(r'\bspotify\b', t):
        from tools.ghost_operator import paste
        return paste()

    if re.search(r'\b(copi[aá](\s+eso)?|ctrl\s*\+\s*c)\b', t) and not re.search(r'\barchivo\b', t):
        from tools.ghost_operator import copy
        return copy()

    if re.search(r'\b(deshac[eé](\s+eso)?|ctrl\s*\+\s*z)\b', t):
        from tools.ghost_operator import undo
        return undo()

    if re.search(r'\b(rehac[eé](\s+eso)?|ctrl\s*\+\s*y)\b', t):
        from tools.ghost_operator import redo
        return redo()

    # Pestañas
    if re.search(r'\b(nueva\s+pesta[ñn]a|abr[íi]\s+(una\s+)?pesta[ñn]a|ctrl\s*\+\s*t)\b', t):
        from tools.ghost_operator import new_tab
        return new_tab()

    if re.search(r'\b(cerr[aá]\s+(esta\s+)?pesta[ñn]a|ctrl\s*\+\s*w)\b', t):
        from tools.ghost_operator import close_tab
        return close_tab()

    if re.search(r'\b(re?abr[íi]\s+(la\s+)?pesta[ñn]a|pesta[ñn]a\s+cerrada)\b', t):
        from tools.ghost_operator import reopen_tab
        return reopen_tab()

    if re.search(r'\b(siguiente\s+pesta[ñn]a|pesta[ñn]a\s+siguiente)\b', t):
        from tools.ghost_operator import next_tab
        return next_tab()

    if re.search(r'\b(pesta[ñn]a\s+anterior|anterior\s+pesta[ñn]a)\b', t) and not re.search(r'\bcanci[oó]n\b', t):
        from tools.ghost_operator import prev_tab
        return prev_tab()

    # Navegación
    if re.search(r'\b(volv[eé]\s+atr[aá]s|page\s+back|nav[eé]g[aá]\s+atr[aá]s)\b', t):
        from tools.ghost_operator import go_back
        return go_back()

    if re.search(r'\b(avanz[aá]|page\s+forward|nav[eé]g[aá]\s+adelante)\b', t) and not re.search(r'\b(pista|canci[oó]n)\b', t):
        from tools.ghost_operator import go_forward
        return go_forward()

    if re.search(r'\b(recarg[aá]|refresc[aá]|f5|recarg[aá]\s+la\s+p[aá]gina)\b', t):
        from tools.ghost_operator import refresh_page
        return refresh_page()

    # URL directa
    m = re.search(r'\b(?:abr[íi]|ir?\s+[aá]|nav[eé]g[aá]\s+[aá])\s+(https?://\S+|www\.\S+)', t)
    if m:
        from tools.ghost_operator import navigate_to
        return navigate_to(m.group(1).strip())

    # Escritorio / pantalla
    if re.search(r'\b(mostr[aá]\s+(el\s+)?escritorio|escritorio|win\s*\+\s*d)\b', t) and not re.search(r'\b(fondo|imagen)\b', t):
        from tools.ghost_operator import show_desktop
        return show_desktop()

    if re.search(r'\b(bloqu[eé][aá]\s+(la\s+)?pantalla|bloqu[eé][aá]\s+(la\s+)?pc|bloqueo)\b', t):
        from tools.ghost_operator import lock_screen
        return lock_screen()

    # Escribir texto (Ghost)
    m = re.search(r'\b(?:escrib[íi]|tip[eé][aá]|ingres[aá])\s+(?:el\s+texto\s+)?["""]?(.+?)["""]?(?:\s+por\s+favor|$)', t)
    if m and not re.search(r'\b(nota|recordatorio|meta)\b', t):
        from tools.ghost_operator import type_text
        return type_text(m.group(1).strip())

    # ── Mensajería Telegram (PRO) ─────────────────────────────────────────────
    # "mandá un mensaje por telegram que..."  /  "telegram: ..."
    m = re.search(r'\b(?:mand[aá]|env[íi][aá]|decile)\s+(?:un?\s+mensaje\s+)?(?:por\s+)?telegram[:\s]+(.+)', t)
    if m:
        from tools.messaging_tools import send_telegram
        return send_telegram(m.group(1).strip())

    if re.search(r'\b(mensajes\s+de\s+telegram|qu[eé]\s+(me\s+)?lleg[oó]\s+por\s+telegram|telegram\s+nuevos)\b', t):
        from tools.messaging_tools import get_telegram_messages
        return get_telegram_messages()

    # ── Mensajería WhatsApp (PRO) ─────────────────────────────────────────────
    m = re.search(r'\b(?:mand[aá]|env[íi][aá])\s+(?:un?\s+)?(?:mensaje\s+)?(?:de\s+)?whatsapp\s+(?:al?\s+número\s+)?(\d+)?\s*[:\s]+(.+)', t)
    if m:
        from tools.messaging_tools import send_whatsapp
        number  = (m.group(1) or "").strip()
        message = m.group(2).strip()
        return send_whatsapp(message, number)

    m = re.search(r'\b(?:mand[aá]|env[íi][aá])\s+(?:por\s+)?whatsapp[:\s]+(.+)', t)
    if m:
        from tools.messaging_tools import send_whatsapp
        return send_whatsapp(m.group(1).strip())

    # ── Calendario / Agenda (PRO) ─────────────────────────────────────────────
    # "qué tengo hoy" / "mis eventos de hoy"
    if re.search(r'\b(qu[eé]\s+tengo\s+(hoy|para\s+hoy)|eventos\s+de\s+hoy|agenda\s+de\s+hoy|mi\s+agenda\s+hoy)\b', t):
        from tools.calendar_tools import get_today_events
        return get_today_events()

    # "qué tengo esta semana" / "agenda de la semana"
    if re.search(r'\b(qu[eé]\s+tengo\s+(esta|la)\s+semana|eventos\s+de\s+(esta|la)\s+semana|agenda\s+(semanal|de\s+(esta|la)\s+semana))\b', t):
        from tools.calendar_tools import get_week_events
        return get_week_events()

    # "agendá X" / "crea un evento" / "agregame a la agenda"
    m = re.search(r'\b(?:agend[aá](?:me)?|cre[aá]\s+(?:un\s+)?evento|agreg[aá](?:me)?\s+(?:a\s+(?:la\s+)?agenda))\s+(.+)', t)
    if m:
        raw = m.group(1).strip()
        # Intentar extraer hora: "a las 15:00" / "a las 3"
        time_match = re.search(r'a\s+las?\s+(\d{1,2}(?:[:h]\d{2})?)', raw)
        time_hint  = time_match.group(1) if time_match else ""
        # Intentar extraer fecha: "el lunes" / "mañana" / "el 20/06"
        date_match = re.search(r'\b(ma[ñn]ana|pasado|lunes|martes|mi[eé]rcoles|jueves|viernes|s[aá]bado|domingo|\d{1,2}/\d{1,2}(?:/\d{4})?)\b', raw)
        date_hint  = date_match.group(1) if date_match else ""
        # Título = raw sin las partes de fecha/hora
        title = re.sub(r'\b(a\s+las?\s+\d{1,2}(?:[:h]\d{2})?)\b', '', raw)
        title = re.sub(r'\b(ma[ñn]ana|pasado|el\s+lunes|el\s+martes|el\s+mi[eé]rcoles|el\s+jueves|el\s+viernes|el\s+s[aá]bado|el\s+domingo|\d{1,2}/\d{1,2}(?:/\d{4})?)\b', '', title)
        title = re.sub(r'\s{2,}', ' ', title).strip()
        if not title:
            title = raw
        from tools.calendar_tools import create_event
        return create_event(title, date_hint, time_hint)

    # "borrá el evento X" / "eliminá de la agenda X"
    m = re.search(r'\b(?:borr[aá]|elimin[aá])\s+(?:el\s+)?(?:evento\s+|de\s+la\s+agenda\s+)?(.+)', t)
    if m and re.search(r'\b(evento|agenda|reuni[oó]n|cita)\b', t):
        from tools.calendar_tools import delete_event
        return delete_event(m.group(1).strip())

    return None  # → delegar al API de MATE
