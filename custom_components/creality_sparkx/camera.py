"""Camera entity for the Creality SPARKX integration.

The printer runs its own small WebRTC signaling server for its built-in
camera (confirmed on SPARKX i7 at http://<host>:8000/ - a "Video On Demand"
demo page). It uses a non-trickle offer/answer exchange: the browser
gathers all its local ICE candidates first, then POSTs the complete SDP
offer and gets the complete SDP answer back in one round trip. That maps
directly onto Home Assistant's async WebRTC camera provider API.

NOTE: this printer wiring was reverse-engineered from the demo page's own
JavaScript rather than official documentation (there is none), and could
not be exercised through an actual browser in the environment this was
built in - it's built from the confirmed-correct protocol and should work,
but please check the camera actually shows a live picture in the
Lovelace UI after updating and restarting, and open an issue if it
doesn't.
"""
from __future__ import annotations

import logging

from homeassistant.components.camera import (
    Camera,
    CameraEntityFeature,
    WebRTCAnswer,
    WebRTCSendMessage,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEVICE_MANUFACTURER, DOMAIN
from .coordinator import CrealitySparkXCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: CrealitySparkXCoordinator = hass.data[DOMAIN][entry.entry_id]
    # Only add the camera if this session's snapshot says the printer
    # actually reports camera/WebRTC capability - avoids a dead camera
    # entity on printers/firmware that don't have one.
    if not coordinator.data.get("webrtcSupport") and not coordinator.data.get("video"):
        _LOGGER.debug(
            "Printer does not report webrtcSupport/video - skipping camera entity"
        )
        return
    async_add_entities([CrealitySparkXCamera(coordinator, entry)])


class CrealitySparkXCamera(CoordinatorEntity[CrealitySparkXCoordinator], Camera):
    """Live camera feed via the printer's local WebRTC endpoint."""

    _attr_has_entity_name = True
    _attr_translation_key = "printer_camera"
    _attr_supported_features = CameraEntityFeature.STREAM

    def __init__(self, coordinator: CrealitySparkXCoordinator, entry: ConfigEntry) -> None:
        CoordinatorEntity.__init__(self, coordinator)
        Camera.__init__(self)
        self._attr_unique_id = f"{entry.unique_id}_camera"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.unique_id or entry.entry_id)},
            manufacturer=DEVICE_MANUFACTURER,
            model=coordinator.data.get("model", "SPARKX i7"),
            name=coordinator.data.get("hostname", entry.title),
        )

    @property
    def available(self) -> bool:
        return self.coordinator.available and self.coordinator.printer_powered_on

    async def async_handle_async_webrtc_offer(
        self, offer_sdp: str, session_id: str, send_message: WebRTCSendMessage
    ) -> None:
        """Forward the browser's SDP offer to the printer, relay its answer back."""
        answer_sdp = await self.coordinator.async_webrtc_offer(offer_sdp)
        if answer_sdp is None:
            _LOGGER.warning(
                "Printer camera did not return a WebRTC answer for session %s", session_id
            )
            return
        send_message(WebRTCAnswer(answer_sdp))

    async def async_on_webrtc_candidate(self, session_id: str, candidate) -> None:
        """No-op: the printer's endpoint is non-trickle (full offer -> full answer in one call)."""
        return

    @callback
    def close_webrtc_session(self, session_id: str) -> None:
        """The printer's endpoint is one-shot/stateless on our side - nothing to clean up."""
        return

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        # No plain HTTP snapshot endpoint was found on this printer - the
        # camera is WebRTC-only. Returning None here means the Lovelace
        # camera card falls back to attempting a live stream instead of a
        # static snapshot, which is what we want.
        return None
