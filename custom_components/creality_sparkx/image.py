"""Print preview image entity for the Creality SPARKX integration."""
from __future__ import annotations

import logging

from homeassistant.components.image import ImageEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DEVICE_MANUFACTURER, DOMAIN
from .coordinator import CrealitySparkXCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: CrealitySparkXCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([CrealitySparkXPreviewImage(hass, coordinator, entry)])


class CrealitySparkXPreviewImage(CoordinatorEntity[CrealitySparkXCoordinator], ImageEntity):
    """Shows the sliced-model thumbnail embedded in the current print's gcode file.

    Read directly from the gcode file via Moonraker (see
    coordinator.async_fetch_current_print_thumbnail) since this printer's
    Moonraker build doesn't populate its own /server/files/thumbnails
    endpoint. Refreshes whenever the current print filename changes.
    """

    _attr_has_entity_name = True
    _attr_translation_key = "print_preview"
    _attr_icon = "mdi:image-outline"

    def __init__(
        self, hass: HomeAssistant, coordinator: CrealitySparkXCoordinator, entry: ConfigEntry
    ) -> None:
        CoordinatorEntity.__init__(self, coordinator)
        ImageEntity.__init__(self, hass)
        self._attr_unique_id = f"{entry.unique_id}_print_preview"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.unique_id or entry.entry_id)},
            manufacturer=DEVICE_MANUFACTURER,
            model=coordinator.data.get("model", "SPARKX i7"),
            name=coordinator.data.get("hostname", entry.title),
        )
        self._last_filename: str | None = None
        self._image_bytes: bytes | None = None

    @property
    def available(self) -> bool:
        return (
            self.coordinator.available
            and self.coordinator.printer_powered_on
            and self._image_bytes is not None
        )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        await self._async_maybe_refresh()

    @callback
    def _handle_coordinator_update(self) -> None:
        self.hass.async_create_task(self._async_maybe_refresh())
        super()._handle_coordinator_update()

    async def _async_maybe_refresh(self) -> None:
        filename = self.coordinator.data.get("printFileName")
        if not filename or filename == self._last_filename:
            return
        self._last_filename = filename
        png = await self.coordinator.async_fetch_current_print_thumbnail()
        if png is None:
            _LOGGER.debug("No embedded thumbnail found for %s", filename)
            return
        self._image_bytes = png
        self._attr_image_last_updated = dt_util.utcnow()
        self.async_write_ha_state()

    async def async_image(self) -> bytes | None:
        return self._image_bytes
