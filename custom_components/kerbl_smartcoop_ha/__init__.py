"""Kerbl SmartCoop Integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import KerblSmartCoopApiClient
from .coordinator import KerblSmartCoopCoordinator
from .live import KerblLiveConnection
from .exceptions import KerblApiError, KerblAuthError, KerblConnectionError

_LOGGER = logging.getLogger(__name__)

# Entitaeten frueherer Versionen, die es nicht mehr gibt: (Plattform, Suffix der
# unique_id). Seit v0.16 deckt die Tor/Tuer-Entitaet (cover) Zustand, Fahrt und
# Zeiten ab; der Roh-Code steht dort als Attribut "roh_status".
_REMOVED_ENTITIES = (
    ("binary_sensor", "_door_state"),
    ("sensor", "_door_state"),
    ("sensor", "_door_last_opened"),
    ("sensor", "_door_last_closed"),
)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.NUMBER, Platform.SWITCH, Platform.COVER]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    session = async_get_clientsession(hass)
    client = KerblSmartCoopApiClient(session)

    try:
        await client.authenticate(entry.data[CONF_EMAIL], entry.data[CONF_PASSWORD])
    except KerblAuthError as err:
        raise ConfigEntryAuthFailed(f"Anmeldung ungueltig: {err}") from err
    except (KerblApiError, KerblConnectionError) as err:
        raise ConfigEntryNotReady(f"Kerbl-Welt nicht erreichbar: {err}") from err

    coordinator = KerblSmartCoopCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    _remove_retired_entities(hass, entry)

    # Live-Updates wie in der App; die minuetliche Abfrage bleibt als Netz.
    coordinator.live = KerblLiveConnection(coordinator, session)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    coordinator.live.start()
    return True


def _remove_retired_entities(hass: HomeAssistant, entry: ConfigEntry) -> None:
    registry = er.async_get(hass)
    for entity in er.async_entries_for_config_entry(registry, entry.entry_id):
        if any(
            entity.domain == domain and entity.unique_id.endswith(suffix)
            for domain, suffix in _REMOVED_ENTITIES
        ):
            _LOGGER.debug("Entferne veraltete Entitaet %s", entity.entity_id)
            registry.async_remove(entity.entity_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        live = getattr(entry.runtime_data, "live", None)
        if live is not None:
            await live.stop()
    return unload_ok
