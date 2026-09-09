"""Diagnostics support for the Creality SPARKX integration.

Settings -> Devices & Services -> Creality SPARKX -> (three-dot menu on the
device) -> Download diagnostics. Returns the coordinator's full merged
printer state plus connection details, for troubleshooting/bug reports.
"""
from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import CrealitySparkXCoordinator

# Fields worth redacting if a user pastes diagnostics into a public issue -
# the printer serial number is the closest thing to a device identifier here.
_REDACT_KEYS = {"deviceSn", "sn"}


def _redact(data: dict[str, Any]) -> dict[str, Any]:
    return {k: ("**REDACTED**" if k in _REDACT_KEYS else v) for k, v in data.items()}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    coordinator: CrealitySparkXCoordinator = hass.data[DOMAIN][entry.entry_id]

    moonraker_ok = (
        await coordinator.async_fetch_moonraker_object_query("webhooks") is not None
    )

    return {
        "config_entry": {
            "host": coordinator.host,
            "moonraker_port": coordinator.moonraker_port,
            "camera_port": coordinator.camera_port,
            "power_switch_entity_id": coordinator.power_switch_entity_id,
        },
        "connection": {
            "ws_url": coordinator.ws_url,
            "ws_connected": coordinator.available,
            "printer_powered_on": coordinator.printer_powered_on,
            "moonraker_reachable": moonraker_ok,
            "moonraker_base_url": coordinator.moonraker_base_url,
        },
        "printer_state": _redact(coordinator.data),
    }
