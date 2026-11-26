"""Optional hardware: an ESP32 building node publishing telemetry over MQTT (contract in docs/hardware.md).

Topic  qgrid/<zone>/telemetry   payload JSON {"ts": unix_s, "pv_kw": float, "load_kw": float, "soc": 0..1, "rssi": int?}
Topic  qgrid/<zone>/command     (published by the operator app) {"battery_kw": float, "dg_on": bool, "pump_on": bool}
A zone counts as LIVE HARDWARE while its last telemetry is under 10 s old; otherwise it is simulated, and labelled so.
Broker: env QGRID_MQTT_HOST (default localhost), QGRID_MQTT_PORT (1883; 8883 = TLS with QGRID_MQTT_TLS=1)."""
from __future__ import annotations

import json
import os
import threading
import time


class Hardware:
    def __init__(self, zones: list[str]):
        self.zones = set(zones)
        self.last: dict[str, dict] = {}
        self.connected = False
        self.error: str | None = None
        self._client = None

    def start(self):
        try:
            import paho.mqtt.client as mqtt
        except ImportError:
            self.error = "paho-mqtt not installed"
            return
        host = os.environ.get("QGRID_MQTT_HOST", "localhost"); port = int(os.environ.get("QGRID_MQTT_PORT", "1883"))
        c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="qgrid-operator")
        if os.environ.get("QGRID_MQTT_TLS") == "1":
            c.tls_set()
        if os.environ.get("QGRID_MQTT_USER"):
            c.username_pw_set(os.environ["QGRID_MQTT_USER"], os.environ.get("QGRID_MQTT_PASS"))

        def on_connect(cl, _u, _f, rc, _p=None):
            self.connected = (rc == 0)
            cl.subscribe("qgrid/+/telemetry")

        def on_message(_cl, _u, msg):
            try:
                zone = msg.topic.split("/")[1]
                if zone not in self.zones:
                    return
                d = json.loads(msg.payload)
                d["_rx"] = time.time()
                self.last[zone] = d
            except Exception:
                pass

        c.on_connect, c.on_message = on_connect, on_message
        c.on_disconnect = lambda *a, **k: setattr(self, "connected", False)
        try:
            c.connect_async(host, port, keepalive=30)
            c.loop_start()
            self._client = c
        except Exception as e:
            self.error = f"{type(e).__name__}: {e}"[:120]

    def live(self, zone: str, max_age: float = 10.0) -> dict | None:
        d = self.last.get(zone)
        return d if d and time.time() - d["_rx"] < max_age else None

    def command(self, zone: str, cmd: dict):
        if self._client is not None and self.connected:
            self._client.publish(f"qgrid/{zone}/command", json.dumps(cmd), qos=1)

    def status(self) -> dict:
        return {"broker_connected": self.connected, "error": self.error, "zones_live": [z for z in self.zones if self.live(z)]}
