#!/usr/bin/env python3
"""
MATE Orb — Native Windows UI
Orbe flotante con interfaz de voz para MATE
Requiere: pip install PyQt6 sounddevice soundfile numpy faster-whisper edge-tts openwakeword pydub requests
"""

import sys
import math
import threading
import time
import logging
import os
import re
import json
from pathlib import Path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Qt
# ---------------------------------------------------------------------------
try:
    from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QSystemTrayIcon, QMenu
    from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal
    from PyQt6.QtGui import QPainter, QColor, QRadialGradient, QIcon, QPen, QPixmap, QBrush
except ImportError:
    print("ERROR: Instalá PyQt6 primero:")
    print("  pip install PyQt6")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Config — carga .env local si existe (portabilidad entre PCs)
# ---------------------------------------------------------------------------
_env_file = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(_env_file):
    with open(_env_file, encoding="utf-8") as _ef:
        for _line in _ef:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _v = _line.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))

MATE_URL   = os.getenv("MATE_URL", "https://mate.local")
ORB_SIZE   = 180
TOKEN_FILE   = os.path.join(os.path.dirname(__file__), ".mate_token")
NOTIFY_FILE  = os.path.join(os.path.dirname(__file__), ".mate_queue.json")
CONV_TIMEOUT = 10.0   # segundos sin habla antes de cerrar la conversación automáticamente

# ---------------------------------------------------------------------------
# Estados del orbe
# ---------------------------------------------------------------------------
IDLE       = "idle"
LISTENING  = "listening"
PROCESSING = "processing"
SPEAKING   = "speaking"
ERROR      = "error"
ALERT      = "alert"    # notificación proactiva entrante

# ---------------------------------------------------------------------------
# OrbWidget — canvas animado
# ---------------------------------------------------------------------------
class OrbWidget(QWidget):
    clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._state  = IDLE
        self._frame  = 0
        self._drag   = None

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(33)   # ~30 fps

        self.setCursor(Qt.CursorShape.PointingHandCursor)

    # public ----------------------------------------------------------------
    def set_state(self, state: str):
        self._state = state
        self.update()

    # internal --------------------------------------------------------------
    def _tick(self):
        self._frame += 1
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        cx, cy = w // 2, h // 2
        r  = min(w, h) // 2 - 14
        f  = self._frame

        if   self._state == IDLE:       self._idle(p, cx, cy, r, f)
        elif self._state == LISTENING:  self._listening(p, cx, cy, r, f)
        elif self._state == PROCESSING: self._processing(p, cx, cy, r, f)
        elif self._state == SPEAKING:   self._speaking(p, cx, cy, r, f)
        elif self._state == ERROR:      self._error(p, cx, cy, r, f)
        elif self._state == ALERT:      self._alert(p, cx, cy, r, f)
        p.end()

    # --- paint states -------------------------------------------------------

    def _idle(self, p, cx, cy, r, f):
        pulse = 0.88 + 0.12 * math.sin(f * 0.04)
        cr = int(r * pulse)

        # Outer glow
        g = QRadialGradient(cx, cy, int(cr * 1.5))
        g.setColorAt(0.0, QColor(0, 0, 0, 0))
        g.setColorAt(0.6, QColor(20, 80, 200, 18))
        g.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.setBrush(QBrush(g)); p.setPen(Qt.PenStyle.NoPen)
        gr = int(cr * 1.5)
        p.drawEllipse(cx - gr, cy - gr, gr * 2, gr * 2)

        # Core
        g2 = QRadialGradient(cx - r // 4, cy - r // 4, cr)
        g2.setColorAt(0.0, QColor(130, 175, 255, 220))
        g2.setColorAt(0.4, QColor(40,  105, 225, 205))
        g2.setColorAt(0.8, QColor(15,  50,  165, 185))
        g2.setColorAt(1.0, QColor(5,   20,   80, 155))
        p.setBrush(QBrush(g2))
        p.drawEllipse(cx - cr, cy - cr, cr * 2, cr * 2)

        # Highlight
        hl = int(cr * 0.35)
        g3 = QRadialGradient(cx - hl // 2, cy - hl // 2, hl)
        g3.setColorAt(0.0, QColor(210, 225, 255, 110))
        g3.setColorAt(1.0, QColor(100, 150, 255, 0))
        p.setBrush(QBrush(g3))
        p.drawEllipse(cx - hl - hl // 2, cy - hl - hl // 2, hl * 2, hl * 2)

    def _listening(self, p, cx, cy, r, f):
        pulse = 0.82 + 0.18 * abs(math.sin(f * 0.13))
        cr = int(r * pulse)

        # Ripple waves
        p.setBrush(Qt.BrushStyle.NoBrush)
        for i in range(3):
            age = (f * 3 + i * 40) % 120
            wr  = int(r * (0.88 + age * 0.007))
            alpha = max(0, int(155 - age * 1.4))
            p.setPen(QPen(QColor(0, 185, 255, alpha), 1.5))
            p.drawEllipse(cx - wr, cy - wr, wr * 2, wr * 2)

        # Core
        g = QRadialGradient(cx - r // 4, cy - r // 4, cr)
        g.setColorAt(0.0, QColor(165, 225, 255, 235))
        g.setColorAt(0.4, QColor(0,   155, 255, 225))
        g.setColorAt(0.8, QColor(0,    85, 225, 205))
        g.setColorAt(1.0, QColor(0,    42, 155, 180))
        p.setBrush(QBrush(g)); p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(cx - cr, cy - cr, cr * 2, cr * 2)

        # Mic icon
        p.setPen(QPen(QColor(255, 255, 255, 190), 2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(cx - 7, cy - 13, 14, 18, 7, 7)
        p.drawLine(cx, cy + 5, cx, cy + 12)
        p.drawLine(cx - 8, cy + 10, cx + 8, cy + 10)

    def _processing(self, p, cx, cy, r, f):
        cr = int(r * 0.92)
        g = QRadialGradient(cx, cy, cr)
        g.setColorAt(0.0, QColor(85,  135, 205, 185))
        g.setColorAt(0.6, QColor(30,   72, 165, 155))
        g.setColorAt(1.0, QColor(10,   30,  85, 125))
        p.setBrush(QBrush(g)); p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(cx - cr, cy - cr, cr * 2, cr * 2)

        # 3 orbiting dots
        orb_r = int(r * 0.56)
        base_angle = f * 0.07
        for i, (sz, alpha) in enumerate([(8, 235), (6, 185), (4, 135)]):
            a  = base_angle + i * 2.094
            dx = cx + int(orb_r * math.cos(a))
            dy = cy + int(orb_r * math.sin(a))
            p.setBrush(QBrush(QColor(145, 205, 255, alpha)))
            p.drawEllipse(dx - sz // 2, dy - sz // 2, sz, sz)

    def _speaking(self, p, cx, cy, r, f):
        cr = int(r * 0.95)
        g = QRadialGradient(cx - r // 4, cy - r // 4, cr)
        g.setColorAt(0.0, QColor(145, 215, 255, 235))
        g.setColorAt(0.5, QColor(0,   135, 245, 215))
        g.setColorAt(1.0, QColor(0,    62, 185, 185))
        p.setBrush(QBrush(g)); p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(cx - cr, cy - cr, cr * 2, cr * 2)

        # Audio bars
        num_bars, bw, gap = 9, 4, 5
        total = num_bars * (bw + gap) - gap
        sx = cx - total // 2
        for i in range(num_bars):
            phase  = f * 0.14 + i * 0.45
            bar_h  = int(8 + 22 * abs(math.sin(phase)))
            bx     = sx + i * (bw + gap)
            by     = cy - bar_h // 2
            alpha  = 185 + int(55 * abs(math.sin(phase)))
            p.setBrush(QBrush(QColor(225, 242, 255, alpha)))
            p.drawRoundedRect(bx, by, bw, bar_h, 2, 2)

    def _error(self, p, cx, cy, r, f):
        pulse = 0.5 + 0.5 * abs(math.sin(f * 0.09))
        cr = int(r * 0.9)
        g = QRadialGradient(cx, cy, cr)
        g.setColorAt(0.0, QColor(255, 80,  80, int(205 * pulse)))
        g.setColorAt(0.6, QColor(185, 20,  20, int(155 * pulse)))
        g.setColorAt(1.0, QColor(80,   0,   0, 0))
        p.setBrush(QBrush(g)); p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(cx - cr, cy - cr, cr * 2, cr * 2)

    def _alert(self, p, cx, cy, r, f):
        """Ámbar pulsante — notificación proactiva entrante."""
        pulse = 0.80 + 0.20 * abs(math.sin(f * 0.11))
        cr = int(r * pulse)

        # Anillo exterior ámbar
        p.setBrush(Qt.BrushStyle.NoBrush)
        for i in range(2):
            age = (f * 4 + i * 50) % 100
            wr  = int(r * (0.90 + age * 0.008))
            alpha = max(0, int(170 - age * 1.7))
            p.setPen(QPen(QColor(255, 175, 30, alpha), 2))
            p.drawEllipse(cx - wr, cy - wr, wr * 2, wr * 2)

        # Núcleo naranja-ámbar
        g = QRadialGradient(cx - r // 4, cy - r // 4, cr)
        g.setColorAt(0.0, QColor(255, 220, 100, 240))
        g.setColorAt(0.4, QColor(255, 155,  30, 220))
        g.setColorAt(0.8, QColor(210,  95,   0, 195))
        g.setColorAt(1.0, QColor(120,  50,   0, 160))
        p.setBrush(QBrush(g)); p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(cx - cr, cy - cr, cr * 2, cr * 2)

        # Ícono de campana (simplificado con arco + línea)
        p.setPen(QPen(QColor(255, 255, 200, 200), 2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawArc(cx - 9, cy - 12, 18, 16, 0, 180 * 16)
        p.drawLine(cx - 9, cy + 4, cx + 9, cy + 4)
        p.drawLine(cx - 3, cy + 7, cx + 3, cy + 7)

    # --- drag / click -------------------------------------------------------
    def mousePressEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            self._drag = ev.globalPosition().toPoint() - self.window().pos()

    def mouseMoveEvent(self, ev):
        if self._drag and ev.buttons() == Qt.MouseButton.LeftButton:
            self.window().move(ev.globalPosition().toPoint() - self._drag)

    def mouseReleaseEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton and self._drag:
            delta = ev.globalPosition().toPoint() - self.window().pos()
            if (delta - self._drag).manhattanLength() < 6:
                self.clicked.emit()
        self._drag = None


# ---------------------------------------------------------------------------
# VoiceWorker — pipeline completo en un QThread
# ---------------------------------------------------------------------------
class VoiceWorker(QThread):
    state_changed    = pyqtSignal(str)   # idle / listening / processing / speaking / error
    transcript_ready = pyqtSignal(str)
    response_ready   = pyqtSignal(str)

    def __init__(self, token: str, mate_url: str = MATE_URL):
        super().__init__()
        self.token    = token
        self.mate_url = mate_url
        self._running = True
        self._stop_tts = threading.Event()
        self._manual_trigger = threading.Event()
        self._speaking_flag = threading.Event()
        self._conv_id  = None
        self._barge_in = threading.Event()

    def stop(self):
        self._running = False
        self._stop_tts.set()

    # --- main loop ----------------------------------------------------------
    def run(self):
        try:
            self._pipeline()
        except Exception as e:
            logger.error(f"VoiceWorker crash: {e}", exc_info=True)
            self.state_changed.emit(ERROR)

    def _pipeline(self):
        import numpy as np
        import sounddevice as sd
        import openwakeword
        from openwakeword.model import Model as WakeModel
        import faster_whisper

        import pyttsx3
        logger.info("Cargando modelos de voz…")

        # Seleccionar dispositivo de entrada compatible (evitar WDM-KS)
        devs = sd.query_devices()
        best_input = None
        for preferred in ["Windows WASAPI", "MME", "Windows DirectSound"]:
            for i, api in enumerate(sd.query_hostapis()):
                if preferred.lower() in api["name"].lower():
                    idx = api["default_input_device"]
                    if idx >= 0 and devs[idx]["max_input_channels"] > 0:
                        best_input = idx
                        logger.info(f"Audio input: {devs[idx]['name']} ({api['name']})")
                        break
            if best_input is not None:
                break
        if best_input is not None:
            sd.default.device = (best_input, sd.default.device[1])

        _ww_model = str(Path(__file__).parent / "models" / "oye_mate.onnx")
        ww = WakeModel(wakeword_models=[_ww_model], inference_framework="onnx")
        stt  = faster_whisper.WhisperModel("medium", device="cpu", compute_type="int8")

        # TTS local (Windows SAPI — sin red, instantáneo)
        self._tts = pyttsx3.init()
        self._tts.setProperty("rate", 165)
        for v in self._tts.getProperty("voices"):
            if any(x in v.name.lower() for x in ["spanish", "helena", "sabina", "es-", "español"]):
                self._tts.setProperty("voice", v.id)
                logger.info(f"Voz TTS: {v.name}")
                break

        available = list(ww.models.keys()) if hasattr(ww, "models") else ["(desconocidos)"]
        logger.info(f"Wake words disponibles: {available}")
        logger.info("MATE Orb listo — decí 'oye MATE' o hacé clic en el orbe para activar")
        self.state_changed.emit(IDLE)

        # Chime de inicio (sonido del sistema de Windows, sin dependencias extra)
        try:
            import winsound
            winsound.PlaySound(
                r"C:\Windows\Media\chimes.wav",
                winsound.SND_FILENAME | winsound.SND_ASYNC,
            )
        except Exception:
            pass

        SR, CHUNK = 16000, 1280
        import queue as _queue

        while self._running:
            # ── 1. Wake word o click (callback mode — compatible con WDM-KS) ─
            if self._manual_trigger.is_set():
                self._manual_trigger.clear()
                logger.info("Activado por clic")
            else:
                ww_q = _queue.Queue()
                def _ww_cb(indata, frames, t, status):
                    ww_q.put(indata.copy())

                with sd.InputStream(samplerate=SR, channels=1, dtype="int16",
                                    blocksize=CHUNK, callback=_ww_cb):
                    while self._running and not self._manual_trigger.is_set():
                        try:
                            chunk = ww_q.get(timeout=0.5)
                        except _queue.Empty:
                            continue
                        pred = ww.predict(chunk.flatten())
                        best = max(pred.values()) if pred else 0
                        if best > 0.02:
                            logger.debug(f"Wake scores: { {k: f'{v:.3f}' for k,v in pred.items() if v > 0.01} }")
                        if any(v > 0.90 for v in pred.values()):
                            logger.info("Wake word detectado")
                            # Earcon: doble beep corto al activarse
                            try:
                                import winsound
                                winsound.Beep(880, 80)
                                winsound.Beep(1100, 80)
                            except Exception:
                                pass
                            break
                    if self._manual_trigger.is_set():
                        self._manual_trigger.clear()
                        logger.info("Activado por clic durante escucha de wake word")
            if not self._running:
                break

            # ── Bucle de conversación continua ────────────────────────────
            in_conv = True
            while in_conv and self._running:

                # ── 2. Capturar habla ──────────────────────────────────────
                while self._speaking_flag.is_set() and self._running:
                    time.sleep(0.05)
                self.state_changed.emit(LISTENING)
                audio = self._capture(SR, max_sec=CONV_TIMEOUT)
                if audio is None:
                    logger.info("Sin respuesta — fin de conversación")
                    self.state_changed.emit(IDLE)
                    in_conv = False
                    break

                # ── 3. STT ────────────────────────────────────────────────
                self.state_changed.emit(PROCESSING)
                text = self._transcribe(stt, audio)
                if not text.strip():
                    self.state_changed.emit(IDLE)
                    in_conv = False
                    break

                self.transcript_ready.emit(text)
                logger.info(f"STT: {text}")

                # Cierre explícito de conversación
                if re.search(
                    r'\b(adi[oó]s|hasta luego|chau|eso es todo|terminamos|listo gracias|hasta pronto)\b',
                    text.lower()
                ):
                    self.state_changed.emit(SPEAKING)
                    self._speak("Hasta luego.")
                    self.state_changed.emit(IDLE)
                    in_conv = False
                    break

                # ── 4. Comandos locales de sistema (sin llamada al API) ───
                try:
                    import sys as _sys, os as _os
                    _tools_dir = _os.path.join(_os.path.dirname(__file__), "tools")
                    if _tools_dir not in _sys.path:
                        _sys.path.insert(0, _os.path.dirname(__file__))
                    from tools.system_control import detect_and_execute
                    local_resp = detect_and_execute(text)
                    if local_resp:
                        logger.info(f"[LOCAL] {local_resp}")
                        self.response_ready.emit(local_resp)
                        self.state_changed.emit(SPEAKING)
                        self._speak(local_resp)
                        self._barge_in.clear()
                        self.state_changed.emit(LISTENING)
                        continue
                except Exception as _e:
                    logger.warning(f"System control error: {_e}")

                # ── 5. MATE API ───────────────────────────────────────────
                reply = self._call_mate(text)
                if not reply:
                    self.state_changed.emit(ERROR)
                    time.sleep(1.5)
                    self.state_changed.emit(IDLE)
                    in_conv = False
                    break

                self.response_ready.emit(reply)

                # ── 6. TTS ────────────────────────────────────────────────
                self.state_changed.emit(SPEAKING)
                self._speak(reply)

                # Barge-in: usuario interrumpió → capturar de inmediato
                if self._barge_in.is_set():
                    logger.info("Barge-in — procesando nuevo input")
                    self._barge_in.clear()
                    continue   # vuelve a capturar sin wake word

                # Sin interrupción: seguir en conversación
                self.state_changed.emit(LISTENING)

    # --- helpers ------------------------------------------------------------

    def _capture(self, sr: int, silence_sec=1.0, max_sec=12.0):
        """
        Captura audio hasta detectar silencio post-habla.
        max_sec: timeout antes de detectar voz (ej. 10s en modo conversación).
        Una vez detectada voz, la captura continúa hasta silencio (no se corta por max_sec).
        """
        import numpy as np
        import sounddevice as sd
        import queue as _queue
        CHUNK = 1024
        THRESHOLD = 250
        MIN_SPEECH_FRAMES = 4
        silence_needed   = int(silence_sec * sr / CHUNK)
        pre_speech_limit = int(max_sec     * sr / CHUNK)   # frames para timeout sin voz
        hard_limit       = int(15.0        * sr / CHUNK)   # límite duro post-voz

        cap_q = _queue.Queue()
        def _cap_cb(indata, frames, t, status):
            cap_q.put(indata.copy())

        silence = 0
        buf = []
        speech_frames = 0
        total_frames  = 0

        with sd.InputStream(samplerate=sr, channels=1, dtype="int16",
                            blocksize=CHUNK, callback=_cap_cb):
            while self._running:
                total_frames += 1
                # Timeout si todavía no hay voz
                if speech_frames < MIN_SPEECH_FRAMES and total_frames >= pre_speech_limit:
                    break
                # Límite duro una vez que hay voz (15s máx desde el inicio)
                if speech_frames >= MIN_SPEECH_FRAMES and total_frames >= hard_limit:
                    break
                try:
                    chunk = cap_q.get(timeout=1.0)
                except _queue.Empty:
                    continue
                flat = chunk.flatten()
                rms  = np.abs(flat).mean()
                buf.append(flat.copy())

                if rms >= THRESHOLD:
                    speech_frames += 1
                    silence = 0
                elif speech_frames >= MIN_SPEECH_FRAMES:
                    silence += 1
                    if silence >= silence_needed:
                        break

        if speech_frames < MIN_SPEECH_FRAMES:
            logger.debug(f"Captura descartada: {speech_frames} frames de voz")
            return None

        return np.concatenate(buf)

    def _transcribe(self, model, audio) -> str:
        import numpy as np
        f32 = audio.astype(np.float32) / 32768.0
        segs, _ = model.transcribe(
            f32,
            language="es",
            beam_size=5,
            initial_prompt="Instrucción para MATE, asistente personal en español.",
            condition_on_previous_text=False,
            no_speech_threshold=0.6,
            temperature=0.0,
        )
        return " ".join(s.text for s in segs).strip()

    def _call_mate(self, text: str) -> str:
        import requests, json
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.token}",
        }
        voice_text = f"{text}\n[VOZ: respondé en 1-2 oraciones, sin markdown]"
        payload = {
            "messages": [{"role": "user", "content": voice_text}],
            "voice": True,
        }
        if self._conv_id:
            payload["conversation_id"] = self._conv_id

        result = ""
        try:
            with requests.post(
                f"{self.mate_url}/api/v1/chat",
                json=payload, headers=headers,
                stream=True, timeout=60, verify=False,
            ) as r:
                for raw in r.iter_lines():
                    if not self._running: break
                    if not raw: continue
                    line = raw.decode("utf-8")
                    if not line.startswith("data: "): continue
                    tok = line[6:].strip()
                    if not tok:
                        continue
                    try:
                        chunk = json.loads(tok)
                    except Exception:
                        continue
                    if not isinstance(chunk, str):
                        continue
                    if chunk == "[DONE]":
                        break
                    if chunk.startswith("[STATUS:"):
                        continue
                    if chunk.startswith("[CONFIRM_EMAIL:"):
                        continue
                    if chunk.startswith("[CONV:"):
                        self._conv_id = chunk[6:-1]
                        continue
                    result += chunk
        except Exception as e:
            logger.error(f"MATE API error: {e}")
        return result

    @staticmethod
    def _strip_markdown(text: str) -> str:
        """Elimina formato markdown para que el TTS no lea símbolos."""
        text = re.sub(r'\*{1,3}(.+?)\*{1,3}', r'\1', text, flags=re.DOTALL)
        text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
        text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
        text = re.sub(r'```[\s\S]*?```', '', text)
        text = re.sub(r'`([^`]+)`', r'\1', text)
        text = re.sub(r'^\s*[-*+]\s+', '', text, flags=re.MULTILINE)
        text = re.sub(r'^\s*\d+\.\s+', '', text, flags=re.MULTILINE)
        text = re.sub(r'^[-*_]{3,}$', '', text, flags=re.MULTILINE)
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()

    def _speak(self, text: str):
        text = self._strip_markdown(text)
        if not text.strip():
            return
        self._stop_tts.clear()
        self._barge_in.clear()
        self._speaking_flag.set()

        # Monitor de barge-in en hilo paralelo (detecta si el usuario habla durante TTS)
        monitor = threading.Thread(target=self._barge_in_monitor, daemon=True)
        monitor.start()

        try:
            tts = getattr(self, "_tts", None)
            if tts is None:
                import pyttsx3
                tts = pyttsx3.init()
                tts.setProperty("rate", 165)

            # Dividir en oraciones para poder interrumpir entre ellas
            sentences = re.split(r'(?<=[.!?])\s+', text.strip())
            for sentence in sentences:
                if self._stop_tts.is_set() or self._barge_in.is_set():
                    logger.info("TTS interrumpido")
                    break
                if sentence.strip():
                    tts.say(sentence.strip())
                    tts.runAndWait()
        except Exception as e:
            logger.error(f"TTS error: {e}")
        finally:
            time.sleep(0.2)
            self._speaking_flag.clear()

    def _barge_in_monitor(self):
        """
        Corre en hilo paralelo durante TTS.
        Si detecta voz del usuario (RMS > umbral alto) por N frames consecutivos,
        activa _barge_in para interrumpir la reproducción.
        """
        import numpy as np
        import sounddevice as sd
        import queue as _queue

        BARGE_THRESHOLD = 600   # más alto que THRESHOLD de captura para evitar eco del TTS
        CONFIRM_FRAMES  = 4     # frames consecutivos requeridos para confirmar intención

        q = _queue.Queue()
        def _cb(indata, frames, t, status):
            q.put(indata.copy())

        consecutive = 0
        try:
            with sd.InputStream(samplerate=16000, channels=1, dtype="int16",
                                blocksize=1280, callback=_cb):
                while self._speaking_flag.is_set() and self._running:
                    try:
                        chunk = q.get(timeout=0.4)
                        rms = np.abs(chunk.flatten()).mean()
                        if rms > BARGE_THRESHOLD:
                            consecutive += 1
                            if consecutive >= CONFIRM_FRAMES:
                                logger.info(f"Barge-in confirmado (RMS {rms:.0f})")
                                self._barge_in.set()
                                return
                        else:
                            consecutive = max(0, consecutive - 1)
                    except _queue.Empty:
                        consecutive = 0
        except Exception as e:
            logger.debug(f"Barge-in monitor no disponible: {e}")


# ---------------------------------------------------------------------------
# MateOrbWindow — ventana principal
# ---------------------------------------------------------------------------
class MateOrbWindow(QMainWindow):

    # señal para actualizar orbe desde cualquier hilo
    _sig_state = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("MATE Orb")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(ORB_SIZE, ORB_SIZE)

        # Orbe
        self.orb = OrbWidget(self)
        self.orb.setGeometry(0, 0, ORB_SIZE, ORB_SIZE)
        self.orb.clicked.connect(self._on_click)

        # Señal interna (hilo seguro)
        self._sig_state.connect(self.orb.set_state)

        # Posición inicial — esquina inferior derecha
        screen = QApplication.primaryScreen().geometry()
        self.move(screen.width() - ORB_SIZE - 20, screen.height() - ORB_SIZE - 60)

        # Tray
        self._setup_tray()

        # Worker de voz
        self.worker: VoiceWorker | None = None
        token = self._load_token()
        if token:
            self._start_worker(token)
        else:
            logger.warning("No se encontró token. Ejecutá mate_login.py primero.")
            self.orb.set_state(ERROR)

        # Timer de notificaciones proactivas (cada 10s)
        self._notif_timer = QTimer(self)
        self._notif_timer.timeout.connect(self._check_notifications)
        self._notif_timer.start(10_000)

    # --- token --------------------------------------------------------------
    def _load_token(self) -> str | None:
        if os.path.exists(TOKEN_FILE):
            t = open(TOKEN_FILE).read().strip()
            return t if t else None
        return None

    # --- worker -------------------------------------------------------------
    def _start_worker(self, token: str):
        self.worker = VoiceWorker(token, MATE_URL)
        self.worker.state_changed.connect(self._sig_state)
        self.worker.transcript_ready.connect(lambda t: logger.info(f"[STT] {t}"))
        self.worker.response_ready.connect(lambda r: logger.info(f"[MATE] {r[:80]}…"))
        self.worker.start()

    # --- tray ---------------------------------------------------------------
    def _setup_tray(self):
        pm = QPixmap(16, 16)
        pm.fill(QColor(0, 100, 220))
        self.tray = QSystemTrayIcon(QIcon(pm), self)

        menu = QMenu()
        menu.addAction("Mostrar / Ocultar").triggered.connect(self.toggle)
        menu.addSeparator()
        menu.addAction("Salir").triggered.connect(QApplication.quit)

        self.tray.setContextMenu(menu)
        self.tray.show()
        self.tray.activated.connect(
            lambda r: self.toggle()
            if r == QSystemTrayIcon.ActivationReason.DoubleClick else None
        )

    # --- notificaciones proactivas ------------------------------------------
    def _check_notifications(self):
        """
        Llamado por QTimer cada 10s.
        Lee .mate_queue.json y .mate_reminders.json; anuncia cuando el orbe está en IDLE.
        """
        if self.orb._state not in (IDLE, ERROR):
            return   # no interrumpir conversación activa
        if self.worker and self.worker._speaking_flag.is_set():
            return   # TTS en curso

        messages = []

        # ── Cola de notificaciones del monitor (07_monitor.py) ────────────────
        if os.path.exists(NOTIFY_FILE):
            try:
                with open(NOTIFY_FILE, "r", encoding="utf-8") as f:
                    queued = json.load(f)
                if queued:
                    os.remove(NOTIFY_FILE)
                    messages.extend(queued)
            except Exception as e:
                logger.error(f"Error leyendo notificaciones: {e}")

        # ── Recordatorios vencidos (reminder_tools) ───────────────────────────
        try:
            from tools.reminder_tools import check_and_fire
            due = check_and_fire()
            messages.extend(due)
        except Exception as e:
            logger.debug(f"Error chequeando recordatorios: {e}")

        if messages:
            threading.Thread(
                target=self._announce_notifications,
                args=(messages,),
                daemon=True,
            ).start()

    def _announce_notifications(self, messages: list):
        """Habla las notificaciones en estado ALERT usando el TTS del worker."""
        if not self.worker:
            return
        self._sig_state.emit(ALERT)
        try:
            intro = f"Tenés {len(messages)} notificación{'es' if len(messages) > 1 else ''}."
            self.worker._speak(intro)
            for msg in messages:
                if msg.strip():
                    self.worker._speak(msg)
        except Exception as e:
            logger.error(f"Error anunciando notificaciones: {e}")
        finally:
            self._sig_state.emit(IDLE)

    # --- handlers -----------------------------------------------------------
    def _on_click(self):
        if self.worker and self.worker.isRunning():
            logger.info("Click: activando escucha manual")
            self.worker._manual_trigger.set()
            self.orb.set_state(LISTENING)
        else:
            logger.debug("Click: worker no activo")

    def toggle(self):
        self.setVisible(not self.isVisible())

    def closeEvent(self, ev):
        ev.ignore()
        self.hide()

    def cleanup(self):
        if self.worker:
            self.worker.stop()
            self.worker.wait(3000)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName("MATE Orb")

    win = MateOrbWindow()
    win.show()

    try:
        ret = app.exec()
    finally:
        win.cleanup()
    sys.exit(ret)


if __name__ == "__main__":
    main()
