"""Config flow for the Creality SPARKX integration."""
from __future__ import annotations

import json
import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_CAMERA_PORT,
    CONF_HOST,
    CONF_MOONRAKER_PORT,
    CONF_POWER_SWITCH_ENTITY_ID,
    DEFAULT_CAMERA_PORT,
    DEFAULT_MOONRAKER_PORT,
    DOMAIN,
    INFO_PATH,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_SCHEMA = vol.Schema({vol.Required(CONF_HOST): str})


async def _async_validate_host(hass, host: str) -> dict[str, Any]:
    """Hit the printer's /info endpoint to confirm it's reachable and get its serial."""
    session = async_get_clientsession(hass)
    url = f"http://{host}{INFO_PATH}"
    async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
        resp.raise_for_status()
        text = await resp.text()
        return json.loads(text)


class CrealitySparkXConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Creality SPARKX."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            try:
                info = await _async_validate_host(self.hass, host)
            except (aiohttp.ClientError, TimeoutError, ValueError):
                errors["base"] = "cannot_connect"
            else:
                serial = info.get("sn") or host
                await self.async_set_unique_id(serial)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"Creality {info.get('model', 'SPARKX')} ({host})",
                    data={CONF_HOST: host},
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_SCHEMA, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> CrealitySparkXOptionsFlow:
        return CrealitySparkXOptionsFlow(config_entry)


class CrealitySparkXOptionsFlow(config_entries.OptionsFlow):
    """Optional advanced settings: bind an existing power switch, override ports.

    Everything here is optional - the integration works without touching
    this. Binding a power switch here lets entities show a clean
    'unavailable' instead of a stale reading when the printer's mains power
    is known to be off (there's no such switch on the printer itself).
    """

    def __init__(self, config_entry: ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            cleaned = {
                CONF_POWER_SWITCH_ENTITY_ID: user_input.get(CONF_POWER_SWITCH_ENTITY_ID) or None,
                CONF_MOONRAKER_PORT: user_input.get(
                    CONF_MOONRAKER_PORT, DEFAULT_MOONRAKER_PORT
                ),
                CONF_CAMERA_PORT: user_input.get(CONF_CAMERA_PORT, DEFAULT_CAMERA_PORT),
            }
            return self.async_create_entry(title="", data=cleaned)

        current = self.config_entry.options
        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_POWER_SWITCH_ENTITY_ID,
                    description={
                        "suggested_value": current.get(CONF_POWER_SWITCH_ENTITY_ID)
                    },
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="switch")
                ),
                vol.Optional(
                    CONF_MOONRAKER_PORT,
                    default=current.get(CONF_MOONRAKER_PORT, DEFAULT_MOONRAKER_PORT),
                ): int,
                vol.Optional(
                    CONF_CAMERA_PORT,
                    default=current.get(CONF_CAMERA_PORT, DEFAULT_CAMERA_PORT),
                ): int,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
