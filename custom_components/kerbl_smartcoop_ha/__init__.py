"""Kerbl SmartCoop Integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import KerblSmartCoopApiClient
from .const import DOMAIN
from .coordinator import KerblSmartCoopCoordinator
from .exceptions import KerblApiError, KerblAuthError, KerblConnectionError

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.NUMBER, Platform.SWITCH]


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

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
