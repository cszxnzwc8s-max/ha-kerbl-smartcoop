"""Tuer als Home-Assistant-Typ 'Tor/Tuer' (cover).

Zustaende aus door.state (seit Oktober 2026 vielfach bestaetigt):
  79 = offen, 67 = geschlossen, 111 = oeffnet, 99 = schliesst

Vorerst nur Anzeige, ohne Auf/Zu-Knoepfe. Die Steuerung kommt erst nach dem
Test am echten Stall dazu (Kerbl-Befehl doorControl ist ein Umschalter).
"""

from __future__ import annotations

import logging

from homeassistant.components.cover import CoverDeviceClass, CoverEntity, CoverEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .coordinator import KerblSmartCoopCoordinator
from .sensor import _KerblSmartCoopBaseEntity, _get_path, _is_demo_device

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0

DOOR_OPEN = 79
DOOR_CLOSED = 67
DOOR_OPENING = 111
DOOR_CLOSING = 99
_KNOWN_CODES = {DOOR_OPEN, DOOR_CLOSED, DOOR_OPENING, DOOR_CLOSING}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: KerblSmartCoopCoordinator = entry.runtime_data
    entities: list[CoverEntity] = []
    for device in coordinator.data.get("devices", []):
        if _is_demo_device(device):
            continue
        if _get_path(device, "door.state") is not None:
            entities.append(KerblSmartCoopDoorCover(coordinator, str(device.get("id"))))
    async_add_entities(entities)


class KerblSmartCoopDoorCover(_KerblSmartCoopBaseEntity, CoverEntity, RestoreEntity):
    """Huehnertuer: offen / oeffnet / schliesst / geschlossen."""

    _attr_device_class = CoverDeviceClass.DOOR
    _attr_supported_features = CoverEntityFeature(0)

    def __init__(self, coordinator: KerblSmartCoopCoordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id)
        self._attr_unique_id = f"{device_id}_door_cover"
        self._attr_name = "Tür"
        self._last_closed: bool | None = None
        self._reported_codes: set[int] = set()

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last and last.state in ("open", "closed"):
            self._last_closed = last.state == "closed"

    def _raw(self) -> int | None:
        raw = _get_path(self._device_data(), "door.state")
        if raw is not None and raw not in _KNOWN_CODES and raw not in self._reported_codes:
            # Neue Codes sollen auffallen statt still verschluckt zu werden.
            self._reported_codes.add(raw)
            _LOGGER.warning(
                "Unbekannter Tuer-Code %s - Anzeige bleibt beim letzten bekannten Zustand. "
                "Bitte melden: %s/issues", raw, "https://github.com/cszxnzwc8s-max/ha-kerbl-smartcoop",
            )
        return raw

    @property
    def is_opening(self) -> bool:
        return self._raw() == DOOR_OPENING

    @property
    def is_closing(self) -> bool:
        return self._raw() == DOOR_CLOSING

    @property
    def is_closed(self) -> bool | None:
        raw = self._raw()
        if raw == DOOR_CLOSED:
            self._last_closed = True
        elif raw == DOOR_OPEN:
            self._last_closed = False
        return self._last_closed

    @property
    def extra_state_attributes(self) -> dict[str, int | None]:
        return {"roh_status": self._raw()}
