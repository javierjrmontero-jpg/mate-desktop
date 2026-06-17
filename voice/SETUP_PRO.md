# MATE PRO — Guía de Configuración

Todas las features PRO son opcionales. MATE funciona sin ellas; las que no estén configuradas responden con instrucciones de configuración por voz.

---

## 1. Memoria Persistente

**No requiere configuración.** Se activa automáticamente.

Comandos disponibles:
- *"recuerda que mi nombre es Javier"*
- *"recuerda que trabajo en IT"*
- *"¿qué sabes de mí?"*
- *"¿cuál es mi nombre?"*
- *"olvida que [...]"*

Los datos se guardan en `.mate_memory.json` junto al ejecutable y se inyectan automáticamente como contexto en cada conversación con el API.

---

## 2. Dev Agent (Python / PowerShell)

**No requiere configuración.** Se activa automáticamente.

Comandos disponibles:
- *"ejecutá el último script"*
- *"corré el script anterior"*
- *"listá los scripts guardados"*
- *"abrí la carpeta de scripts"*
- *"ejecutá PowerShell [comando]"*

Los scripts se guardan en `mate_scripts/` junto al ejecutable.

El MATE API puede generar código automáticamente usando el marcador `[RUN_PY:código]` en su respuesta — MATE lo ejecuta y habla el resultado.

---

## 3. Ghost Operator (Control de teclado y mouse)

**No requiere configuración.** Se activa automáticamente vía pyautogui.

Comandos disponibles:
- *"scrolleá abajo / arriba"*
- *"nueva pestaña"* / *"cerrá la pestaña"* / *"reabrir pestaña"* / *"siguiente pestaña"*
- *"recargá la página"*
- *"volvé atrás"* / *"avanzá"*
- *"copiá"* / *"pegá"* / *"cortá"* / *"deshacer"* / *"rehacer"*
- *"seleccioná todo"*
- *"mostrá el escritorio"*
- *"bloqueá la pantalla"*
- *"escribí [texto]"* → escribe texto en el campo activo
- *"abrí https://..."* → navega a una URL en el navegador activo
- *"buscá en el navegador [consulta]"* → abre nueva pestaña y busca

---

## 4. Telegram

### Configuración
1. En Telegram, buscar **@BotFather** → `/newbot` → seguir pasos → copiar el token
2. Escribirle cualquier mensaje a tu nuevo bot
3. Abrir en navegador: `https://api.telegram.org/bot<TOKEN>/getUpdates`
4. Copiar el valor de `"id"` dentro del objeto `"chat"`
5. Agregar al `.env`:
   ```
   TELEGRAM_BOT_TOKEN=1234567890:ABCDEFxxxxxxxxxxxxxx
   TELEGRAM_CHAT_ID=123456789
   ```

### Comandos disponibles
- *"mandá un mensaje por telegram que: [mensaje]"*
- *"enviá por telegram: [mensaje]"*
- *"mensajes de telegram"* / *"qué llegó por telegram"*

---

## 5. WhatsApp

### Configuración
1. Abrir Chrome y loguearse en **web.whatsapp.com**
2. Mantener esa pestaña abierta cuando uses el comando
3. Agregar al `.env`:
   ```
   WHATSAPP_DEFAULT_NUMBER=541161234567
   ```
   (código país + área + número, sin +, sin espacios)
4. Instalar dependencia: `pip install pywhatkit`

### Comandos disponibles
- *"mandá por whatsapp: [mensaje]"*
- *"enviá un whatsapp: [mensaje]"*
- *"mandá un whatsapp al número 54116...: [mensaje]"*

> **Nota:** WhatsApp se envía via WhatsApp Web. Chrome debe estar abierto con la sesión activa.

---

## 6. Google Calendar

### Configuración
1. Ir a https://console.cloud.google.com → Crear proyecto
2. API y Servicios → Biblioteca → buscar "Google Calendar API" → Habilitar
3. Credenciales → Crear credenciales → ID de cliente OAuth → Tipo: **App de escritorio**
4. Descargar el JSON → guardarlo en cualquier carpeta (ej: `C:\MATE\client_secret.json`)
5. Agregar al `.env`:
   ```
   GOOGLE_CREDENTIALS_PATH=C:\MATE\client_secret.json
   MATE_TIMEZONE=America/Argentina/Buenos_Aires
   ```
6. Ejecutar el script de autorización **una sola vez**:
   ```
   python mate_calendar_auth.py
   ```
   → Se abre el navegador para autorizar. El token queda en `.gcal_token.json`.
7. Instalar dependencias:
   ```
   pip install google-auth-oauthlib google-auth-httplib2 google-api-python-client
   ```

> **Sin Google Calendar configurado:** los eventos se guardan en `.mate_calendar.json` (local, funciona igual).

### Comandos disponibles
- *"¿qué tengo hoy?"* / *"agenda de hoy"*
- *"¿qué tengo esta semana?"* / *"agenda semanal"*
- *"agendá [evento] mañana a las 15"*
- *"agendá reunión el viernes a las 10"*
- *"agendá [evento] el 25/06 a las 9"*
- *"borrá el evento [nombre]"*

---

## 7. Briefing Matutino

**No requiere configuración.** Combina clima + agenda + recordatorios + noticias.

Comandos disponibles:
- *"dame el briefing"*
- *"briefing del día"*
- *"resumen de la mañana"*
- *"estado rápido"* → versión corta con sistema + clima

---

## Resumen de variables .env PRO

```env
# Telegram
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=

# WhatsApp
WHATSAPP_DEFAULT_NUMBER=

# Google Calendar
GOOGLE_CREDENTIALS_PATH=
MATE_TIMEZONE=America/Argentina/Buenos_Aires
```

---

## Verificación

Correr el smoke test para confirmar que todo está OK:
```
python mate_pro_test.py
```
