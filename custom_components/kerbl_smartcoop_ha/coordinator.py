"""DataUpdateCoordinator fuer Kerbl SmartCoop."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import KerblSmartCoopApiClient
from .const import DEVICE_LIST_KEYS, DOMAIN, UPDATE_INTERVAL_SECONDS
from .exceptions import KerblApiError, KerblAuthError, KerblConnectionError

_LOGGER = logging.getLogger(__name__)


class KerblSmartCoopCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Fragt periodisch den gemeinsamen Kerbl-Welt /device-Endpunkt ab."""

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, client: KerblSmartCoopApiClient
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=UPDATE_INTERVAL_SECONDS),
        )
        self.client = client
        self.entry = entry

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            raw = await self.client.async_get_raw_devices()
        except KerblAuthError as err:
            raise UpdateFailed(f"Anmeldung ungueltig: {err}") from err
        except (KerblApiError, KerblConnectionError) as err:
            raise UpdateFailed(f"Abfrage fehlgeschlagen: {err}") from err

        # SmartCoop-Hardware kann laut Server auf zwei getrennte Kategorien
        # aufgeteilt sein: der Stallcontroller/Klima unter "smartCoop" und
        # das Tuermodul separat unter "smartChickenDoor". Beide werden
        # zusammengefuehrt; jedes Geraet wird mit seiner Quelle markiert
        # (_source_key), damit im Rohdaten-Sensor erkennbar bleibt, woher
        # es kommt.
        devices: list[dict[str, Any]] = []
        for key in DEVICE_LIST_KEYS:
            found = raw.get(key) or []
            for device in found:
                device = dict(device)
                device["_source_key"] = key
                devices.append(device)

        if not devices:
            _LOGGER.warning(
                "Keine SmartCoop-Geraete unter %s gefunden (alle leer). "
                "Vorhandene Top-Level-Schluessel in der Antwort: %s. Pruefe, "
                "ob die Hardware bereits in der Kerbl-Welt-App mit dem "
                "Account gekoppelt ist - die HA-Integration kann nur "
                "Geraete sehen, die dort schon registriert sind.",
                DEVICE_LIST_KEYS,
                list(raw.keys()),
            )

        return {"devices": devices, "raw_top_level_keys": list(raw.keys())}
