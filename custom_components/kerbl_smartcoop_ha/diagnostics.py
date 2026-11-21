"""Diagnose-Download fuer Kerbl SmartCoop (Geraeteseite -> 'Diagnose herunterladen')."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import REDACT_KEYS


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    coordinator = entry.runtime_data
    live = getattr(coordinator, "live", None)
    return {
        "entry": {
            "title": "**REDACTED**",
            "data": async_redact_data(dict(entry.data), REDACT_KEYS),
        },
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            "update_interval_s": coordinator.update_interval.total_seconds()
            if coordinator.update_interval
            else None,
        },
        "live": {
            "connected": bool(live and live.connected),
            "last_event_module_time": getattr(live, "last_event", None),
        },
        "data": async_redact_data(coordinator.data, REDACT_KEYS),
    }
