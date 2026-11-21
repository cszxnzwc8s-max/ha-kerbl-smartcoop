"""Zeitstempel 'Tuer zuletzt geoeffnet / geschlossen', die Neustarts ueberstehen.

Home Assistant setzt 'zuletzt geaendert' einer Entitaet bei jedem Neustart
neu. Diese Sensoren merken sich den Zeitpunkt selbst:
- Wechsel 67 (zu) <-> 79 (offen) wird beim Eintreffen der Daten erkannt
  (dank Live-Verbindung meist auf Sekunden genau)
- Wert und zuletzt gesehener Zustand werden ueber Neustarts gerettet
- faehrt die Tuer, waehrend HA aus ist oder das Modul offline war, wird der
  Zeitpunkt des Bemerkens eingetragen und als 'ungefaehr' markiert
- beim allerersten Start wird der letzte echte Wechsel aus dem Verlauf
  (Recorder) des Tuer-Sensors uebernommen
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import RestoreSensor, SensorDeviceClass
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import KerblSmartCoopCoordinator
from .sensor import _KerblSmartCoopBaseEntity, _get_path

_LOGGER = logging.getLogger(__name__)

DOOR_OPEN = 79
DOOR_CLOSED = 67


async def _last_change_from_history(hass, entity_id: str, target_ha_state: str) -> datetime | None:
    """Letzten echten Wechsel in target_ha_state aus dem Recorder holen."""
    try:
        from homeassistant.components.recorder import get_instance, history

        result = await get_instance(hass).async_add_executor_job(
            history.get_last_state_changes, hass, 200, entity_id
        )
    except Exception as err:  # noqa: BLE001 - Verlauf ist nur ein Bonus
        _LOGGER.debug("Verlauf fuer %s nicht lesbar: %s", entity_id, err)
        return None

    states = sorted(result.get(entity_id, []), key=lambda s: s.last_changed)
    found: datetime | None = None
    previous: str | None = None
    for state in states:
        if state.state not in ("on", "off"):
            continue  # unavailable/unknown (z.B. Neustart) ueberspringen
        if previous is not None and state.state != previous and state.state == target_ha_state:
            found = state.last_changed
        previous = state.state
    return found


class KerblSmartCoopDoorTimeSensor(_KerblSmartCoopBaseEntity, RestoreSensor):
    """Zeitpunkt, zu dem die Tuer zuletzt geoeffnet bzw. geschlossen wurde."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(
        self,
        coordinator: KerblSmartCoopCoordinator,
        device_id: str,
        *,
        target_raw: int,
        target_ha_state: str,
        key: str,
        name: str,
        icon: str,
    ) -> None:
        super().__init__(coordinator, device_id)
        self._target_raw = target_raw
        self._target_ha_state = target_ha_state
        self._attr_unique_id = f"{device_id}_door_last_{key}"
        self._attr_name = name
        self._attr_icon = icon
        self._value: datetime | None = None
        self._last_seen: int | None = None
        self._approx = False
        self._first_update = True

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()

        last_data = await self.async_get_last_sensor_data()
        if last_data and isinstance(last_data.native_value, datetime):
            self._value = last_data.native_value
        last_state = await self.async_get_last_state()
        if last_state:
            seen = last_state.attributes.get("letzter_status")
            self._last_seen = seen if seen in (DOOR_OPEN, DOOR_CLOSED) else None
            self._approx = bool(last_state.attributes.get("ungefaehr", False))

        if self._value is None:
            door_entity = er.async_get(self.hass).async_get_entity_id(
                "binary_sensor", DOMAIN, f"{self._device_id}_door_state"
            )
            if door_entity:
                self._value = await _last_change_from_history(
                    self.hass, door_entity, self._target_ha_state
                )

        self._process(write=False)
        self.async_write_ha_state()

    def _process(self, write: bool) -> None:  # noqa: ARG002
        raw = _get_path(self._device_data(), "door.state")
        if raw not in (DOOR_OPEN, DOOR_CLOSED):
            return  # faehrt gerade oder unbekannt - nichts festhalten
        if (
            raw == self._target_raw
            and self._last_seen is not None
            and self._last_seen != raw
        ):
            self._value = dt_util.utcnow()
            # Beim ersten Update nach dem Start ist der Wechsel waehrend der
            # Pause passiert -> Zeitpunkt nur ungefaehr bekannt.
            self._approx = self._first_update
        self._last_seen = raw
        self._first_update = False

    @callback
    def _handle_coordinator_update(self) -> None:
        self._process(write=True)
        super()._handle_coordinator_update()

    @property
    def native_value(self) -> datetime | None:
        return self._value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"letzter_status": self._last_seen, "ungefaehr": self._approx}
