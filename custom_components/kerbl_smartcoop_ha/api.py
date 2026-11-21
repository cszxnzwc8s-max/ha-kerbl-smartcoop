"""Minimal Kerbl-Welt API client, scoped to what SmartCoop needs.

Der Auth-Flow (Endpunkte, Payload- und Token-Feldnamen) ist aus dem
öffentlichen Quellcode von kerblwelt-api (PyPI, MIT-Lizenz) uebernommen -
dort fuer die Weidezaun-Geräte bestätigt funktionierend, und da SmartCoop
denselben Kerbl-Welt-Account/Backend nutzt, gilt derselbe Login-Flow auch
hier. Die Geräteliste (/device) wird hier bewusst *roh* durchgereicht,
da die genauen Feldnamen innerhalb eines SmartCoop-Geräts noch nicht
bekannt sind.
"""

from __future__ import annotations

import logging
from typing import Any

import aiohttp

from .const import (
    BASE_URL,
    ENDPOINT_AUTH_REFRESH,
    ENDPOINT_AUTH_SIGN_IN,
    ENDPOINT_DEVICES,
    ENDPOINT_PARAMETER,
)
from .exceptions import KerblApiError, KerblAuthError, KerblConnectionError

_LOGGER = logging.getLogger(__name__)


class KerblSmartCoopApiClient:
    """Kleiner Client fuer das Kerbl-Welt-Backend."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        self._session = session
        self._access_token: str | None = None
        self._refresh_token: str | None = None

    @property
    def is_authenticated(self) -> bool:
        return self._access_token is not None

    def get_tokens(self) -> tuple[str | None, str | None]:
        return self._access_token, self._refresh_token

    def set_tokens(self, access_token: str, refresh_token: str) -> None:
        self._access_token = access_token
        self._refresh_token = refresh_token

    async def authenticate(self, email: str, password: str) -> None:
        """Anmelden und Tokens speichern."""
        url = f"{BASE_URL}{ENDPOINT_AUTH_SIGN_IN}"
        payload = {"email": email, "password": password}
        try:
            async with self._session.post(url, json=payload) as resp:
                if resp.status == 201:
                    data = await resp.json()
                    self._access_token = data["accessToken"]
                    self._refresh_token = data["refreshToken"]
                    return
                if resp.status == 401:
                    raise KerblAuthError("Ungueltige E-Mail oder Passwort")
                text = await resp.text()
                raise KerblApiError(f"Login fehlgeschlagen ({resp.status}): {text}")
        except aiohttp.ClientError as err:
            raise KerblConnectionError(f"Verbindung fehlgeschlagen: {err}") from err

    async def _refresh(self) -> None:
        if not self._refresh_token:
            raise KerblAuthError("Keine Sitzung vorhanden - erneut anmelden")
        url = f"{BASE_URL}{ENDPOINT_AUTH_REFRESH}"
        try:
            async with self._session.post(
                url, json={"refreshToken": self._refresh_token}
            ) as resp:
                if resp.status == 201:
                    data = await resp.json()
                    self._access_token = data["accessToken"]
                    self._refresh_token = data["refreshToken"]
                    return
                self._access_token = None
                self._refresh_token = None
                raise KerblAuthError("Sitzung abgelaufen - erneut anmelden")
        except aiohttp.ClientError as err:
            raise KerblConnectionError(f"Verbindung fehlgeschlagen: {err}") from err

    async def async_get_raw_devices(self) -> dict[str, Any]:
        """Rohe /device-Antwort abrufen (alle Kerbl-Welt-Geraetetypen des Accounts)."""
        if not self._access_token:
            raise KerblAuthError("Nicht angemeldet")

        url = f"{BASE_URL}{ENDPOINT_DEVICES}"

        try:
            headers = {"Authorization": f"Bearer {self._access_token}"}
            async with self._session.get(url, headers=headers) as resp:
                if resp.status == 200:
                    return await resp.json()
                if resp.status == 401:
                    await self._refresh()
                    headers = {"Authorization": f"Bearer {self._access_token}"}
                    async with self._session.get(url, headers=headers) as retry_resp:
                        if retry_resp.status == 200:
                            return await retry_resp.json()
                        text = await retry_resp.text()
                        raise KerblApiError(
                            f"Geraeteabfrage fehlgeschlagen ({retry_resp.status}): {text}"
                        )
                text = await resp.text()
                raise KerblApiError(f"Geraeteabfrage fehlgeschlagen ({resp.status}): {text}")
        except aiohttp.ClientError as err:
            raise KerblConnectionError(f"Verbindung fehlgeschlagen: {err}") from err

    async def async_set_parameter(self, device_id: str, path: str, value: int | float) -> None:
        """Eine Einstellung am Geraet setzen (z.B. door.relativeOpeningBrightness).

        Entspricht dem, was die Kerbl-App beim Aendern einer Einstellung sendet.
        Die Cloud uebertraegt den Wert ans Modul, sobald es online ist.
        """
        if not self._access_token:
            raise KerblAuthError("Nicht angemeldet")
        url = f"{BASE_URL}{ENDPOINT_PARAMETER.format(device_id=device_id, path=path)}"
        payload = {"value": value}
        try:
            for attempt in range(2):
                headers = {"Authorization": f"Bearer {self._access_token}"}
                async with self._session.patch(url, headers=headers, json=payload) as resp:
                    if resp.status == 401 and attempt == 0:
                        await self._refresh()
                        continue
                    text = await resp.text()
                    if resp.status != 200:
                        raise KerblApiError(
                            f"Einstellung {path} konnte nicht gesetzt werden ({resp.status}): {text}"
                        )
                    try:
                        data = await resp.json(content_type=None)
                    except ValueError:
                        data = {}
                    if isinstance(data, dict) and data.get("success") is False:
                        raise KerblApiError(f"Kerbl hat {path}={value} abgelehnt: {text}")
                    return
        except aiohttp.ClientError as err:
            raise KerblConnectionError(f"Verbindung fehlgeschlagen: {err}") from err
