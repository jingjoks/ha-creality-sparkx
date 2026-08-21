"""Data update coordinator for Creality SPARKX printers.

The printer pushes JSON state over a plain WebSocket at ws://<host>/ws with
no authentication. The first message after connecting is a full snapshot;
subsequent messages are partial updates (only changed keys). This
coordinator keeps a merged view of the latest known state and notifies
listeners (entities) whenever new data arrives.

Sending a control command is done by writing a JSON object with the keys
you want to change, e.g. {"lightSw": 0} to turn the chamber light off.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Callable

import websockets
from websockets.exceptions import ConnectionClosed, InvalidURI, WebSocketException

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import PING_INTERVAL_SECONDS, RECONNECT_DELAY_SECONDS, WS_PATH

_LOGGER = logging.getLogger(__name__)


class CrealitySparkXCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Maintains a persistent WebSocket connection to the printer."""

    def __init__(self, hass: HomeAssistant, host: str) -> None:
        super().__init__(hass, _LOGGER, name="creality_sparkx", update_interval=None)
        self.host = host
        self.data: dict[str, Any] = {}
        self.available: bool = False
        self._ws: websockets.WebSocketClientProtocol | None = None
        self._listen_task: asyncio.Task | None = None
        self._stop = False

    @property
    def ws_url(self) -> str:
        return f"ws://{self.host}{WS_PATH}"

    async def async_start(self) -> None:
        """Start the background listen loop."""
        self._stop = False
        self._listen_task = self.hass.loop.create_task(self._listen_loop())

    async def async_stop(self) -> None:
        """Stop the background listen loop and close the socket."""
        self._stop = True
        if self._listen_task:
            self._listen_task.cancel()
        if self._ws is not None:
            await self._ws.close()

    async def _listen_loop(self) -> None:
        """Reconnect-forever loop that keeps self.data fresh."""
        while not self._stop:
            try:
                async with websockets.connect(
                    self.ws_url,
                    ping_interval=PING_INTERVAL_SECONDS,
                    open_timeout=10,
                ) as ws:
                    self._ws = ws
                    self.available = True
                    _LOGGER.debug("Connected to %s", self.ws_url)
                    async for message in ws:
                        self._handle_message(message)
            except (ConnectionClosed, WebSocketException, InvalidURI, OSError) as err:
                self.available = False
                self._ws = None
                self.async_set_updated_data(self.data)
                _LOGGER.debug(
                    "Creality SPARKX connection lost (%s); retrying in %ss",
                    err,
                    RECONNECT_DELAY_SECONDS,
                )
                await asyncio.sleep(RECONNECT_DELAY_SECONDS)
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001 - keep the loop alive no matter what
                _LOGGER.exception("Unexpected error in Creality SPARKX listen loop")
                self.available = False
                await asyncio.sleep(RECONNECT_DELAY_SECONDS)

    def _handle_message(self, message: str | bytes) -> None:
        try:
            payload = json.loads(message)
        except (ValueError, TypeError):
            _LOGGER.debug("Ignoring non-JSON message from printer: %r", message)
            return
        if not isinstance(payload, dict):
            return
        # Messages are partial updates; merge into the running state.
        self.data.update(payload)
        self.available = True
        self.async_set_updated_data(self.data)

    async def async_send_command(self, values: dict[str, Any]) -> bool:
        """Send a control command, e.g. {"lightSw": 0}."""
        if self._ws is None:
            _LOGGER.warning("Cannot send command, not connected to printer")
            return False
        try:
            await self._ws.send(json.dumps(values))
            return True
        except (ConnectionClosed, WebSocketException, OSError) as err:
            _LOGGER.warning("Failed to send command %s: %s", values, err)
            return False
