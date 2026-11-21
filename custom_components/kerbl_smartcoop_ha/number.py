"""Einstellbare Werte fuer Kerbl SmartCoop (Zahlenfelder).

Schreibt ueber denselben Weg wie die Kerbl-App:
PATCH /device/smart-coop/<modul-id>/parameter/<punkt.pfad> mit {"value": n}
(fuer door.relativeOpeningBrightness am 21.11.2026 mitgeschnitten, die
weiteren Pfade mit unveraendertem Wert gegengeprueft).

Die Grenzen sind bewusst eher eng gewaehlt. Die Tuer-Helligkeiten sind aus
der Stellung der Schieberegler in der App abgeleitet.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    UnitOfElectricPotential,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import KerblSmartCoopCoordinator
from .exceptions import KerblApiError, KerblAuthError, KerblConnectionError
from .sensor import _KerblSmartCoopBaseEntity, _get_path, _is_demo_device

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class _NumberSpec:
    path: str
    name: str
    icon: str
    minimum: float
    maximum: float
    step: float = 1
    unit: str | None = None
    device_class: NumberDeviceClass | None = None


_NUMBER_SPECS: list[_NumberSpec] = [
    # Tuer
    _NumberSpec("door.relativeOpeningBrightness", "Tür – Öffnungshelligkeit", "mdi:brightness-5", 10, 60, unit=PERCENTAGE),
    _NumberSpec("door.relativeClosingBrightness", "Tür – Schließhelligkeit", "mdi:brightness-3", 1, 15, unit=PERCENTAGE),
    _NumberSpec("door.closingDelayDuration", "Tür – Schließverzögerung", "mdi:timer-outline", 0, 60, unit=UnitOfTime.MINUTES),
    # Luefter
    _NumberSpec("fan.power", "Lüfter – Leistung", "mdi:fan", 10, 100, unit=PERCENTAGE),
    _NumberSpec("fan.interval", "Lüfter – Intervall", "mdi:fan-clock", 10, 120, unit=UnitOfTime.MINUTES),
    _NumberSpec("fan.onDuration", "Lüfter – Laufzeit je Intervall", "mdi:fan-clock", 1, 60, unit=UnitOfTime.MINUTES),
    _NumberSpec("fan.alwaysOffBelowTemperature", "Lüfter – Aus unter", "mdi:thermometer-low", -10, 30,
                unit=UnitOfTemperature.CELSIUS, device_class=NumberDeviceClass.TEMPERATURE),
    _NumberSpec("fan.alwaysOnAboveTemperature", "Lüfter – Dauerbetrieb über", "mdi:thermometer-high", 15, 45,
                unit=UnitOfTemperature.CELSIUS, device_class=NumberDeviceClass.TEMPERATURE),
    # Fuetterung
    _NumberSpec("feeder.animalCount", "Fütterung – Anzahl Tiere", "mdi:google-circles-communities", 1, 50),
    _NumberSpec("feeder.amountPerAnimal", "Fütterung – Menge pro Tier", "mdi:scale", 10, 200, unit=PERCENTAGE),
    # Strom
    _NumberSpec("power.energySavingActiveBelow", "Strom – Energiesparmodus unter", "mdi:battery-low", 10.5, 12.5,
                step=0.1, unit=UnitOfElectricPotential.VOLT, device_class=NumberDeviceClass.VOLTAGE),
]


PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: KerblSmartCoopCoordinator = entry.runtime_data

    entities: list[NumberEntity] = []
    for device in coordinator.data.get("devices", []):
        if _is_demo_device(device):
            continue
        device_id = str(device.get("id"))
        for spec in _NUMBER_SPECS:
            if _get_path(device, spec.path) is None:
                continue
            entities.append(KerblSmartCoopNumber(coordinator, device_id, spec))

    async_add_entities(entities)


async def async_write_parameter(
    entity: _KerblSmartCoopBaseEntity, path: str, value: Any
) -> None:
    """Gemeinsamer Schreibweg fuer Zahlen und Schalter."""
    try:
        await entity.coordinator.client.async_set_parameter(entity._device_id, path, value)
    except (KerblApiError, KerblAuthError, KerblConnectionError) as err:
        raise HomeAssistantError(f"Kerbl: {err}") from err

    # Sofort anzeigen, danach mit der Cloud abgleichen.
    device = entity._device_data()
    section, _, key = path.partition(".")
    if key and isinstance(device.get(section), dict):
        device[section][key] = value
    entity.coordinator.async_update_listeners()
    await entity.coordinator.async_request_refresh()


class KerblSmartCoopNumber(_KerblSmartCoopBaseEntity, NumberEntity):
    """Eine Einstellung, die sich aus Home Assistant aendern laesst."""

    _attr_mode = NumberMode.BOX
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self, coordinator: KerblSmartCoopCoordinator, device_id: str, spec: _NumberSpec
    ) -> None:
        super().__init__(coordinator, device_id)
        self._spec = spec
        self._attr_unique_id = f"{device_id}_set_{spec.path.replace('.', '_')}"
        self._attr_name = spec.name
        self._attr_icon = spec.icon
        self._attr_native_min_value = spec.minimum
        self._attr_native_max_value = spec.maximum
        self._attr_native_step = spec.step
        self._attr_native_unit_of_measurement = spec.unit
        self._attr_device_class = spec.device_class

    @property
    def native_value(self) -> float | None:
        value = _get_path(self._device_data(), self._spec.path)
        return float(value) if isinstance(value, (int, float)) else None

    async def async_set_native_value(self, value: float) -> None:
        if self._spec.step >= 1:
            new_value: int | float = int(round(value))
        else:
            new_value = round(value, 1)
        await async_write_parameter(self, self._spec.path, new_value)
