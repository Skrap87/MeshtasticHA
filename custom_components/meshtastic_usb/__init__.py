"""Meshtastic integration setup and services."""

from __future__ import annotations

import logging
from collections.abc import Iterable
from typing import Any, Mapping

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers import config_validation as cv

from .connection import (
    MeshtasticConnectionError,
    reboot_node,
    send_text_message,
    set_primary_channel,
)
from .const import (
    ATTR_CHANNEL_NAME,
    ATTR_ENTRY_ID,
    ATTR_MESSAGE,
    ATTR_TARGET,
    DOMAIN,
    PLATFORMS,
    SERVICE_REFRESH,
    SERVICE_REBOOT,
    SERVICE_SEND_MESSAGE,
    SERVICE_SET_CHANNEL,
)
from .coordinator import MeshtasticUsbCoordinator
from .version import __version__

_LOGGER = logging.getLogger(__name__)

DATA_COORDINATORS = "coordinators"
DATA_SERVICES_REGISTERED = "services_registered"

SERVICE_SEND_MESSAGE_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_ENTRY_ID): cv.string,
        vol.Optional(ATTR_TARGET): cv.string,
        vol.Required(ATTR_MESSAGE): cv.string,
    }
)

SERVICE_REBOOT_SCHEMA = vol.Schema({vol.Optional(ATTR_ENTRY_ID): cv.string})

SERVICE_SET_CHANNEL_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_ENTRY_ID): cv.string,
        vol.Required(ATTR_CHANNEL_NAME): cv.string,
    }
)

SERVICE_REFRESH_SCHEMA = vol.Schema({vol.Optional(ATTR_ENTRY_ID): cv.string})


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Set up the Meshtastic component."""
    hass.data.setdefault(
        DOMAIN,
        {
            DATA_COORDINATORS: {},
            DATA_SERVICES_REGISTERED: False,
        },
    )
    _LOGGER.debug("Setting up Meshtastic integration version %s", __version__)

    if not hass.data[DOMAIN][DATA_SERVICES_REGISTERED]:
        _async_register_services(hass)
        hass.data[DOMAIN][DATA_SERVICES_REGISTERED] = True

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Meshtastic from a config entry."""
    coordinator = MeshtasticUsbCoordinator(hass, entry)

    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception as err:  # pragma: no cover - defensive startup guard
        raise ConfigEntryNotReady from err

    hass.data[DOMAIN][DATA_COORDINATORS][entry.entry_id] = coordinator

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN][DATA_COORDINATORS].pop(entry.entry_id, None)
    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options updates by reloading the entry."""
    await hass.config_entries.async_reload(entry.entry_id)


def _async_register_services(hass: HomeAssistant) -> None:
    """Register Meshtastic domain services."""

    async def _async_call_with_connection(
        call: ServiceCall,
        executor,
        *args,
    ) -> None:
        for coordinator in _resolve_coordinators(hass, call.data):
            config = coordinator.connection_config
            try:
                await hass.async_add_executor_job(executor, config, *args)
            except MeshtasticConnectionError as err:
                raise HomeAssistantError(str(err)) from err

    async def _async_handle_send_message(call: ServiceCall) -> None:
        message: str = call.data[ATTR_MESSAGE]
        target: str | None = call.data.get(ATTR_TARGET)
        if not message.strip():
            raise HomeAssistantError("Message cannot be empty")
        await _async_call_with_connection(call, send_text_message, message, target)

    async def _async_handle_reboot(call: ServiceCall) -> None:
        await _async_call_with_connection(call, reboot_node)

    async def _async_handle_set_channel(call: ServiceCall) -> None:
        channel_name: str = call.data[ATTR_CHANNEL_NAME]
        if not channel_name.strip():
            raise HomeAssistantError("Channel name cannot be empty")
        await _async_call_with_connection(call, set_primary_channel, channel_name)

    async def _async_handle_refresh(call: ServiceCall) -> None:
        for coordinator in _resolve_coordinators(hass, call.data):
            await coordinator.async_request_refresh()

    hass.services.async_register(
        DOMAIN,
        SERVICE_SEND_MESSAGE,
        _async_handle_send_message,
        schema=SERVICE_SEND_MESSAGE_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_REBOOT,
        _async_handle_reboot,
        schema=SERVICE_REBOOT_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_CHANNEL,
        _async_handle_set_channel,
        schema=SERVICE_SET_CHANNEL_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_REFRESH,
        _async_handle_refresh,
        schema=SERVICE_REFRESH_SCHEMA,
    )


def _resolve_coordinators(
    hass: HomeAssistant, data: Mapping[str, Any]
) -> Iterable[MeshtasticUsbCoordinator]:
    """Return the coordinators targeted by a service call."""
    entry_id: str | None = data.get(ATTR_ENTRY_ID)
    coordinators: dict[str, MeshtasticUsbCoordinator] = hass.data[DOMAIN][
        DATA_COORDINATORS
    ]

    if entry_id:
        coordinator = coordinators.get(entry_id)
        if coordinator is None:
            raise HomeAssistantError(f"Unknown Meshtastic entry_id: {entry_id}")
        return [coordinator]

    if len(coordinators) == 1:
        return list(coordinators.values())

    if not coordinators:
        raise HomeAssistantError("No Meshtastic entries configured")

    raise HomeAssistantError("Multiple Meshtastic entries configured; provide entry_id")
