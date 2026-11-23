"""Schnellpruefung vor jedem Release: python3 scripts/check.py

- alle Module importierbar
- jede Entitaetsklasse hat device_info aus der Basisklasse (siehe Fehler in 0.13.0)
- Tuer-Entitaet zeigt Fahrt korrekt an
"""
import sys
import inspect
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import importlib

PKG = "custom_components.kerbl_smartcoop_ha"
mods = {m: importlib.import_module(f"{PKG}.{m}") for m in
        ["const", "api", "coordinator", "sensor", "binary_sensor", "number", "switch",
         "config_flow", "live", "diagnostics", "cover"]}
importlib.import_module(PKG)

base = mods["sensor"]._KerblSmartCoopBaseEntity
errors = []
for mod in mods.values():
    for name, cls in inspect.getmembers(mod, inspect.isclass):
        if issubclass(cls, base) and cls is not base:
            owner = next(c for c in cls.__mro__ if "device_info" in c.__dict__)
            if owner is not base:
                errors.append(f"{name}: device_info kommt aus {owner.__name__}")

class Coord:
    def __init__(self): self.data = {"devices": [{"id": "d", "door": {"state": 67}}]}
c = Coord()

# Tuer-Cover: Fahrt wird angezeigt, Endlage gemerkt
cv = mods["cover"]
cov = cv.KerblSmartCoopDoorCover.__new__(cv.KerblSmartCoopDoorCover)
cov.coordinator = c; cov._device_id = "d"; cov._last_closed = None
seq = [(67, "closed"), (111, "opening"), (79, "open"), (99, "closing"), (67, "closed")]
for raw, cover_state in seq:
    c.data["devices"][0]["door"]["state"] = raw
    got = "opening" if cov.is_opening else "closing" if cov.is_closing else ("closed" if cov.is_closed else "open")
    assert got == cover_state, (raw, got)

if errors:
    print("FEHLER:", *errors, sep="\n  ")
    sys.exit(1)
print("check ok")
