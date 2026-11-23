"""Schnellpruefung vor jedem Release: python3 scripts/check.py

- alle Module importierbar
- jede Entitaetsklasse hat device_info aus der Basisklasse (siehe Fehler in 0.13.0)
- Tuer-Zeitstempel reagieren korrekt auf Zustandswechsel
"""
import sys
import inspect
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import importlib

PKG = "custom_components.kerbl_smartcoop_ha"
mods = {m: importlib.import_module(f"{PKG}.{m}") for m in
        ["const", "api", "coordinator", "sensor", "binary_sensor", "number", "switch",
         "config_flow", "live", "diagnostics", "door_times", "cover"]}
importlib.import_module(PKG)

base = mods["sensor"]._KerblSmartCoopBaseEntity
errors = []
for mod in mods.values():
    for name, cls in inspect.getmembers(mod, inspect.isclass):
        if issubclass(cls, base) and cls is not base:
            owner = next(c for c in cls.__mro__ if "device_info" in c.__dict__)
            if owner is not base:
                errors.append(f"{name}: device_info kommt aus {owner.__name__}")

# Tuer-Zeitstempel: Logik ohne laufendes HA pruefen
dt = mods["door_times"]
class Coord:
    def __init__(self): self.data = {"devices": [{"id": "d", "door": {"state": 67}}]}
c = Coord()
s = dt.KerblSmartCoopDoorTimeSensor.__new__(dt.KerblSmartCoopDoorTimeSensor)
s.coordinator = c; s._device_id = "d"; s._target_raw = 79
s._value = None; s._last_seen = 67; s._approx = False; s._first_update = True
s._process(write=False)                       # Start: zu -> nichts
assert s._value is None and s._approx is False, "Start ohne Wechsel"
c.data["devices"][0]["door"]["state"] = 111; s._process(write=True)   # faehrt
assert s._value is None and s._last_seen == 67, "Fahrt darf nichts setzen"
c.data["devices"][0]["door"]["state"] = 79; s._process(write=True)    # offen
assert s._value is not None and s._approx is False, "Oeffnen erkannt"
s2 = dt.KerblSmartCoopDoorTimeSensor.__new__(dt.KerblSmartCoopDoorTimeSensor)
s2.coordinator = c; s2._device_id = "d"; s2._target_raw = 79
s2._value = None; s2._last_seen = 67; s2._approx = False; s2._first_update = True
s2._process(write=False)                      # beim Start schon offen -> ungefaehr
assert s2._value is not None and s2._approx is True, "Wechsel waehrend Pause = ungefaehr"

# Tuer-Cover und Binary-Sensor: Fahrt haelt alten Zustand
cv = mods["cover"]; bs = mods["binary_sensor"]
cov = cv.KerblSmartCoopDoorCover.__new__(cv.KerblSmartCoopDoorCover)
bin_ = bs.KerblSmartCoopDoorSensor.__new__(bs.KerblSmartCoopDoorSensor)
for e in (cov, bin_):
    e.coordinator = c; e._device_id = "d"
cov._last_closed = None; bin_._last_stable = None
seq = [(67, "closed", False), (111, "opening", False), (79, "open", True), (99, "closing", True), (67, "closed", False)]
for raw, cover_state, door_on in seq:
    c.data["devices"][0]["door"]["state"] = raw
    got = "opening" if cov.is_opening else "closing" if cov.is_closing else ("closed" if cov.is_closed else "open")
    assert got == cover_state, (raw, got)
    assert bin_.is_on is door_on, (raw, bin_.is_on)

if errors:
    print("FEHLER:", *errors, sep="\n  ")
    sys.exit(1)
print("check ok")
