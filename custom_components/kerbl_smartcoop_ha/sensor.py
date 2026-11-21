"""Sensoren fuer Kerbl SmartCoop.

Struktur an echten Live-Daten bestaetigt (22.08.2026): Ein Geraet ("Kerbl Wlan
Modul") traegt Tuer/Luefter/Fuetterung/Wassererwaermer/Licht/Helligkeit/Strom
als verschachtelte Unterobjekte. Kerbls Cloud liefert zusaetzlich immer ein
Demo-Geraet ("myDemo", identifier "0000000000", connectionVersion "demo")
mit - das wird hier bewusst ausgeblendet, damit keine Fantasie-Sensoren
entstehen.

Lesende Sensoren (Ist-Werte + aktuelle Einstellungen). Einstellbare Werte
liegen in number.py (Zahlen) und switch.py (Ein/Aus).
"""

from __future__ import annotations

import json
from datetime import timedelta
import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import MATCH_ALL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN, REDACT_KEYS
from .coordinator import KerblSmartCoopCoordinator

_LOGGER = logging.getLogger(__name__)

_GRACE = timedelta(minutes=10)

# Bekannte Demo-Geraete von Kerbl, die die Cloud immer mitliefert.
_DEMO_IDENTIFIERS = {"0000000000"}



def _is_demo_device(device: dict[str, Any]) -> bool:
    if device.get("identifier") in _DEMO_IDENTIFIERS:
        return True
    if device.get("connectionVersion") == "demo":
        return True
    return False


def _get_path(data: dict[str, Any], path: str) -> Any:
    """Liest einen Wert per Punkt-Pfad aus verschachtelten Dicts, z.B. 'door.state'."""
    current: Any = data
    for part in path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def _device_name(device: dict[str, Any]) -> str:
    return str(device.get("description") or device.get("id", "SmartCoop"))


# Ja/Nein statt True/False. Nur fuer echte bool-Werte (siehe _translate).
_JA_NEIN: dict[Any, str] = {True: "Ja", False: "Nein"}

# Fehler-/Meldungscodes, bestaetigt ueber die "Meldungen"-Seite der App
# (24.08., 29.08. + 06.11.2026). 4096 kam einmalig mit sehr altem Datum (2020)
# vor - noch keine App-Bestaetigung, daher absichtlich nicht uebersetzt.
ERROR_CODES: dict[int, str] = {
    0: "Kein Fehler",
    8: "Batterie schwach",
    16: "Wasserheizung aktiv",  # Info-Meldung bei Frost, keine Stoerung
    32: "Wasser leer",
    512: "Klappenstörung",
    2048: "Fremdlichtstörung",
}


def _code_list(raw: Any) -> list[int] | None:
    """'[0]' / '[8,32]' / [8] -> Liste von Codes."""
    if isinstance(raw, list):
        items = raw
    elif isinstance(raw, str):
        try:
            items = json.loads(raw)
        except ValueError:
            return None
        if not isinstance(items, list):
            items = [items]
    elif isinstance(raw, int):
        items = [raw]
    else:
        return None
    return [i for i in items if isinstance(i, int)]


def _format_codes(raw: Any, names: dict[int, str], none_text: str) -> Any:
    codes = _code_list(raw)
    if codes is None:
        return raw
    codes = [c for c in codes if c != 0]
    if not codes:
        return none_text
    return ", ".join(names.get(c, f"Code {c}") for c in codes)


# (Pfad, Anzeigename, Icon, Einheit, device_class, state_class)
_LIVE_VALUE_SPECS: list[tuple[str, str, str, str | None, SensorDeviceClass | None, SensorStateClass | None]] = [
    ("waterHeater.waterTemperature", "Wassertemperatur", "mdi:coolant-temperature", "°C", SensorDeviceClass.TEMPERATURE, SensorStateClass.MEASUREMENT),
    ("brightness.currentBrightness", "Helligkeit (Sensor)", "mdi:brightness-6", "%", None, SensorStateClass.MEASUREMENT),
    ("power.currentVoltage", "Akkuspannung", "mdi:sine-wave", "V", SensorDeviceClass.VOLTAGE, SensorStateClass.MEASUREMENT),
    ("airTemperature", "Lufttemperatur", "mdi:thermometer", "°C", SensorDeviceClass.TEMPERATURE, SensorStateClass.MEASUREMENT),
]

# (Pfad, Anzeigename, Icon, optionale Uebersetzungstabelle roh->Text)
_SETTING_SPECS: list[tuple[str, str, str, dict[Any, str] | str | None]] = [
    ("currentErrorReason", "Aktueller Fehler", "mdi:alert-octagon-outline", "error_list"),
    ("door.doorClosesInMin", "Tür – schließt in (Min)", "mdi:timer-alert-outline", None),
    ("automaticPauseReason", "Automatik pausiert – Grund", "mdi:pause-circle-outline", "pause_list"),
    ("doDesiredAndActualStateMatch", "Einstellungen synchron", "mdi:sync", _JA_NEIN),
    ("door.type", "Tür – Typ", "mdi:door", {2: "Zahnstange"}),
    ("door.openingTime", "Tür – Öffnungszeit", "mdi:clock-start", None),
    ("door.weekendOpeningTime", "Tür – Öffnungszeit (Wochenende)", "mdi:clock-start", None),
    ("door.state", "Tür – Rohstatus (unbekannte Kodierung)", "mdi:help-circle-outline", None),
    ("feeder.startTime", "Fütterung – Start", "mdi:clock-start", None),
    ("feeder.endTime", "Fütterung – Ende", "mdi:clock-end", None),
    ("feeder.feedingInterval", "Fütterung – Intervall (Min)", "mdi:timer-outline", None),
    ("feeder.feedingActive", "Fütterung – aktiv", "mdi:food-drumstick", _JA_NEIN),
    ("feeder.isFeedFull", "Fütterung – Behälter voll", "mdi:food-drumstick-outline", _JA_NEIN),
    ("light.mode", "Licht – Modus", "mdi:lightbulb-outline", {1: "Modus 1", 2: "Modus 2", 3: "Modus 3", 4: "Keine Beleuchtung"}),
    ("light.darkTime", "Licht – Dunkelzeit (Std.)", "mdi:weather-night", None),
    ("light.currentDimValue", "Licht – Dimmwert", "mdi:brightness-6", None),
    ("power.onTime", "Strom – Einschaltzeit", "mdi:power-plug", None),
    ("power.offTime", "Strom – Ausschaltzeit", "mdi:power-plug-off", None),
]


PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: KerblSmartCoopCoordinator = entry.runtime_data

    entities: list[SensorEntity] = []
    for device in coordinator.data.get("devices", []):
        device_id = str(device.get("id", _device_name(device)))
        is_demo = _is_demo_device(device)

        # Rohdaten-Diagnosesensor: fuer alle Geraete (auch Demo), zur Transparenz.
        entities.append(KerblSmartCoopRawSensor(coordinator, device_id))

        if is_demo:
            # Keine "echten" Sensoren fuers Kerbl-Demo-Geraet anlegen.
            continue

        for path, name, icon, unit, device_class, state_class in _LIVE_VALUE_SPECS:
            if _get_path(device, path) is None:
                continue
            entities.append(
                KerblSmartCoopValueSensor(
                    coordinator, device_id, name, path, icon,
                    unit=unit, device_class=device_class, state_class=state_class,
                    offline_unavailable=True,
                )
            )

        for path, name, icon, translations in _SETTING_SPECS:
            if _get_path(device, path) is None:
                continue
            entities.append(
                KerblSmartCoopValueSensor(
                    coordinator, device_id, name, path, icon,
                    category=EntityCategory.DIAGNOSTIC,
                    translations=translations,
                )
            )

        error_history_raw = device.get("errorReasonHistory")
        if error_history_raw:
            entities.append(KerblSmartCoopLastErrorSensor(coordinator, device_id))

        if _get_path(device, "door.state") is not None:
            from .door_times import DOOR_CLOSED, DOOR_OPEN, KerblSmartCoopDoorTimeSensor

            entities.append(KerblSmartCoopDoorTimeSensor(
                coordinator, device_id, target_raw=DOOR_OPEN, target_ha_state="on",
                key="opened", name="Tür – zuletzt geöffnet", icon="mdi:door-open",
            ))
            entities.append(KerblSmartCoopDoorTimeSensor(
                coordinator, device_id, target_raw=DOOR_CLOSED, target_ha_state="off",
                key="closed", name="Tür – zuletzt geschlossen", icon="mdi:door-closed",
            ))

    if not entities:
        _LOGGER.warning("Keine SmartCoop-Geraete gefunden - Setup war erfolgreich, aber es wurden (noch) keine Sensoren angelegt.")

    async_add_entities(entities)


class _KerblSmartCoopBaseEntity(CoordinatorEntity[KerblSmartCoopCoordinator]):
    """Gemeinsame Basis; jede Entitaet zeigt ihr eigenes Symbol (kein Logo)."""

    def __init__(self, coordinator: KerblSmartCoopCoordinator, device_id: str) -> None:
        super().__init__(coordinator)
        self._device_id = device_id

    def _device_data(self) -> dict[str, Any]:
        for device in self.coordinator.data.get("devices", []):
            if str(device.get("id")) == self._device_id:
                return device
        return {}

    @property
    def available(self) -> bool:
        """Kurze Cloud-Aussetzer (bis 10 Min) ueberbruecken statt sofort
        'nicht verfuegbar' zu zeigen."""
        if self.coordinator.last_update_success:
            return True
        last = getattr(self.coordinator, "last_success", None)
        return last is not None and dt_util.utcnow() - last < _GRACE

    def _module_online(self) -> bool:
        """False nur, wenn die Cloud das Modul ausdruecklich als offline meldet."""
        return self._device_data().get("isOnline") is not False

    @property
    def device_info(self) -> DeviceInfo:
        data = self._device_data()
        return DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            name=_device_name(data),
            manufacturer="Kerbl",
            model="SmartCoop",
        )


class _OfflineUnavailableMixin:
    """Live-Werte als 'nicht verfuegbar' zeigen, solange das Modul offline ist.

    Sonst wuerde z.B. der Tuerstatus tagelang den letzten Stand anzeigen, als
    waere er aktuell.
    """

    @property
    def available(self) -> bool:
        return super().available and self._module_online()  # type: ignore[misc]


class KerblSmartCoopRawSensor(_KerblSmartCoopBaseEntity, SensorEntity):
    """Diagnose-Sensor: Online-Status, Rohdaten als Attribute.

    Die Attribute (ca. 5 KB) werden bewusst NICHT in der Datenbank
    gespeichert; fuer Fehlersuche gibt es den Diagnose-Download.
    """

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:code-json"
    _unrecorded_attributes = frozenset({MATCH_ALL})

    def __init__(self, coordinator: KerblSmartCoopCoordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id)
        self._attr_unique_id = f"{device_id}_raw"
        self._attr_name = "Rohdaten"

    @property
    def native_value(self) -> str:
        data = self._device_data()
        online = data.get("isOnline")
        if online is True:
            return "online"
        if online is False:
            return "offline"
        return "unbekannt"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = dict(self._device_data())
        for key in REDACT_KEYS:
            if key in data:
                data[key] = "**REDACTED**"
        return data


class KerblSmartCoopValueSensor(_KerblSmartCoopBaseEntity, SensorEntity):
    """Liest einen einzelnen Wert per Punkt-Pfad aus den verschachtelten Rohdaten."""

    def __init__(
        self,
        coordinator: KerblSmartCoopCoordinator,
        device_id: str,
        name: str,
        path: str,
        icon: str,
        unit: str | None = None,
        device_class: SensorDeviceClass | None = None,
        state_class: SensorStateClass | None = None,
        category: EntityCategory | None = None,
        translations: dict[Any, str] | str | None = None,
        offline_unavailable: bool = False,
    ) -> None:
        super().__init__(coordinator, device_id)
        self._offline_unavailable = offline_unavailable
        self._path = path
        self._translations = translations or {}
        safe_path = path.replace(".", "_")
        self._attr_unique_id = f"{device_id}_{safe_path}"
        self._attr_name = name
        self._attr_icon = icon
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        self._attr_state_class = state_class
        self._attr_entity_category = category

    @property
    def available(self) -> bool:
        if self._offline_unavailable and not self._module_online():
            return False
        return super().available

    @property
    def native_value(self) -> Any:
        value = _get_path(self._device_data(), self._path)
        if self._translations == "error_list":
            return _format_codes(value, ERROR_CODES, "Kein Fehler")
        if self._translations == "pause_list":
            return _format_codes(value, {}, "Nicht pausiert")
        if isinstance(value, bool):
            return (self._translations or {}).get(value, value)
        if isinstance(self._translations, dict):
            return self._translations.get(value, value)
        return value


class KerblSmartCoopLastErrorSensor(_KerblSmartCoopBaseEntity, SensorEntity):
    """Zeigt den letzten Fehlercode aus der Fehlerhistorie mit Datum/Uhrzeit."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:alert-circle-outline"

    _ERROR_CODES = ERROR_CODES

    def __init__(self, coordinator: KerblSmartCoopCoordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id)
        self._attr_unique_id = f"{device_id}_last_error"
        self._attr_name = "Letzter Fehlercode"

    def _history(self) -> list[dict[str, Any]]:
        raw = self._device_data().get("errorReasonHistory")
        if not raw:
            return []
        try:
            parsed = json.loads(raw)
        except (TypeError, ValueError):
            return []
        return parsed if isinstance(parsed, list) else []

    @property
    def native_value(self) -> Any:
        history = self._history()
        if not history:
            return None
        latest = history[0]
        code = latest.get("errorReason")
        return self._ERROR_CODES.get(code, code)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        history = self._history()
        if not history:
            return {}
        latest = history[0]
        verlauf_uebersetzt = [
            {
                "datum": eintrag.get("date"),
                "uhrzeit": eintrag.get("time"),
                "fehler": self._ERROR_CODES.get(eintrag.get("errorReason"), eintrag.get("errorReason")),
                "code_roh": eintrag.get("errorReason"),
            }
            for eintrag in history[:10]
        ]
        return {
            "code_roh": latest.get("errorReason"),
            "datum": latest.get("date"),
            "uhrzeit": latest.get("time"),
            "verlauf_letzte_10": verlauf_uebersetzt,
        }
