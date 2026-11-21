"""Constants for the Kerbl SmartCoop integration.

Auth-Flow und Basis-URL sind aus dem echten Quellcode der Weidezaun-
Bibliothek (kerblwelt-api von stgarrity, PyPI) bestätigt - beide Produkte
laufen über denselben Kerbl-Welt-Account/Backend.
"""

DOMAIN = "kerbl_smartcoop_ha"

BASE_URL = "https://backend.kerbl-iot.com/api/v0.1"
ENDPOINT_AUTH_SIGN_IN = "/auth/sign-in"
ENDPOINT_AUTH_REFRESH = "/auth/refresh"
ENDPOINT_DEVICES = "/device"
# Einstellung schreiben, wie die Kerbl-App es tut (mitgeschnitten 21.11.2026):
# PATCH .../device/smart-coop/<modul-id>/parameter/<punkt.pfad>  Body {"value": n}
ENDPOINT_PARAMETER = "/device/smart-coop/{device_id}/parameter/{path}"

UPDATE_INTERVAL_SECONDS = 60

# Live-Verbindung (Socket.IO) wie in der Kerbl-App
LIVE_URL = "https://app.kerbl-iot.com"
LIVE_SOCKETIO_PATH = "/ws/v0.1/socket.io"

# Bestätigt an echten Live-Daten (16.08.2026): Die /device-Antwort enthält
# tatsächlich einen Schlüssel "smartCoop". Zusätzlich existiert ein
# getrennter Schlüssel "smartChickenDoor" für das Türmodul - beide werden
# abgefragt und zusammengeführt, da SmartCoop-Hardware oft aus Controller
# + separatem Türantrieb besteht.
DEVICE_LIST_KEYS = ["smartCoop", "smartChickenDoor"]
