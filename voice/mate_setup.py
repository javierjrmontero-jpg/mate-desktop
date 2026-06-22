#!/usr/bin/env python3
"""
MATE Setup Wizard — primer arranque o reconfiguración.
Aparece cuando falta .mate_config.bin o cuando el usuario lo invoca manualmente.
"""
import sys
import os
from pathlib import Path


def _needs_setup() -> bool:
    """True si no hay config cifrada o falta MATE_URL."""
    from secure_config import config_exists, load_config
    if not config_exists():
        return True
    cfg = load_config() or {}
    return not cfg.get("MATE_URL", "").strip()


def run_setup(force: bool = False) -> bool:
    """
    Lanza el wizard. Retorna True si el usuario completó y guardó la configuración.
    force=True: muestra siempre (para reconfiguración).
    """
    if not force and not _needs_setup():
        return True

    try:
        from PyQt6.QtWidgets import (
            QApplication, QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
            QLabel, QLineEdit, QPushButton, QGroupBox, QFileDialog,
            QComboBox, QTabWidget, QWidget, QScrollArea, QFrame,
        )
        from PyQt6.QtCore import Qt
        from PyQt6.QtGui import QFont, QColor, QPalette
    except ImportError:
        print("ERROR: PyQt6 no disponible. Instalá con: pip install PyQt6")
        return False

    app = QApplication.instance() or QApplication(sys.argv)

    dlg = _SetupDialog()
    result = dlg.exec()
    return result == QDialog.DialogCode.Accepted


class _SetupDialog:
    def __init__(self):
        try:
            from PyQt6.QtWidgets import (
                QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
                QLabel, QLineEdit, QPushButton, QGroupBox, QFileDialog,
                QComboBox, QTabWidget, QWidget, QScrollArea,
            )
            from PyQt6.QtCore import Qt
            from PyQt6.QtGui import QFont
        except ImportError:
            return

        self._QDialog        = QDialog
        self._QVBoxLayout    = QVBoxLayout
        self._QHBoxLayout    = QHBoxLayout
        self._QFormLayout    = QFormLayout
        self._QLabel         = QLabel
        self._QLineEdit      = QLineEdit
        self._QPushButton    = QPushButton
        self._QGroupBox      = QGroupBox
        self._QFileDialog    = QFileDialog
        self._QComboBox      = QComboBox
        self._QTabWidget     = QTabWidget
        self._QWidget        = QWidget
        self._QScrollArea    = QScrollArea
        self._Qt             = Qt
        self._QFont          = QFont

    def exec(self):
        from PyQt6.QtWidgets import (
            QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
            QLabel, QLineEdit, QPushButton, QGroupBox, QFileDialog,
            QComboBox, QTabWidget, QWidget,
        )
        from PyQt6.QtCore import Qt
        from PyQt6.QtGui import QFont

        dlg = QDialog()
        dlg.setWindowTitle("MATE — Configuración inicial")
        dlg.setMinimumWidth(540)
        dlg.setStyleSheet("""
            QDialog { background-color: #1a1a2e; color: #e0e0e0; }
            QLabel  { color: #e0e0e0; }
            QLineEdit {
                background: #16213e; color: #e0e0e0;
                border: 1px solid #4a4a8a; border-radius: 4px;
                padding: 5px 8px;
            }
            QLineEdit:focus { border: 1px solid #7c7cff; }
            QPushButton {
                background: #4a4a8a; color: #fff;
                border: none; border-radius: 4px;
                padding: 7px 18px; font-weight: bold;
            }
            QPushButton:hover { background: #6a6aaa; }
            QPushButton#save  { background: #5a5aff; }
            QPushButton#save:hover { background: #7a7aff; }
            QGroupBox {
                border: 1px solid #4a4a8a; border-radius: 6px;
                margin-top: 10px; padding: 8px;
                color: #aaaaff; font-weight: bold;
            }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
            QTabWidget::pane { border: 1px solid #4a4a8a; }
            QTabBar::tab {
                background: #16213e; color: #aaa;
                padding: 6px 14px; border: 1px solid #4a4a8a;
            }
            QTabBar::tab:selected { background: #2a2a5a; color: #fff; }
            QComboBox {
                background: #16213e; color: #e0e0e0;
                border: 1px solid #4a4a8a; border-radius: 4px; padding: 5px 8px;
            }
        """)

        main_layout = QVBoxLayout(dlg)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(16, 16, 16, 16)

        # Título
        title = QLabel("⚙  Configuración de MATE")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title.setStyleSheet("color: #aaaaff; margin-bottom: 4px;")
        main_layout.addWidget(title)

        subtitle = QLabel("Los datos se guardan cifrados con Windows DPAPI. Solo vos podés leerlos.")
        subtitle.setStyleSheet("color: #888; font-size: 11px;")
        main_layout.addWidget(subtitle)

        tabs = QTabWidget()
        main_layout.addWidget(tabs)

        # ── Tab 1: Backend & Seguridad ──────────────────────────────────────
        t1 = QWidget()
        f1 = QFormLayout(t1)
        f1.setSpacing(10)

        self._url = QLineEdit()
        self._url.setPlaceholderText("https://molmont.duckdns.org")
        self._url.setText(os.environ.get("MATE_URL", "https://molmont.duckdns.org"))

        self._tls = QComboBox()
        self._tls.addItems(["true  (verificar TLS — recomendado)", "false  (desarrollo local con cert autofirmado)"])
        cur_tls = os.environ.get("MATE_TLS_VERIFY", "true").lower()
        self._tls.setCurrentIndex(1 if cur_tls == "false" else 0)

        self._api_key = QLineEdit()
        self._api_key.setPlaceholderText("sk-ant-…")
        self._api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self._api_key.setText(os.environ.get("ANTHROPIC_API_KEY", ""))

        f1.addRow("URL del backend *", self._url)
        f1.addRow("TLS / Certificado", self._tls)
        f1.addRow("Anthropic API Key *", self._api_key)
        tabs.addTab(t1, "Backend")

        # ── Tab 2: Mensajería ───────────────────────────────────────────────
        t2 = QWidget()
        f2 = QFormLayout(t2)
        f2.setSpacing(10)

        self._tg_token = QLineEdit()
        self._tg_token.setPlaceholderText("123456:AABBccdd…")
        self._tg_token.setEchoMode(QLineEdit.EchoMode.Password)
        self._tg_token.setText(os.environ.get("TELEGRAM_BOT_TOKEN", ""))

        self._tg_chat = QLineEdit()
        self._tg_chat.setPlaceholderText("-100123456789")
        self._tg_chat.setText(os.environ.get("TELEGRAM_CHAT_ID", ""))

        self._wa_num = QLineEdit()
        self._wa_num.setPlaceholderText("541161234567")
        self._wa_num.setText(os.environ.get("WHATSAPP_DEFAULT_NUMBER", ""))

        f2.addRow("Telegram Bot Token", self._tg_token)
        f2.addRow("Telegram Chat ID", self._tg_chat)
        f2.addRow("WhatsApp número", self._wa_num)
        tabs.addTab(t2, "Mensajería")

        # ── Tab 3: Spotify & Calendar ───────────────────────────────────────
        t3 = QWidget()
        f3 = QFormLayout(t3)
        f3.setSpacing(10)

        self._sp_id = QLineEdit()
        self._sp_id.setPlaceholderText("Client ID de Spotify")
        self._sp_id.setText(os.environ.get("SPOTIFY_CLIENT_ID", ""))

        self._sp_sec = QLineEdit()
        self._sp_sec.setPlaceholderText("Client Secret de Spotify")
        self._sp_sec.setEchoMode(QLineEdit.EchoMode.Password)
        self._sp_sec.setText(os.environ.get("SPOTIFY_CLIENT_SECRET", ""))

        gcal_row = QHBoxLayout()
        self._gcal = QLineEdit()
        self._gcal.setPlaceholderText("Ruta al client_secret.json")
        self._gcal.setText(os.environ.get("GOOGLE_CREDENTIALS_PATH", ""))
        browse_btn = QPushButton("…")
        browse_btn.setFixedWidth(32)
        browse_btn.clicked.connect(lambda: self._browse_gcal())
        gcal_row.addWidget(self._gcal)
        gcal_row.addWidget(browse_btn)

        self._tz = QLineEdit()
        self._tz.setPlaceholderText("America/Argentina/Buenos_Aires")
        self._tz.setText(os.environ.get("MATE_TIMEZONE", ""))

        f3.addRow("Spotify Client ID", self._sp_id)
        f3.addRow("Spotify Client Secret", self._sp_sec)
        f3.addRow("Google Calendar JSON", gcal_row)
        f3.addRow("Zona horaria", self._tz)
        tabs.addTab(t3, "Spotify / Calendar")

        # ── Botones ─────────────────────────────────────────────────────────
        self._status = QLabel("")
        self._status.setStyleSheet("color: #ff6666; font-size: 11px;")
        main_layout.addWidget(self._status)

        btn_row = QHBoxLayout()
        cancel_btn = QPushButton("Cancelar")
        save_btn = QPushButton("Guardar y cifrar")
        save_btn.setObjectName("save")
        save_btn.setMinimumWidth(160)
        btn_row.addStretch()
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(save_btn)
        main_layout.addLayout(btn_row)

        cancel_btn.clicked.connect(dlg.reject)
        save_btn.clicked.connect(lambda: self._save(dlg))

        self._dlg = dlg
        return dlg.exec()

    def _browse_gcal(self):
        from PyQt6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(
            self._dlg, "Seleccioná el archivo client_secret.json",
            str(Path.home()), "JSON (*.json)"
        )
        if path:
            self._gcal.setText(path)

    def _save(self, dlg):
        url     = self._url.text().strip()
        api_key = self._api_key.text().strip()

        if not url:
            self._status.setText("URL del backend es obligatoria.")
            return
        if not api_key:
            self._status.setText("Anthropic API Key es obligatoria.")
            return

        tls_val = "false" if self._tls.currentIndex() == 1 else "true"

        cfg = {
            "MATE_URL":                url,
            "MATE_TLS_VERIFY":         tls_val,
            "ANTHROPIC_API_KEY":       api_key,
            "TELEGRAM_BOT_TOKEN":      self._tg_token.text().strip(),
            "TELEGRAM_CHAT_ID":        self._tg_chat.text().strip(),
            "WHATSAPP_DEFAULT_NUMBER": self._wa_num.text().strip(),
            "SPOTIFY_CLIENT_ID":       self._sp_id.text().strip(),
            "SPOTIFY_CLIENT_SECRET":   self._sp_sec.text().strip(),
            "GOOGLE_CREDENTIALS_PATH": self._gcal.text().strip(),
            "MATE_TIMEZONE":           self._tz.text().strip(),
        }
        # quitar claves vacías para no sobreescribir valores ya en env
        cfg = {k: v for k, v in cfg.items() if v}

        try:
            from secure_config import save_config
            save_config(cfg)
            # inyectar inmediatamente en el proceso actual
            for k, v in cfg.items():
                os.environ[k] = v
            dlg.accept()
        except Exception as e:
            self._status.setText(f"Error al cifrar: {e}")


# ─── Punto de entrada standalone ─────────────────────────────────────────────

if __name__ == "__main__":
    ok = run_setup(force=True)
    print("Configuración guardada." if ok else "Cancelado.")
