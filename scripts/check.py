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
cov.coordinator = c; cov._device_id = "d"; cov._last_closed = None; cov._reported_codes = set()
seq = [(67, "closed"), (111, "opening"), (79, "open"), (99, "closing"), (67, "closed")]
for raw, cover_state in seq:
    c.data["devices"][0]["door"]["state"] = raw
    got = "opening" if cov.is_opening else "closing" if cov.is_closing else ("closed" if cov.is_closed else "open")
    assert got == cover_state, (raw, got)

# blockiert (63): immer "nicht ganz zu", Stoerung im Wortlaut der App
c.data["devices"][0]["door"]["state"] = 67; assert cov.is_closed is True
c.data["devices"][0]["door"]["state"] = 63
c.data["devices"][0]["currentErrorReason"] = "[512]"
assert cov.is_closed is False and 63 not in cov._reported_codes
assert cov.extra_state_attributes["stoerung"] == "Klappenstörung"
c.data["devices"][0]["currentErrorReason"] = "[16]"
assert "stoerung" not in cov.extra_state_attributes   # Wasserheizung ist keine Tuer-Stoerung
c.data["devices"][0]["door"]["state"] = 67; assert cov.is_closed is True

# unbekannter Code: Anzeige bleibt beim letzten Stand, Code steht im Attribut
c.data["devices"][0]["door"]["state"] = 4242
assert cov.is_closed is True and not cov.is_opening and not cov.is_closing
assert cov.extra_state_attributes["roh_status"] == 4242 and 4242 in cov._reported_codes

# Aufraeumen trifft nur abgeschaffte Entitaeten
init = importlib.import_module(PKG)
keep = {("sensor", "x_door_doorClosesInMin"), ("cover", "x_door_cover"), ("number", "x_door_relativeOpeningBrightness")}
gone = {("binary_sensor", "x_door_state"), ("sensor", "x_door_state"), ("sensor", "x_door_last_opened")}
hit = lambda d, u: any(d == dd and u.endswith(sx) for dd, sx in init._REMOVED_ENTITIES)
assert all(hit(*e) for e in gone) and not any(hit(*e) for e in keep)

if errors:
    print("FEHLER:", *errors, sep="\n  ")
    sys.exit(1)
print("check ok")
