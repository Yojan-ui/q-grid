# Hardware: an ESP32 building node on MQTT

The Operate mode treats a building as **LIVE HARDWARE** while an ESP32 (or any device) publishes its telemetry on MQTT;
otherwise the building is simulated and labelled "simulated". There is no ESP32 firmware in this repository yet; this
is the contract the backend (`backend/qgrid/operate/mqtt.py`) implements.

| Topic | Direction | Payload (JSON) |
|---|---|---|
| `qgrid/<zone>/telemetry` | node → app, every 1–5 s | `{"ts": unix_seconds, "pv_kw": float, "load_kw": float, "soc": 0..1, "rssi": int (optional)}` |
| `qgrid/<zone>/command` | app → node, every simulated minute | `{"battery_kw": float, "dg_on": bool, "pump_on": bool}` (already clamped by the safety layer) |

- `<zone>` is a campus zone name from `config.yaml` (e.g. `server_room`).
- A zone counts as live while its last telemetry is under 10 s old; latency = receive time − `ts`.
- Measured `pv_kw`, `load_kw` and `soc` replace the simulated values for that building; plans, safety and the daily
  report use them.
- Broker: `QGRID_MQTT_HOST` (default `localhost`), `QGRID_MQTT_PORT` (default 1883); TLS with `QGRID_MQTT_TLS=1`
  (port 8883), credentials with `QGRID_MQTT_USER` / `QGRID_MQTT_PASS`. Without a reachable broker every building is
  simulated and the Devices panel says so.
