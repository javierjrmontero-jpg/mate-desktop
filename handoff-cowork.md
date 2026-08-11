# MATE — Resumen de Traspaso de Sesión
**Fecha:** 19/06/2026 | **Repo desktop:** `D:\mate-desktop` | **Branch:** `main`

---

## 1. Estado Actual del Proyecto

MATE está en **Fase PRO completada en código**, pendiente de build del EXE final.

- Commits aplicados: `c9da114` (PRO batch 1) y `fe64c7a` (PRO batch 2)
- El `build_exe.ps1` fue corregido pero el fix tiene un commit pendiente (lock de git en Windows). El archivo en disco es correcto.
- El EXE **no fue rebuildeado** — el usuario fue a correr `.\build_exe.ps1` al final de la sesión.

---

## 2. Objetivo General del Proyecto

MATE (Motor de Asistencia Técnica e Inteligencia) es un asistente personal estilo Jarvis que corre localmente en Windows. Tiene:
- Un **orbe flotante** PyQt6 con wake word "Oye MATE", STT (Whisper), TTS (SAPI5), barge-in
- **Herramientas locales** que ejecutan comandos sin llamar al API
- Un **backend FastAPI** en VM (RHEL 10) en `https://molmont.duckdns.org` para conversación con Claude
- Distribución como **EXE PyInstaller** portable entre PCs Windows

---

## 3. Funcionalidades Implementadas

### Orbe (mate_orb.py)
- Wake word custom "Oye MATE" (OpenWakeWord, modelo `oye_mate.onnx`)
- STT: faster-whisper medium, filtro `avg_logprob > -1.0` + `no_speech_prob < 0.5`
- TTS: `win32com.client.Dispatch("SAPI.SpVoice")` con `SVSFlagsAsync` (pyttsx3 tenía bug en frozen PyInstaller)
- Barge-in durante TTS
- Conversación continua sin re-activar wake word
- Audio cross-PC: detección `NATIVE_SR` + resampling `scipy.signal.resample_poly`
- Inyección de contexto de memoria en cada llamada al API
- Hook `[RUN_PY:código]` en respuestas del API → ejecución local de Python

### Herramientas locales (tools/)
| Módulo | Qué hace |
|--------|----------|
| `system_control.py` | Tiempo, CPU/RAM/disco, volumen, brillo, apps, ventanas, modo oscuro, fondo |
| `web_tools.py` | Clima (Open-Meteo), noticias (RSS), búsqueda (DDG), YouTube, visión (Claude Vision) |
| `spotify_tools.py` | Control Spotify API + fallback web player |
| `file_tools.py` | Archivos y carpetas por voz |
| `notes_tools.py` | Notas y metas en JSON local |
| `reminder_tools.py` | Recordatorios con timer |
| `memory_tools.py` ★ | Memoria persistente cross-session (`.mate_memory.json`) |
| `dev_agent_tools.py` ★ | Ejecutar Python/PowerShell, carpeta `mate_scripts/` |
| `ghost_operator.py` ★ | Mouse, teclado, scroll, pestañas, hotkeys por voz |
| `messaging_tools.py` ★ | Telegram Bot API + WhatsApp via pywhatkit |
| `calendar_tools.py` ★ | Google Calendar + fallback JSON local |
| `briefing_tools.py` ★ | Briefing matutino (clima+agenda+recordatorios+noticias) |

★ = nuevo en Fase PRO

### Backend (VM)
- FastAPI con Claude claude-sonnet-4-5, herramientas de calendario/email/tareas
- SYSTEM_PROMPT actualizado con sección Dev Agent `[RUN_PY:]`
- Autenticación JWT, Google Calendar OAuth, Outlook OAuth2, IMAP/SMTP

---

## 4. Archivos Modificados o Creados

### En `D:\mate-desktop\voice\`
```
mate_orb.py              — modificado: memoria injection + [RUN_PY:] hook + TTS win32com
mate_orb.spec            — modificado: collect_all/submodules + PRO hiddenimports
build_exe.ps1            — modificado: paso 1b instala deps PRO (fix ErrorActionPreference pendiente de commit)
commit_pro.ps1           — nuevo: limpia git locks y commitea batch 2

tools/memory_tools.py    — nuevo (PRO)
tools/dev_agent_tools.py — nuevo (PRO)
tools/ghost_operator.py  — nuevo (PRO)
tools/messaging_tools.py — nuevo (PRO)
tools/calendar_tools.py  — nuevo (PRO)
tools/briefing_tools.py  — nuevo (PRO)
tools/system_control.py  — modificado: +registro de todos los comandos PRO

mate_calendar_auth.py    — nuevo: auth OAuth Google Calendar
mate_pro_test.py         — nuevo: smoke test de todos los módulos PRO
SETUP_PRO.md             — nuevo: guía de configuración PRO
.env.example             — modificado: variables Telegram/WhatsApp/Google Calendar
```

### En `C:\Users\jmontero\OneDrive\0.0.3.Proyecto MATE\Proyecto IA Agentica\`
```
client.py                — modificado: SYSTEM_PROMPT con sección Dev Agent [RUN_PY:]
```
> ⚠️ Este archivo necesita ser desplegado en la VM para que el backend conozca el marcador `[RUN_PY:]`.

---

## 5. Cambios Pendientes

| # | Qué | Cómo |
|---|-----|------|
| 1 | Commitear el fix de `build_exe.ps1` | Desde PowerShell: `git add build_exe.ps1 commit_pro.ps1 && git commit -m "fix(build): ErrorActionPreference deps PRO"` (después de que git libere el lock) |
| 2 | Hacer el build del EXE | `.\build_exe.ps1` (desde la raíz del repo con el venv activo) |
| 3 | Desplegar `client.py` en la VM | SCP desde Windows a `~/aiden/app/services/llm/client.py` en la VM, luego `docker compose up -d backend` |
| 4 | Configurar variables PRO en `.env` | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `WHATSAPP_DEFAULT_NUMBER`, `GOOGLE_CREDENTIALS_PATH` |
| 5 | Auth Google Calendar (si se usa) | Ejecutar `python mate_calendar_auth.py` en la PC destino una vez |

---

## 6. Errores / Problemas Abiertos

| Problema | Causa | Estado |
|----------|-------|--------|
| `git commit` falla desde el sandbox Linux | `.git/HEAD.lock` y `.git/index.lock` generados por PowerShell en Windows | El script `commit_pro.ps1` los limpia automáticamente — **usar siempre ese script** para commitear desde Cowork |
| `build_exe.ps1` abortaba en paso 1b | `$ErrorActionPreference = "Stop"` + `2>$null` con pip | **Corregido** en disco. Commit pendiente |
| Spotify: token no disponible en otra PC | `.spotify_cache` no copiado | Copiar `.spotify_cache` a la PC destino O ejecutar `mate_spotify_auth.py` |
| WhatsApp requiere Chrome abierto | pywhatkit usa WhatsApp Web | Documentado en SETUP_PRO.md |

---

## 7. Decisiones Técnicas Tomadas

| Decisión | Razón |
|----------|-------|
| TTS via `win32com SAPI5` (no pyttsx3) | pyttsx3 `runAndWait()` retorna inmediatamente en apps frozen PyInstaller — bug conocido |
| `collect_all("openwakeword")` + `collect_submodules("scipy", "sklearn")` en spec | Elimina el whack-a-mole de hiddenimports individuales; cubre toda la cadena de dependencias |
| `NATIVE_SR` detection + resampling | Dispositivos WASAPI pueden no soportar 16000 Hz (ej: Realtek soporta solo 48000 Hz) |
| Paths frozen: `sys.executable.parent` (no `__file__`) | En frozen PyInstaller, `__file__` apunta al temp dir de extracción |
| Whisper sin `initial_prompt`, con filtro logprob | `initial_prompt` causaba hallucinations; filtro `avg_logprob > -1.0` las elimina |
| `[RUN_PY:código]` como marcador en respuestas del API | Permite al backend generar código para ejecución local sin modificar el protocolo SSE |
| Memoria inyectada como prefijo en mensajes VOZ | El contexto del usuario enriquece cada respuesta sin requerir cambios en el backend |
| Google Calendar con fallback local JSON | Funciona sin credenciales; `.mate_calendar.json` junto al EXE |
| Telegram via Bot API (no cliente oficial) | No requiere app instalada, funciona con solo un token HTTP |

---

## 8. Próximos Pasos Recomendados

**Inmediatos (antes de distribuir el EXE):**
1. Correr `.\build_exe.ps1` — genera `voice\dist\MATE\MATE.exe`
2. Probar el EXE: copiar la carpeta `dist\MATE\` a otra PC, crear `.env` con las variables, ejecutar `MATE.exe`
3. Desplegar `client.py` en la VM (SCP + `docker compose up -d backend`)

**Mejoras futuras sugeridas:**
- **Dictation mode:** "dictame un mensaje" → MATE escribe todo lo que el usuario habla hasta "listo"
- **Vision + Ghost Operator:** combinar screenshot con Claude Vision para que MATE haga click en elementos por nombre ("click en el botón Aceptar")
- **Spotify en otra PC:** flujo automático para copiar/sincronizar `.spotify_cache`
- **Multi-PC sync:** sincronizar `.mate_memory.json` y `.mate_calendar.json` via OneDrive/Dropbox
- **Notificaciones Telegram bidireccionales:** recibir comandos por Telegram además de enviar mensajes

---

## 9. Comandos Importantes

```powershell
# Activar el entorno virtual
.\voice\mate-wakeword-env\Scripts\Activate.ps1

# Build del EXE
.\build_exe.ps1

# Commitear después de cambios (limpia git locks primero)
.\commit_pro.ps1

# Auth Spotify (una vez por PC)
python voice\mate_spotify_auth.py

# Auth Google Calendar (una vez por PC)
python voice\mate_calendar_auth.py

# Smoke test de módulos PRO (sin hardware de audio)
cd voice && python mate_pro_test.py

# Ejecutar el orbe directamente (sin build)
python voice\mate_orb.py

# Desplegar backend en VM (desde Windows via SCP)
scp voice/tools/*.py user@vm:~/aiden/app/
# O en la VM:
docker compose up -d backend
```

---

## 10. Advertencias — Archivos que NO Deben Modificarse Sin Cuidado

| Archivo | Riesgo |
|---------|--------|
| `voice/mate_orb.spec` | Cambios en `excludes` pueden romper scipy/sklearn en runtime. No agregar `scipy`, `sklearn`, `openwakeword` a excludes. |
| `voice/mate_orb.py` — sección audio (`NATIVE_SR`, `_to_16k`, `_capture`) | La lógica de resampling es frágil. Cambiar blocksize o SR sin actualizar las proporciones causa `PortAudio Invalid sample rate`. |
| `voice/mate_orb.py` — `_speak()` | `SVSFlagsAsync = 1` es crítico. Sin él el TTS bloquea el thread. |
| `.mate_token` junto al EXE | Token de autenticación del backend. No commitear. |
| `.spotify_cache` junto al EXE | Token Spotify. No commitear. Copiar manualmente entre PCs. |
| `voice/models/oye_mate.onnx` | Modelo custom de wake word. No sobreescribir con modelos base de openwakeword. |
| `client.py` en el backend (OneDrive) | Contiene el SYSTEM_PROMPT completo. Cambios sin deploy a la VM no tienen efecto. |
