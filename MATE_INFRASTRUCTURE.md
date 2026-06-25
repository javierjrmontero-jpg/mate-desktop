# MATE — Infraestructura existente
> Documento de referencia para integración con Home Assistant y plataformas domóticas.
> Generado: 2026-06-24

---

## 1. Visión general

MATE (Motor de Asistencia Técnica e Inteligencia) es un asistente de voz + app Android + backend FastAPI.
Está estructurado en tres repositorios independientes:

| Repositorio | Tecnología | Descripción | Equipamiento
|---|---|---|
| `MATE-Desktop` | Python 3.12 + PyQt6 | Asistente de escritorio Windows (orbe, wake word, STT, TTS) | Equipo físico windows 11
| `AIDEN-Backend` | FastAPI + SQLite | API central, LLM, memoria, domótica | VM RHEL10 montada sobre vmware en el equipo windows 11
| `MATE-Android` | Flutter 3 | Cliente Android delgado (STT nativo, TTS, SSE streaming) |

---

## 2. Backend (AIDEN-Backend)

### 2.1 Servidor

- **Framework:** FastAPI (Python)
- **Base de datos:** SQLite (`data/db/aiden.db`)
- **Host de producción:** `molmont.duckdns.org` (RHEL VM)
- **Puerto:** `8000` (HTTP) / `8443` (HTTPS self-signed → en migración a Let's Encrypt)
- **Prefijo global de rutas:** `/api/v1`

### 2.2 Autenticación

- **Tipo:** JWT Bearer Token
- **Login:** `POST /api/v1/auth/login` → `{ email, password }` → `{ access_token }`
- **Expiración:** 24 horas (configurable `JWT_EXPIRE_HOURS`)
- **Todos los endpoints** (excepto `/`, `/health`, `/api/v1/auth/login`) requieren header:
  ```
  Authorization: Bearer <token>
  ```

### 2.3 Endpoints existentes

| Método | Ruta | Descripción |
|---|---|---|
| POST | `/api/v1/auth/login` | Login, retorna JWT |
| POST | `/api/v1/chat` | Chat con LLM (SSE streaming) |
| GET/POST | `/api/v1/conversations` | Historial de conversaciones |
| GET/POST | `/api/v1/memories` | Memorias persistentes del usuario |
| POST | `/api/v1/transcribe` | STT con Whisper (audio → texto) |
| GET/POST | `/api/v1/calendar` | Integración Google Calendar |
| POST | `/api/v1/briefing` | Briefing diario |
| POST | `/api/v1/agent` | Agente autónomo |
| GET/POST | `/api/v1/tasks` | Gestión de tareas |
| POST | `/api/v1/email` | Lectura/envío de emails |
| **GET** | **`/api/v1/domotica/devices`** | **Lista todos los dispositivos domóticos** |
| **GET** | **`/api/v1/domotica/sensors`** | **Solo sensores (temperatura, humedad, etc.)** |
| **POST** | **`/api/v1/domotica/control`** | **Controlar un dispositivo** |

### 2.4 Endpoint de domótica — detalle

#### `GET /api/v1/domotica/devices`
Retorna todos los dispositivos de todas las plataformas configuradas.

**Response:**
```json
[
  {
    "id": "light.living_room",
    "name": "Luz del living",
    "type": "light",
    "state": { "state": "on", "on": true, "brightness": 200 },
    "platform": "ha",
    "is_on": true,
    "friendly_state": "encendido"
  },
  {
    "id": "sensor.temperature_bedroom",
    "name": "Temperatura dormitorio",
    "type": "sensor",
    "state": { "value": "22.5", "unit": "°C" },
    "platform": "ha",
    "is_on": false,
    "friendly_state": "22.5 °C"
  }
]
```

**Tipos de dispositivo:** `light` | `switch` | `sensor` | `scene` | `climate` | `cover`  
**Plataformas:** `ha` | `ewelink` | `tuya`

#### `GET /api/v1/domotica/sensors`
Igual que `/devices` pero filtrado solo a `type == "sensor"`.

#### `POST /api/v1/domotica/control`
**Body:**
```json
{
  "device": "Luz del living",
  "action": "on",
  "params": {}
}
```

- `device`: nombre parcial o ID exacto del dispositivo
- `action`: `on` | `off` | `toggle` | `scene`
- `params`: opcional, para brightness u otros parámetros HA

**Response:**
```json
{ "result": "Luz del living encendido." }
```

---

## 3. Integración con Home Assistant

### 3.1 Cómo conecta MATE con HA

MATE se comunica con Home Assistant a través de la **REST API nativa de HA**.  
No usa MQTT ni websockets (por ahora). La conexión es directa desde el backend MATE → HA.

```
MATE-Desktop (voz) ──► AIDEN-Backend ──► Home Assistant REST API
MATE-Android (app) ──► AIDEN-Backend ──/
```

### 3.2 Variables de entorno requeridas

Configurar en `.env` del backend (`AIDEN-Backend/`) o en el Setup Wizard de MATE-Desktop:

```env
# Home Assistant
HA_URL=http://192.168.1.100:8123   # URL local de HA (o externa con HTTPS)
HA_TOKEN=eyJhbGci...               # Long-Lived Access Token

# eWeLink (opcional)
EWELINK_EMAIL=tu@email.com
EWELINK_PASSWORD=contraseña
EWELINK_REGION=eu                  # eu | us | cn

# Tuya / Linda Smart (opcional)
TUYA_ACCESS_ID=xxxxxxxxxxxx
TUYA_ACCESS_SECRET=yyyyyyyyyyyy
TUYA_REGION=eu                     # eu | us | cn
```

### 3.3 Cómo obtener el Long-Lived Access Token de HA

1. Abrí Home Assistant en el navegador
2. Clic en tu **perfil** (esquina inferior izquierda)
3. Scrolleá hasta **"Long-lived access tokens"**
4. Clic en **"Create Token"** → dale un nombre (ej: `MATE`)
5. Copiá el token — **solo se muestra una vez**

### 3.4 Entidades que MATE consume de HA

MATE lee **todos los estados** de HA via `GET /api/states` y filtra automáticamente:

**Dominios incluidos:**
- `light.*` → tipo `light`
- `switch.*` → tipo `switch`
- `sensor.*` → tipo `sensor`
- `binary_sensor.*` → tipo `sensor`
- `scene.*` → tipo `scene`
- `climate.*` → tipo `climate`
- `cover.*` → tipo `cover`
- `fan.*` → tipo `switch`

**Dominios excluidos automáticamente:**
- `automation.*`, `input_*`, `person.*`, `zone.*`, `sun.*`, `weather.*`

### 3.5 Servicios HA que MATE invoca

| Acción MATE | Servicio HA llamado |
|---|---|
| `action: "on"` | `<domain>/turn_on` |
| `action: "off"` | `<domain>/turn_off` |
| `action: "toggle"` | `<domain>/toggle` |
| `action: "scene"` | `scene/turn_on` |
| Brillo | `light/turn_on` con `brightness: 0-255` |

### 3.6 Ejemplo de llamada directa a HA desde MATE

```python
# Encender light.living_room
POST http://<HA_URL>/api/services/light/turn_on
Authorization: Bearer <HA_TOKEN>
Content-Type: application/json

{ "entity_id": "light.living_room" }
```

---

## 4. Comandos de voz disponibles (MATE-Desktop)

El módulo `system_control.py` detecta estas frases en español:

| Frase de ejemplo | Función |
|---|---|
| "encendé la luz del living" | `domotica_on("luz del living")` |
| "apagá el ventilador" | `domotica_off("ventilador")` |
| "toggle el enchufe" | `domotica_toggle("enchufe")` |
| "qué temperatura hay" | `domotica_sensors()` |
| "listá los dispositivos domóticos" | `domotica_list()` |
| "activá la escena cine" | `domotica_scene("cine")` |
| "brillo al 50%" | `domotica_brightness("luz", 50)` |

---

## 5. Estructura de archivos relevantes

```
MATE-Desktop/
└── voice/
    └── tools/
        └── domotica_tools.py        # Adaptadores HA + eWeLink + Tuya, funciones de voz

AIDEN-Backend/
└── backend/app/
    ├── api/
    │   └── domotica.py              # Router FastAPI: /devices, /sensors, /control
    └── services/
        └── domotica/
            └── service.py           # Lógica async: get_all_devices, control_device

MATE-Android/
└── lib/
    ├── screens/
    │   └── domotica_screen.dart     # UI: lista de dispositivos con toggle
    └── services/
        └── domotica_service.dart    # HTTP client → AIDEN-Backend /domotica/*
```

---

## 6. Flujo de datos completo

```
Usuario habla "encendé la luz del living"
        │
        ▼
MATE-Desktop (faster-whisper STT)
        │  texto
        ▼
system_control.detect_and_execute()
        │  regex match → domotica_on("luz del living")
        ▼
domotica_tools.DomoticaService.control_by_name()
        │  busca en caché / refresca dispositivos
        ▼
HomeAssistantAdapter.control("light.living_room", "on")
        │  POST /api/services/light/turn_on
        ▼
Home Assistant
        │
        ▼
"Luz del living encendido." → TTS → usuario
```

**Desde Android:**
```
Tap en orbe → STT nativo
        │
        ▼
ApiService.chat() → POST /api/v1/chat (SSE streaming)
        │  AIDEN-Backend procesa la intención y llama a domotica si corresponde
        ▼
DomoticaScreen → DomoticaService.control() → POST /api/v1/domotica/control
        │
        ▼
HomeAssistantAdapter → HA REST API
```

---

## 7. Requerimientos para implementación HA completa

### Mínimo requerido en Home Assistant

- HA con **REST API habilitada** (está habilitada por defecto en HA Core ≥ 0.7)
- **Long-Lived Access Token** generado (ver sección 3.3)
- HA accesible desde la red donde corre AIDEN-Backend (misma LAN o VPN)
- Si HA usa HTTPS self-signed: MATE ya tiene `verify=False` en las llamadas HTTP

### Opcional / mejoras futuras

- **HA WebSocket API** para notificaciones proactivas en tiempo real (temperatura, alertas de sensores)
- **HA MQTT broker** para integración de dispositivos Zigbee/Z-Wave no soportados por eWeLink/Tuya
- **HA Companion App** en Android en lugar de la app MATE-Android para control nativo

### Configuración mínima de `.env` para activar HA

```env
HA_URL=http://192.168.x.x:8123
HA_TOKEN=<long_lived_token>
```

Con solo estas dos variables MATE Desktop y el backend quedan operativos con HA.  
eWeLink y Tuya son opcionales e independientes.

---

## 8. Pendientes de implementación (roadmap domótica)

| Item | Prioridad | Estado |
|---|---|---|
| Credenciales domótica en Setup Wizard (mate_setup.py) | ALTA | Pendiente |
| HA WebSocket para alertas proactivas | MEDIA | Pendiente |
| Monitoreo de sensores → notificación push Android | MEDIA | Pendiente |
| Control de brillo desde pantalla Android | BAJA | Pendiente |
| Soporte escenas desde pantalla Android | BAJA | Pendiente |
