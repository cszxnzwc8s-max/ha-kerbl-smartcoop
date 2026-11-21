"""Live-Aktualisierung ueber die Socket.IO-Verbindung der Kerbl-Cloud.

So arbeitet auch die Kerbl-App (Mitschnitt 21.11.2026):
- Verbindung zu https://app.kerbl-iot.com, Pfad /ws/v0.1/socket.io,
  angemeldet mit demselben Bearer-Token wie die REST-Abfragen
- danach Event "join_room" mit {"deviceIds": [...], "userId": "..."}
- der Server schickt bei jeder Aenderung das Event "smart-coop_update" mit
  dem kompletten Geraetedatensatz (gleiches Format wie in /device)

Die minuetliche REST-Abfrage laeuft unveraendert weiter und haelt auch das
Token frisch; faellt die Live-Verbindung aus, merkt man davon also nur, dass
Aenderungen wieder bis zu einer Minute brauchen.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

import socketio
from homeassistant.util import dt as dt_util

from .const import LIVE_SOCKETIO_PATH, LIVE_URL

if TYPE_CHECKING:
    from .coordinator import KerblSmartCoopCoordinator

_LOGGER = logging.getLogger(__name__)

_CHECK_INTERVAL = 30  # Sekunden, wie die App ein "check" sendet
_RETRY_DELAYS = (10, 30, 60, 120, 300)


class KerblLiveConnection:
    """Haelt die Live-Verbindung offen und speist Updates in den Coordinator."""

    def __init__(self, coordinator: KerblSmartCoopCoordinator, session: Any) -> None:
        self._coordinator = coordinator
        self._session = session
        self._task: asyncio.Task | None = None
        self._stopping = False
        self.connected = False
        self.last_event: str | None = None

    def start(self) -> None:
        self._task = self._coordinator.hass.async_create_background_task(
            self._run(), "kerbl_smartcoop_ha_live"
        )

    async def stop(self) -> None:
        self._stopping = True
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
        self._set_connected(False)

    def _set_connected(self, value: bool) -> None:
        if self.connected != value:
            self.connected = value
            self._coordinator.async_update_listeners()

    def _room_payload(self) -> dict[str, Any] | None:
        devices = (self._coordinator.data or {}).get("devices", [])
        ids = [str(d["id"]) for d in devices if d.get("id")]
        user_ids = [d.get("userId") for d in devices if d.get("userId")]
        if not ids or not user_ids:
            return None
        return {"deviceIds": ids, "userId": user_ids[0]}

    async def _run(self) -> None:
        attempt = 0
        while not self._stopping:
            try:
                await self._connect_once()
                attempt = 0
            except asyncio.CancelledError:
                raise
            except Exception as err:  # noqa: BLE001 - Live ist optional
                if attempt == 0:
                    _LOGGER.warning("Kerbl Live-Verbindung nicht moeglich: %s", err)
                else:
                    _LOGGER.debug("Kerbl Live-Verbindung erneut fehlgeschlagen: %s", err)
            self._set_connected(False)
            if self._stopping:
                break
            await asyncio.sleep(_RETRY_DELAYS[min(attempt, len(_RETRY_DELAYS) - 1)])
            attempt += 1

    async def _connect_once(self) -> None:
        token, _ = self._coordinator.client.get_tokens()
        room = self._room_payload()
        if not token or not room:
            raise RuntimeError("noch keine Anmeldung oder keine Geraete")

        sio = socketio.AsyncClient(reconnection=False, http_session=self._session)

        @sio.event
        async def connect() -> None:
            await sio.emit("join_room", room)
            await sio.emit("check", "check")
            self._set_connected(True)
            _LOGGER.debug("Kerbl Live-Verbindung steht")

        @sio.event
        async def disconnect(*_args: Any) -> None:
            self._set_connected(False)

        @sio.on("smart-coop_update")
        async def on_update(data: Any) -> None:
            self._handle_update(data)

        await sio.connect(
            LIVE_URL,
            headers={"Authorization": f"Bearer {token}"},
            socketio_path=LIVE_SOCKETIO_PATH,
            wait_timeout=20,
        )
        try:
            while sio.connected and not self._stopping:
                await asyncio.sleep(_CHECK_INTERVAL)
                if sio.connected:
                    await sio.emit("check", "check")
        finally:
            if sio.connected:
                await sio.disconnect()

    def _handle_update(self, data: Any) -> None:
        if not isinstance(data, dict) or not data.get("id"):
            return
        current = self._coordinator.data or {}
        devices = list(current.get("devices", []))
        for index, device in enumerate(devices):
            if str(device.get("id")) == str(data["id"]):
                merged = dict(data)
                merged["_source_key"] = device.get("_source_key")
                devices[index] = merged
                break
        else:
            return  # unbekanntes Geraet (z.B. Demo) - ignorieren
        self.last_event = data.get("currentTime")
        self._coordinator.last_success = dt_util.utcnow()
        self._coordinator.async_set_updated_data({**current, "devices": devices})
