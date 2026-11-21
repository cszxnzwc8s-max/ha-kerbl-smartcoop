"""Einstellbare Werte fuer Kerbl SmartCoop (Zahlenfelder).

Schreibt ueber denselben Weg wie die Kerbl-App:
PATCH /device/smart-coop/<modul-id>/parameter/<punkt.pfad> mit {"value": n}
(fuer door.relativeOpeningBrightness am 21.11.2026 mitgeschnitten).

Die Grenzen sind aus den Schiebereglern der App abgeleitet (Position des
Reglers bei bekannten Werten) und bewusst eher eng gewaehlt.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import KerblSmartCoopCoordinator
from .exceptions import KerblApiError, KerblAuthError, KerblConnectionError
from .sensor import _KerblSmartCoopBaseEntity, _get_path, _is_demo_device

_LOGGER = logging.getLogger(__name__)

# (Pfad, Name, Icon, Minimum, Maximum)
_NUMBER_SPECS: list[tuple[str, str, str, int, int]] = [
    ("door.relativeOpeningBrightness", "Tür – Öffnungshelligkeit", "mdi:brightness-5", 10, 60),
    ("door.relativeClosingBrightness", "Tür – Schließhelligkeit", "mdi:brightness-3", 1, 15),
]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: KerblSmartCoopCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[NumberEntity] = []
    for device in coordinator.data.get("devices", []):
        if _is_demo_device(device):
            continue
        device_id = str(device.get("id"))
        for path, name, icon, minimum, maximum in _NUMBER_SPECS:
            if _get_path(device, path) is None:
                continue
            entities.append(
                KerblSmartCoopNumber(coordinator, device_id, path, name, icon, minimum, maximum)
            )

    async_add_entities(entities)


class KerblSmartCoopNumber(_KerblSmartCoopBaseEntity, NumberEntity):
    """Eine Einstellung, die sich aus Home Assistant aendern laesst."""

    _attr_mode = NumberMode.BOX
    _attr_native_step = 1
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        coordinator: KerblSmartCoopCoordinator,
        device_id: str,
        path: str,
        name: str,
        icon: str,
        minimum: int,
        maximum: int,
    ) -> None:
        super().__init__(coordinator, device_id)
        self._path = path
        self._attr_unique_id = f"{device_id}_set_{path.replace('.', '_')}"
        self._attr_name = name
        self._attr_icon = icon
        self._attr_native_min_value = minimum
        self._attr_native_max_value = maximum

    @property
    def native_value(self) -> float | None:
        value = _get_path(self._device_data(), self._path)
        return float(value) if isinstance(value, (int, float)) else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self._device_data()
        return {
            "einstellungen_synchron": data.get("doDesiredAndActualStateMatch"),
            "modul_online": data.get("isOnline"),
        }

    async def async_set_native_value(self, value: float) -> None:
        new_value = int(round(value))
        try:
            await self.coordinator.client.async_set_parameter(
                self._device_id, self._path, new_value
            )
        except (KerblApiError, KerblAuthError, KerblConnectionError) as err:
            raise HomeAssistantError(f"Kerbl: {err}") from err

        # Sofort anzeigen, danach mit der Cloud abgleichen.
        device = self._device_data()
        section, _, key = self._path.partition(".")
        if isinstance(device.get(section), dict):
            device[section][key] = new_value
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()
