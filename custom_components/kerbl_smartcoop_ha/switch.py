"""Ein/Aus-Einstellungen fuer Kerbl SmartCoop."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import KerblSmartCoopCoordinator
from .number import async_write_parameter
from .sensor import _KerblSmartCoopBaseEntity, _get_path, _is_demo_device

# (Pfad, Name, Icon) - Werte 0 = aus, 1 = an
_SWITCH_SPECS: list[tuple[str, str, str]] = [
    ("fan.nightMode", "Lüfter – Intervall auch nachts", "mdi:fan-clock"),
]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: KerblSmartCoopCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[SwitchEntity] = []
    for device in coordinator.data.get("devices", []):
        if _is_demo_device(device):
            continue
        device_id = str(device.get("id"))
        for path, name, icon in _SWITCH_SPECS:
            if _get_path(device, path) is None:
                continue
            entities.append(KerblSmartCoopSettingSwitch(coordinator, device_id, path, name, icon))

    async_add_entities(entities)


class KerblSmartCoopSettingSwitch(_KerblSmartCoopBaseEntity, SwitchEntity):
    """Schalter fuer eine 0/1-Einstellung (z.B. 'Bei Nacht' beim Luefter)."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        coordinator: KerblSmartCoopCoordinator,
        device_id: str,
        path: str,
        name: str,
        icon: str,
    ) -> None:
        super().__init__(coordinator, device_id)
        self._path = path
        self._attr_unique_id = f"{device_id}_set_{path.replace('.', '_')}"
        self._attr_name = name
        self._attr_icon = icon

    @property
    def is_on(self) -> bool | None:
        value = _get_path(self._device_data(), self._path)
        if value is None:
            return None
        return bool(value)

    async def async_turn_on(self, **kwargs: Any) -> None:
        await async_write_parameter(self, self._path, 1)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await async_write_parameter(self, self._path, 0)
