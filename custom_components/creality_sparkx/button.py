"""Print-control button entities for the Creality SPARKX integration.

These call the printer's Moonraker (Klipper) REST API directly
(http://<host>:7125/printer/print/...) rather than the printer's own
proprietary WebSocket command set - Moonraker's print-control endpoints are
official, documented, and unaffected by the "commands are ignored while
printing" WS limitation noted for the chamber-light switch.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Awaitable, Callable

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEVICE_MANUFACTURER, DOMAIN
from .coordinator import CrealitySparkXCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class CrealityButtonDescription(ButtonEntityDescription):
    action_fn: Callable[[CrealitySparkXCoordinator], Awaitable[bool]]


BUTTON_DESCRIPTIONS: tuple[CrealityButtonDescription, ...] = (
    CrealityButtonDescription(
        key="pause_print",
        translation_key="pause_print",
        icon="mdi:pause",
        action_fn=lambda c: c.async_print_pause(),
    ),
    CrealityButtonDescription(
        key="resume_print",
        translation_key="resume_print",
        icon="mdi:play",
        action_fn=lambda c: c.async_print_resume(),
    ),
    CrealityButtonDescription(
        key="cancel_print",
        translation_key="cancel_print",
        icon="mdi:stop",
        action_fn=lambda c: c.async_print_cancel(),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: CrealitySparkXCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        CrealitySparkXButton(coordinator, entry, desc) for desc in BUTTON_DESCRIPTIONS
    )


class CrealitySparkXButton(CoordinatorEntity[CrealitySparkXCoordinator], ButtonEntity):
    entity_description: CrealityButtonDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: CrealitySparkXCoordinator,
        entry: ConfigEntry,
        description: CrealityButtonDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.unique_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.unique_id or entry.entry_id)},
            manufacturer=DEVICE_MANUFACTURER,
            model=coordinator.data.get("model", "SPARKX i7"),
            name=coordinator.data.get("hostname", entry.title),
        )

    @property
    def available(self) -> bool:
        return self.coordinator.available and self.coordinator.printer_powered_on

    async def async_press(self) -> None:
        ok = await self.entity_description.action_fn(self.coordinator)
        if not ok:
            _LOGGER.warning(
                "%s failed - check that Moonraker is reachable at %s",
                self.entity_description.key,
                self.coordinator.moonraker_base_url,
            )
