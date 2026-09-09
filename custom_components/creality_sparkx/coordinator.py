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
import base64
import json
import logging
import re
from typing import Any, Callable

import aiohttp
import websockets
from websockets.exceptions import ConnectionClosed, InvalidURI, WebSocketException

from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    DEFAULT_CAMERA_PORT,
    DEFAULT_MOONRAKER_PORT,
    PING_INTERVAL_SECONDS,
    RECONNECT_DELAY_SECONDS,
    WEBRTC_OFFER_PATH,
    WS_PATH,
)

_LOGGER = logging.getLogger(__name__)

# Matches the base64 PNG embedded between slicer thumbnail markers, e.g.:
#   ; thumbnail begin 260x260 2836
#   ; iVBORw0KGgo...
#   ; thumbnail end
_THUMBNAIL_BLOCK_RE = re.compile(
    r";\s*thumbnail begin\s+(?P<w>\d+)x(?P<h>\d+)\s+\d+\s*\n(?P<body>(?:;.*\n?)+?);\s*thumbnail end",
    re.IGNORECASE,
)


class CrealitySparkXCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Maintains a persistent WebSocket connection to the printer."""

    def __init__(
        self,
        hass: HomeAssistant,
        host: str,
        moonraker_port: int = DEFAULT_MOONRAKER_PORT,
        camera_port: int = DEFAULT_CAMERA_PORT,
        power_switch_entity_id: str | None = None,
    ) -> None:
        super().__init__(hass, _LOGGER, name="creality_sparkx", update_interval=None)
        self.hass = hass
        self.host = host
        self.moonraker_port = moonraker_port
        self.camera_port = camera_port
        self.power_switch_entity_id = power_switch_entity_id
        self.data: dict[str, Any] = {}
        self.available: bool = False
        self._ws: websockets.WebSocketClientProtocol | None = None
        self._listen_task: asyncio.Task | None = None
        self._stop = False
        self._unsub_power_switch: Callable[[], None] | None = None

    @property
    def printer_powered_on(self) -> bool:
        """True unless a bound power switch exists and reports 'off'.

        Lets entities show a clean 'unavailable' instead of a stale last
        reading when the printer's mains power is known to be off, if the
        user has opted into binding an existing HA switch entity to it
        (see the integration's options flow) - the printer has no such
        switch itself.
        """
        if not self.power_switch_entity_id:
            return True
        state = self.hass.states.get(self.power_switch_entity_id)
        if state is None:
            return True
        return state.state != "off"

    @callback
    def _handle_power_switch_event(self, event: Event[EventStateChangedData]) -> None:
        self.async_update_listeners()

    @property
    def ws_url(self) -> str:
        return f"ws://{self.host}{WS_PATH}"

    async def async_start(self) -> None:
        """Start the background listen loop."""
        self._stop = False
        self._listen_task = self.hass.loop.create_task(self._listen_loop())
        if self.power_switch_entity_id:
            self._unsub_power_switch = async_track_state_change_event(
                self.hass, [self.power_switch_entity_id], self._handle_power_switch_event
            )

    async def async_stop(self) -> None:
        """Stop the background listen loop and close the socket."""
        self._stop = True
        if self._listen_task:
            self._listen_task.cancel()
        if self._ws is not None:
            await self._ws.close()
        if self._unsub_power_switch:
            self._unsub_power_switch()
            self._unsub_power_switch = None

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

    # -------------------------------------------------------------------
    # Moonraker (Klipper) REST API - used for print control.
    #
    # SPARKX i7 (and apparently other K-series firmware) runs a full
    # Klipper + Moonraker stack internally, reachable at
    # http://<host>:7125. Its API is documented and stable
    # (https://moonraker.readthedocs.io/), unlike the printer's own
    # proprietary WS control set, so this is used for pause/resume/cancel
    # rather than guessing at undocumented WS command keys.
    # -------------------------------------------------------------------

    @property
    def moonraker_base_url(self) -> str:
        return f"http://{self.host}:{self.moonraker_port}"

    async def _async_moonraker_post(self, path: str) -> bool:
        session = async_get_clientsession(self.hass)
        url = f"{self.moonraker_base_url}{path}"
        try:
            async with session.post(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status >= 400:
                    text = await resp.text()
                    _LOGGER.warning(
                        "Moonraker request %s failed: HTTP %s - %s", url, resp.status, text
                    )
                    return False
                return True
        except (aiohttp.ClientError, TimeoutError) as err:
            _LOGGER.warning("Moonraker request %s failed: %s", url, err)
            return False

    async def async_print_pause(self) -> bool:
        return await self._async_moonraker_post("/printer/print/pause")

    async def async_print_resume(self) -> bool:
        return await self._async_moonraker_post("/printer/print/resume")

    async def async_print_cancel(self) -> bool:
        return await self._async_moonraker_post("/printer/print/cancel")

    async def async_fetch_moonraker_object_query(self, *objects: str) -> dict[str, Any] | None:
        """GET /printer/objects/query?obj1&obj2... - used by diagnostics."""
        session = async_get_clientsession(self.hass)
        query = "&".join(objects)
        url = f"{self.moonraker_base_url}/printer/objects/query?{query}"
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status >= 400:
                    return None
                return await resp.json()
        except (aiohttp.ClientError, TimeoutError, ValueError):
            return None

    # -------------------------------------------------------------------
    # Print preview thumbnail
    #
    # Moonraker's own /server/files/thumbnails endpoint returns 404 on this
    # firmware's Moonraker build, but slicers embed the thumbnail directly
    # in the gcode file as base64 PNG between "; thumbnail begin WxH bytes"
    # and "; thumbnail end" marker comments near the top of the file - this
    # reads it straight from there via Moonraker's file-download endpoint.
    # -------------------------------------------------------------------

    async def async_fetch_current_print_thumbnail(self) -> bytes | None:
        """Return the largest embedded thumbnail PNG for the current print file, if any."""
        filename = self.data.get("printFileName")
        if not filename:
            return None
        # printFileName is a full on-device path; Moonraker's gcodes endpoint
        # wants the path relative to its gcodes root.
        rel_name = filename.split("gcodes/", 1)[-1] if "gcodes/" in filename else filename.lstrip("/")

        session = async_get_clientsession(self.hass)
        url = f"{self.moonraker_base_url}/server/files/gcodes/{rel_name}"
        try:
            headers = {"Range": "bytes=0-16383"}  # thumbnails live near the top of the file
            async with session.get(
                url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status >= 400:
                    return None
                text = await resp.text(errors="ignore")
        except (aiohttp.ClientError, TimeoutError):
            return None

        best_png: bytes | None = None
        best_area = -1
        for match in _THUMBNAIL_BLOCK_RE.finditer(text):
            width, height = int(match.group("w")), int(match.group("h"))
            b64_lines = [
                line.strip().lstrip(";").strip()
                for line in match.group("body").splitlines()
                if line.strip().startswith(";")
            ]
            b64_data = "".join(b64_lines)
            try:
                png_bytes = base64.b64decode(b64_data)
            except (ValueError, TypeError):
                continue
            area = width * height
            if area > best_area:
                best_area = area
                best_png = png_bytes
        return best_png

    # -------------------------------------------------------------------
    # Camera - non-trickle WebRTC signaling
    # -------------------------------------------------------------------

    async def async_webrtc_offer(self, offer_sdp: str) -> str | None:
        """POST a full SDP offer to the printer's local WebRTC endpoint, get the answer SDP back.

        Deliberately does NOT use HA's shared, connection-pooling client
        session here. The printer's own WebRTC signaling server is a tiny
        embedded HTTP server that does not support keep-alive - it closes
        the TCP connection after every response. Reusing a pooled
        connection from HA's shared session (keyed by host, meant for
        real HTTP servers) intermittently hands back a connection the
        printer already closed on its end, which surfaces as
        "Server disconnected" / "Connection reset by peer" - not a real
        offer/answer failure, just a stale-connection reuse bug. A
        dedicated, single-use connection per offer avoids this entirely.
        """
        url = f"http://{self.host}:{self.camera_port}{WEBRTC_OFFER_PATH}"
        body = base64.b64encode(
            json.dumps({"type": "offer", "sdp": offer_sdp}).encode()
        )
        connector = aiohttp.TCPConnector(force_close=True, limit=1, enable_cleanup_closed=True)
        try:
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.post(
                    url,
                    data=body,
                    headers={"Content-Type": "plain/text", "Connection": "close"},
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status >= 400:
                        _LOGGER.warning(
                            "Camera WebRTC offer to %s failed: HTTP %s", url, resp.status
                        )
                        return None
                    raw = await resp.text()
        except (aiohttp.ClientError, TimeoutError) as err:
            _LOGGER.warning("Camera WebRTC offer to %s failed: %s", url, err)
            return None

        try:
            answer = json.loads(base64.b64decode(raw))
        except (ValueError, TypeError) as err:
            _LOGGER.warning("Camera WebRTC answer from %s was not valid: %s", url, err)
            return None
        if answer.get("type") != "answer" or not answer.get("sdp"):
            _LOGGER.warning("Camera WebRTC answer from %s missing sdp: %s", url, answer)
            return None
        return answer["sdp"]
