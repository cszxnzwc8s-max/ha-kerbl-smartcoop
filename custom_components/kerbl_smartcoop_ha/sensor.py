"""Sensoren fuer Kerbl SmartCoop.

Struktur an echten Live-Daten bestaetigt (22.08.2026): Ein Geraet ("Kerbl Wlan
Modul") traegt Tuer/Luefter/Fuetterung/Wassererwaermer/Licht/Helligkeit/Strom
als verschachtelte Unterobjekte. Kerbls Cloud liefert zusaetzlich immer ein
Demo-Geraet ("myDemo", identifier "0000000000", connectionVersion "demo")
mit - das wird hier bewusst ausgeblendet, damit keine Fantasie-Sensoren
entstehen.

Lesende Sensoren (Ist-Werte + aktuelle Einstellungen). Einstellbare Werte
(Oeffnungs-/Schliesshelligkeit der Tuer) liegen in number.py.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import KerblSmartCoopCoordinator

_LOGGER = logging.getLogger(__name__)

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


# (Pfad, Anzeigename, Icon, Einheit, device_class, state_class)
_LIVE_VALUE_SPECS: list[tuple[str, str, str, str | None, SensorDeviceClass | None, SensorStateClass | None]] = [
    ("waterHeater.waterTemperature", "Wassertemperatur", "mdi:coolant-temperature", "°C", SensorDeviceClass.TEMPERATURE, SensorStateClass.MEASUREMENT),
    ("brightness.currentBrightness", "Helligkeit (Sensor)", "mdi:brightness-6", "%", None, SensorStateClass.MEASUREMENT),
    ("power.currentVoltage", "Akkuspannung", "mdi:sine-wave", "V", SensorDeviceClass.VOLTAGE, SensorStateClass.MEASUREMENT),
    ("airTemperature", "Lufttemperatur", "mdi:thermometer", "°C", SensorDeviceClass.TEMPERATURE, SensorStateClass.MEASUREMENT),
]

# (Pfad, Anzeigename, Icon, optionale Uebersetzungstabelle roh->Text)
_SETTING_SPECS: list[tuple[str, str, str, dict[Any, str] | None]] = [
    ("currentErrorReason", "Aktueller Fehler (roh)", "mdi:alert-octagon-outline", None),
    ("door.doorClosesInMin", "Tür – schließt in (Min)", "mdi:timer-alert-outline", None),
    ("automaticPauseReason", "Automatik pausiert – Grund (roh)", "mdi:pause-circle-outline", None),
    ("doDesiredAndActualStateMatch", "Einstellungen synchron", "mdi:sync", None),
    ("door.type", "Tür – Typ", "mdi:door", {2: "Zahnstange"}),
    ("door.openingTime", "Tür – Öffnungszeit", "mdi:clock-start", None),
    ("door.weekendOpeningTime", "Tür – Öffnungszeit (Wochenende)", "mdi:clock-start", None),
    ("door.closingDelayDuration", "Tür – Schließverzögerung (Min)", "mdi:timer-outline", None),
    ("door.state", "Tür – Rohstatus (unbekannte Kodierung)", "mdi:help-circle-outline", None),
    ("fan.power", "Lüfter – Leistung (%)", "mdi:fan", None),
    ("fan.interval", "Lüfter – Intervall (Min)", "mdi:fan-clock", None),
    ("fan.onDuration", "Lüfter – Laufzeit je Intervall (Min)", "mdi:fan-clock", None),
    ("fan.alwaysOffBelowTemperature", "Lüfter – Aus unter (°C)", "mdi:thermometer-low", None),
    ("fan.alwaysOnAboveTemperature", "Lüfter – An über (°C)", "mdi:thermometer-high", None),
    ("feeder.startTime", "Fütterung – Start", "mdi:clock-start", None),
    ("feeder.endTime", "Fütterung – Ende", "mdi:clock-end", None),
    ("feeder.feedingInterval", "Fütterung – Intervall (Min)", "mdi:timer-outline", None),
    ("feeder.animalCount", "Fütterung – Anzahl Tiere", "mdi:google-circles-communities", None),
    ("feeder.amountPerAnimal", "Fütterung – Menge pro Tier (%)", "mdi:scale", None),
    ("feeder.feedingActive", "Fütterung – aktiv", "mdi:food-drumstick", None),
    ("feeder.isFeedFull", "Fütterung – Behälter voll", "mdi:food-drumstick-outline", None),
    ("light.mode", "Licht – Modus", "mdi:lightbulb-outline", {4: "Keine Beleuchtung"}),
    ("light.darkTime", "Licht – Dunkelzeit (Std.)", "mdi:weather-night", None),
    ("light.currentDimValue", "Licht – Dimmwert", "mdi:brightness-6", None),
    ("power.onTime", "Strom – Einschaltzeit", "mdi:power-plug", None),
    ("power.offTime", "Strom – Ausschaltzeit", "mdi:power-plug-off", None),
    ("power.energySavingActiveBelow", "Strom – Energiesparmodus unter (V)", "mdi:battery-low", None),
]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: KerblSmartCoopCoordinator = hass.data[DOMAIN][entry.entry_id]

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
    def device_info(self) -> DeviceInfo:
        data = self._device_data()
        return DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            name=_device_name(data),
            manufacturer="Kerbl",
            model="SmartCoop",
        )


class KerblSmartCoopRawSensor(_KerblSmartCoopBaseEntity, SensorEntity):
    """Diagnose-Sensor: zeigt alle Rohdaten als Attribute."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:code-json"

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
        return dict(self._device_data())


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
        translations: dict[Any, str] | None = None,
    ) -> None:
        super().__init__(coordinator, device_id)
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
    def native_value(self) -> Any:
        value = _get_path(self._device_data(), self._path)
        return self._translations.get(value, value)


class KerblSmartCoopLastErrorSensor(_KerblSmartCoopBaseEntity, SensorEntity):
    """Zeigt den letzten Fehlercode aus der Fehlerhistorie mit Datum/Uhrzeit."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:alert-circle-outline"

    # Bestaetigt ueber die "Meldungen"-Seite der App (24.08., 29.08. + 06.11.2026):
    _ERROR_CODES: dict[int, str] = {
        0: "Kein Fehler",
        8: "Batterie schwach",
        16: "Wasserheizung aktiv",  # Info-Meldung bei Frost, keine Stoerung (06.11.2026)
        32: "Wasser leer",
        512: "Klappenstörung",
        2048: "Fremdlichtstörung",
        # 4096 kam einmalig mit einem sehr alten Datum (2020) vor - noch
        # keine App-Bestaetigung fuer den Text, absichtlich nicht geraten.
    }

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
