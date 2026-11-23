"""Binary Sensoren fuer Kerbl SmartCoop: Luefter laeuft, Licht an, Live-Verbindung.

Die Tuer steht seit v0.15.0 als Tor/Tuer-Entitaet in cover.py.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.util import dt as dt_util

from .coordinator import KerblSmartCoopCoordinator
from .sensor import (
    _KerblSmartCoopBaseEntity,
    _get_path,
    _is_demo_device,
)


PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: KerblSmartCoopCoordinator = entry.runtime_data

    entities: list[BinarySensorEntity] = []
    for device in coordinator.data.get("devices", []):
        if _is_demo_device(device):
            continue
        device_id = str(device.get("id"))
        if _get_path(device, "fan.remainingOnTime") is not None:
            entities.append(KerblSmartCoopFanRunningSensor(coordinator, device_id))
        if _get_path(device, "light.currentDimValue") is not None:
            entities.append(KerblSmartCoopLightOnSensor(coordinator, device_id))
        entities.append(KerblSmartCoopLiveSensor(coordinator, device_id))

    async_add_entities(entities)


class KerblSmartCoopFanRunningSensor(_KerblSmartCoopBaseEntity, BinarySensorEntity):
    """Laeuft der Luefter gerade?

    Drei Signale, die zusammen die App-Logik nachbilden (App-Screenshots vom
    24.08.2026 bestaetigt):
    - fan.remainingOnTime > 0: Intervall-Lauf aktiv (nur kurze Laeufe,
      deckt NICHT den Dauerlauf-Fall ab)
    - automaticPauseReason != "[0]": live beobachtetes Muster fuer den
      Dauerlauf-Override oberhalb von fan.alwaysOnAboveTemperature (35 Grad
      als Beispielwert) - gilt laut App-Beschreibung unabhaengig von Nacht/Tag
    - fan.nightMode: der "Bei Nacht"-Schalter in der App. Steht er auf 0
      (aus), soll der Intervall-Betrieb laut eigener
      Aussage NACHTS nicht laufen - das wird hier zusaetzlich erzwungen,
      falls remainingOnTime das nicht schon selbst korrekt abbildet.
      "Nacht" wird ueber brightness.nightDurationStartTime/EndTime
      (Sekunden seit Mitternacht) bestimmt.

    Weiterhin eine Ableitung aus mehreren Rohdaten-Feldern, keine direkte
    Ablesung vom Motor - noch nicht in der Praxis waehrend eines echten
    Nacht-Intervalls gegengeprueft.
    """

    _attr_device_class = BinarySensorDeviceClass.RUNNING
    _attr_icon = "mdi:fan"

    def __init__(self, coordinator: KerblSmartCoopCoordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id)
        self._attr_unique_id = f"{device_id}_fan_running"
        self._attr_name = "Lüfter läuft"

    @staticmethod
    def _is_night(data: dict[str, Any]) -> bool | None:
        start = _get_path(data, "brightness.nightDurationStartTime")
        end = _get_path(data, "brightness.nightDurationEndTime")
        if start is None or end is None:
            return None
        now = dt_util.now()
        now_sec = now.hour * 3600 + now.minute * 60 + now.second
        if start > end:
            return now_sec >= start or now_sec < end
        return start <= now_sec < end

    @property
    def is_on(self) -> bool | None:
        data = self._device_data()

        pause_reason = data.get("automaticPauseReason")
        override_running = pause_reason is not None and pause_reason != "[0]"
        if override_running:
            return True

        remaining = _get_path(data, "fan.remainingOnTime")
        interval_running = remaining is not None and remaining > 0

        night_mode = _get_path(data, "fan.nightMode")
        if interval_running and night_mode == 0:
            is_night = self._is_night(data)
            if is_night:
                interval_running = False

        if interval_running:
            return True

        if remaining is None and pause_reason is None:
            return None
        return False

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self._device_data()
        return {
            "verbleibende_laufzeit_min": _get_path(data, "fan.remainingOnTime"),
            "automatik_pause_grund_roh": data.get("automaticPauseReason"),
            "aktuelle_lufttemperatur": data.get("airTemperature"),
            "schwelle_immer_an_ueber": _get_path(data, "fan.alwaysOnAboveTemperature"),
            "nachtmodus_erlaubt_intervall": _get_path(data, "fan.nightMode"),
            "gerade_nacht": self._is_night(data),
            "hinweis": "Läuft = Dauerlauf-Override aktiv ODER Intervall-Lauf aktiv (nachts unterdrückt, wenn 'Bei Nacht' in der App aus ist)",
        }


class KerblSmartCoopLightOnSensor(_KerblSmartCoopBaseEntity, BinarySensorEntity):
    """Ist das Licht gerade an? Basiert auf light.currentDimValue (0 = aus)."""

    _attr_device_class = BinarySensorDeviceClass.LIGHT
    _attr_icon = "mdi:lightbulb"

    def __init__(self, coordinator: KerblSmartCoopCoordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id)
        self._attr_unique_id = f"{device_id}_light_on"
        self._attr_name = "Licht"

    @property
    def is_on(self) -> bool | None:
        dim_value = _get_path(self._device_data(), "light.currentDimValue")
        if dim_value is None:
            return None
        return dim_value > 0

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"dimmwert": _get_path(self._device_data(), "light.currentDimValue")}


class KerblSmartCoopLiveSensor(_KerblSmartCoopBaseEntity, BinarySensorEntity):
    """Steht die Live-Verbindung zur Kerbl-Cloud (sofortige Updates)?"""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: KerblSmartCoopCoordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id)
        self._attr_unique_id = f"{device_id}_live_connection"
        self._attr_name = "Live-Verbindung"

    @property
    def is_on(self) -> bool:
        live = getattr(self.coordinator, "live", None)
        return bool(live and live.connected)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        live = getattr(self.coordinator, "live", None)
        return {"letztes_live_update_modulzeit": getattr(live, "last_event", None)}
