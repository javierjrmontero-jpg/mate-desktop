#!/usr/bin/env python3
"""
MATE Domótica Tools
Capa de abstracción para Home Assistant, eWeLink y Tuya/Linda Smart.
Los tokens se configuran en .env o en el Setup Wizard.
"""
import os
import json
import logging
import requests
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


# ─── Modelo unificado ────────────────────────────────────────────────────────

@dataclass
class Device:
    id:       str
    name:     str
    type:     str           # light | switch | sensor | scene | climate | cover
    state:    dict = field(default_factory=dict)
    platform: str = ""      # ha | ewelink | tuya

    @property
    def is_on(self) -> bool:
        return bool(self.state.get("on") or self.state.get("state") == "on")

    @property
    def friendly_state(self) -> str:
        if self.type == "sensor":
            v = self.state.get("value", "")
            u = self.state.get("unit", "")
            return f"{v} {u}".strip()
        return "encendido" if self.is_on else "apagado"


# ─── Adaptador Home Assistant ─────────────────────────────────────────────────

class HomeAssistantAdapter:
    def __init__(self):
        self.url   = os.environ.get("HA_URL", "").rstrip("/")
        self.token = os.environ.get("HA_TOKEN", "")

    @property
    def available(self) -> bool:
        return bool(self.url and self.token)

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}

    def _get(self, path: str) -> Any:
        r = requests.get(f"{self.url}/api{path}", headers=self._headers(), timeout=8, verify=False)
        r.raise_for_status()
        return r.json()

    def _post(self, path: str, data: dict = None) -> Any:
        r = requests.post(f"{self.url}/api{path}", headers=self._headers(),
                          json=data or {}, timeout=8, verify=False)
        r.raise_for_status()
        return r.json()

    def get_devices(self) -> list[Device]:
        if not self.available:
            return []
        try:
            states = self._get("/states")
            devices = []
            skip = ("automation.", "input_", "person.", "zone.", "sun.", "weather.")
            for s in states:
                eid = s["entity_id"]
                if any(eid.startswith(p) for p in skip):
                    continue
                domain = eid.split(".")[0]
                dtype = {
                    "light": "light", "switch": "switch", "sensor": "sensor",
                    "binary_sensor": "sensor", "scene": "scene",
                    "climate": "climate", "cover": "cover", "fan": "switch",
                }.get(domain, "switch")
                attrs = s.get("attributes", {})
                state_val = s.get("state", "off")
                dstate = {"state": state_val, "on": state_val == "on"}
                if dtype == "sensor":
                    dstate = {"value": state_val, "unit": attrs.get("unit_of_measurement", "")}
                elif dtype == "light":
                    dstate["brightness"] = attrs.get("brightness")
                devices.append(Device(
                    id=eid, name=attrs.get("friendly_name", eid),
                    type=dtype, state=dstate, platform="ha"
                ))
            return devices
        except Exception as e:
            logger.warning(f"HA get_devices error: {e}")
            return []

    def control(self, entity_id: str, action: str, params: dict = None) -> str:
        if not self.available:
            return "Home Assistant no configurado."
        domain = entity_id.split(".")[0]
        service_map = {
            "on":     f"{domain}/turn_on",
            "off":    f"{domain}/turn_off",
            "toggle": f"{domain}/toggle",
            "scene":  "scene/turn_on",
        }
        service = service_map.get(action, f"{domain}/{action}")
        data = {"entity_id": entity_id, **(params or {})}
        try:
            self._post(f"/services/{service}", data)
            name = entity_id.split(".")[-1].replace("_", " ")
            verb = {"on": "encendido", "off": "apagado", "toggle": "cambiado"}.get(action, action)
            return f"{name.capitalize()} {verb}."
        except Exception as e:
            return f"Error controlando {entity_id}: {e}"

    def get_sensor(self, entity_id: str) -> str:
        try:
            s = self._get(f"/states/{entity_id}")
            attrs = s.get("attributes", {})
            name  = attrs.get("friendly_name", entity_id)
            val   = s.get("state", "?")
            unit  = attrs.get("unit_of_measurement", "")
            return f"{name}: {val} {unit}".strip()
        except Exception as e:
            return f"No pude leer {entity_id}: {e}"


# ─── Adaptador eWeLink ────────────────────────────────────────────────────────

class eWeLinkAdapter:
    _REGIONS = {"eu": "eu-apia.coolkit.cc", "us": "us-apia.coolkit.cc", "cn": "cn-apia.coolkit.cc"}

    def __init__(self):
        self.email  = os.environ.get("EWELINK_EMAIL", "")
        self.passwd = os.environ.get("EWELINK_PASSWORD", "")
        self.region = os.environ.get("EWELINK_REGION", "eu")
        self._token: str = ""
        self._devices: list[dict] = []

    @property
    def available(self) -> bool:
        return bool(self.email and self.passwd)

    def _base(self) -> str:
        host = self._REGIONS.get(self.region, self._REGIONS["eu"])
        return f"https://{host}"

    def _login(self) -> bool:
        try:
            r = requests.post(f"{self._base()}/v2/user/login", json={
                "email": self.email, "password": self.passwd,
                "countryCode": "+54",
            }, headers={"Content-Type": "application/json", "X-CK-Appid": "YzfeftUVcZ6twZw1OoVKPRFYTrGEg01Q"}, timeout=10)
            data = r.json()
            if data.get("error") == 0:
                self._token = data["data"]["at"]
                return True
        except Exception as e:
            logger.warning(f"eWeLink login error: {e}")
        return False

    def _auth_headers(self) -> dict:
        return {"Authorization": f"Bearer {self._token}", "Content-Type": "application/json"}

    def get_devices(self) -> list[Device]:
        if not self.available:
            return []
        if not self._token and not self._login():
            return []
        try:
            r = requests.get(f"{self._base()}/v2/device/thing",
                             headers=self._auth_headers(), timeout=10)
            data = r.json()
            devices = []
            for item in data.get("data", {}).get("thingList", []):
                d = item.get("itemData", {})
                params = d.get("params", {})
                is_on = params.get("switch", "off") == "on"
                devices.append(Device(
                    id=d.get("deviceid", ""),
                    name=d.get("name", "Dispositivo eWeLink"),
                    type="switch",
                    state={"state": "on" if is_on else "off", "on": is_on},
                    platform="ewelink"
                ))
            self._devices = [d.__dict__ for d in devices]
            return devices
        except Exception as e:
            logger.warning(f"eWeLink get_devices error: {e}")
            return []

    def control(self, device_id: str, action: str, params: dict = None) -> str:
        if not self.available:
            return "eWeLink no configurado."
        if not self._token and not self._login():
            return "No pude conectar a eWeLink."
        switch_val = "on" if action == "on" else "off"
        try:
            r = requests.post(f"{self._base()}/v2/device/thing/status",
                              headers=self._auth_headers(),
                              json={"type": 1, "id": device_id, "params": {"switch": switch_val}},
                              timeout=10)
            if r.json().get("error") == 0:
                return f"Dispositivo {switch_val}."
            return f"Error eWeLink: {r.json().get('msg', 'desconocido')}"
        except Exception as e:
            return f"Error eWeLink: {e}"


# ─── Adaptador Tuya / Linda Smart ─────────────────────────────────────────────

class TuyaAdapter:
    def __init__(self):
        self.access_id     = os.environ.get("TUYA_ACCESS_ID", "")
        self.access_secret = os.environ.get("TUYA_ACCESS_SECRET", "")
        self.region        = os.environ.get("TUYA_REGION", "eu")
        self._token: str   = ""
        self._token_expiry = 0

    @property
    def available(self) -> bool:
        return bool(self.access_id and self.access_secret)

    def _base(self) -> str:
        hosts = {"eu": "openapi.tuyaeu.com", "us": "openapi.tuyaus.com", "cn": "openapi.tuyacn.com"}
        return f"https://{hosts.get(self.region, hosts['eu'])}"

    def _sign(self, t: str, token: str = "") -> str:
        import hashlib, hmac, time
        s = f"{self.access_id}{token}{t}"
        return hmac.new(self.access_secret.encode(), s.encode(), hashlib.sha256).hexdigest().upper()

    def _get_token(self) -> bool:
        import time
        t = str(int(time.time() * 1000))
        try:
            r = requests.get(f"{self._base()}/v1.0/token?grant_type=1",
                             headers={"client_id": self.access_id, "sign": self._sign(t),
                                      "t": t, "sign_method": "HMAC-SHA256"}, timeout=10)
            data = r.json()
            if data.get("success"):
                self._token = data["result"]["access_token"]
                self._token_expiry = int(time.time()) + data["result"].get("expire_time", 7200)
                return True
        except Exception as e:
            logger.warning(f"Tuya token error: {e}")
        return False

    def _headers(self) -> dict:
        import time
        t = str(int(time.time() * 1000))
        if not self._token or time.time() >= self._token_expiry:
            self._get_token()
        return {"client_id": self.access_id, "access_token": self._token,
                "sign": self._sign(t, self._token), "t": t, "sign_method": "HMAC-SHA256"}

    def get_devices(self) -> list[Device]:
        if not self.available:
            return []
        try:
            r = requests.get(f"{self._base()}/v1.0/iot-01/associated-users/devices",
                             headers=self._headers(), timeout=10)
            data = r.json()
            devices = []
            for d in data.get("result", {}).get("devices", []):
                is_on = d.get("online", False)
                devices.append(Device(
                    id=d.get("id", ""), name=d.get("name", "Dispositivo Tuya"),
                    type="switch",
                    state={"state": "on" if is_on else "off", "on": is_on},
                    platform="tuya"
                ))
            return devices
        except Exception as e:
            logger.warning(f"Tuya get_devices error: {e}")
            return []

    def control(self, device_id: str, action: str, params: dict = None) -> str:
        if not self.available:
            return "Tuya no configurado."
        code = "switch_1"
        value = action == "on"
        try:
            r = requests.post(f"{self._base()}/v1.0/iot-03/devices/{device_id}/commands",
                              headers=self._headers(),
                              json={"commands": [{"code": code, "value": value}]}, timeout=10)
            if r.json().get("success"):
                return f"Dispositivo {'encendido' if value else 'apagado'}."
            return f"Error Tuya: {r.json().get('msg', 'desconocido')}"
        except Exception as e:
            return f"Error Tuya: {e}"


# ─── Servicio unificado ───────────────────────────────────────────────────────

class DomoticaService:
    def __init__(self):
        self.ha      = HomeAssistantAdapter()
        self.ewelink = eWeLinkAdapter()
        self.tuya    = TuyaAdapter()
        self._cache: list[Device] = []

    def _adapters(self):
        return [self.ha, self.ewelink, self.tuya]

    def get_all_devices(self) -> list[Device]:
        devices = []
        for adapter in self._adapters():
            if adapter.available:
                devices.extend(adapter.get_devices())
        self._cache = devices
        return devices

    def find_device(self, name_query: str) -> Device | None:
        q = name_query.lower()
        # buscar en caché primero
        for d in self._cache:
            if q in d.name.lower() or q in d.id.lower():
                return d
        # refrescar si no encontró
        devices = self.get_all_devices()
        for d in devices:
            if q in d.name.lower() or q in d.id.lower():
                return d
        return None

    def control_by_name(self, name: str, action: str, params: dict = None) -> str:
        dev = self.find_device(name)
        if not dev:
            return f"No encontré ningún dispositivo llamado '{name}'."
        adapter = {"ha": self.ha, "ewelink": self.ewelink, "tuya": self.tuya}.get(dev.platform)
        if not adapter:
            return "Plataforma no soportada."
        return adapter.control(dev.id, action, params)

    def list_devices(self) -> str:
        devices = self.get_all_devices()
        if not devices:
            return "No hay dispositivos configurados o no hay conexión."
        by_platform = {}
        for d in devices:
            by_platform.setdefault(d.platform, []).append(d)
        parts = []
        labels = {"ha": "Home Assistant", "ewelink": "eWeLink", "tuya": "Tuya/Linda Smart"}
        for plat, devs in by_platform.items():
            names = ", ".join(f"{d.name} ({d.friendly_state})" for d in devs[:8])
            parts.append(f"{labels.get(plat, plat)}: {names}")
        return ". ".join(parts) + "."

    def status_sensors(self) -> str:
        devices = self.get_all_devices()
        sensors = [d for d in devices if d.type == "sensor"]
        if not sensors:
            return "No hay sensores disponibles."
        parts = [f"{d.name}: {d.friendly_state}" for d in sensors[:10]]
        return ". ".join(parts) + "."


# Instancia global (lazy)
_service: DomoticaService | None = None

def _svc() -> DomoticaService:
    global _service
    if _service is None:
        _service = DomoticaService()
    return _service


# ─── Funciones expuestas al sistema de comandos ───────────────────────────────

def domotica_on(device_name: str) -> str:
    """Enciende un dispositivo domótico por nombre."""
    return _svc().control_by_name(device_name, "on")

def domotica_off(device_name: str) -> str:
    """Apaga un dispositivo domótico por nombre."""
    return _svc().control_by_name(device_name, "off")

def domotica_toggle(device_name: str) -> str:
    """Cambia el estado de un dispositivo domótico."""
    return _svc().control_by_name(device_name, "toggle")

def domotica_list() -> str:
    """Lista todos los dispositivos domóticos disponibles."""
    return _svc().list_devices()

def domotica_sensors() -> str:
    """Lee todos los sensores (temperatura, humedad, etc.)."""
    return _svc().status_sensors()

def domotica_scene(scene_name: str) -> str:
    """Activa una escena de Home Assistant."""
    return _svc().control_by_name(scene_name, "on")

def domotica_brightness(device_name: str, pct: int) -> str:
    """Ajusta el brillo de una luz (0-100)."""
    brightness = int(pct * 2.55)
    return _svc().control_by_name(device_name, "on", {"brightness": brightness})
