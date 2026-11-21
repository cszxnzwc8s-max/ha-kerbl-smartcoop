"""Config flow fuer Kerbl SmartCoop - richtiger Setup-Assistent statt YAML."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import KerblSmartCoopApiClient
from .const import DOMAIN
from .exceptions import KerblApiError, KerblAuthError, KerblConnectionError

_LOGGER = logging.getLogger(__name__)

STEP_REAUTH_DATA_SCHEMA = vol.Schema({vol.Required(CONF_PASSWORD): str})

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class KerblSmartCoopConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Setup-Assistent: Kerbl-Welt-Login abfragen und pruefen."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            session = async_get_clientsession(self.hass)
            client = KerblSmartCoopApiClient(session)
            try:
                await client.authenticate(
                    user_input[CONF_EMAIL], user_input[CONF_PASSWORD]
                )
            except KerblAuthError:
                errors["base"] = "invalid_auth"
            except KerblConnectionError:
                errors["base"] = "cannot_connect"
            except KerblApiError:
                _LOGGER.exception("Unerwarteter Fehler beim Login")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(user_input[CONF_EMAIL].lower())
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input[CONF_EMAIL], data=user_input
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> config_entries.ConfigFlowResult:
        """Kerbl lehnt das gespeicherte Passwort ab - neu eingeben lassen."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        errors: dict[str, str] = {}
        entry = self._get_reauth_entry()

        if user_input is not None:
            client = KerblSmartCoopApiClient(async_get_clientsession(self.hass))
            try:
                await client.authenticate(entry.data[CONF_EMAIL], user_input[CONF_PASSWORD])
            except KerblAuthError:
                errors["base"] = "invalid_auth"
            except KerblConnectionError:
                errors["base"] = "cannot_connect"
            except KerblApiError:
                _LOGGER.exception("Unerwarteter Fehler beim Login")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_PASSWORD: user_input[CONF_PASSWORD]}
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_REAUTH_DATA_SCHEMA,
            description_placeholders={"email": entry.data[CONF_EMAIL]},
            errors=errors,
        )
