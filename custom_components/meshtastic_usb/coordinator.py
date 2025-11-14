"""Data update coordinator for the Meshtastic integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .connection import (
    MeshtasticConnectionConfig,
    MeshtasticConnectionError,
    MeshtasticDevice,
    read_meshtastic_device,
)
from .const import (
    AUTODETECT_SERIAL,
    CONF_CONNECTION_TYPE,
    CONF_SERIAL_PORT,
    CONF_TCP_HOST,
    CONF_TCP_PORT,
    CONF_UPDATE_INTERVAL,
    CONNECTION_TYPE_SERIAL,
    DEFAULT_TCP_PORT,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class CoordinatorDeviceState:
    """State returned by the coordinator."""

    devices: list[MeshtasticDevice]


class MeshtasticUsbCoordinator(DataUpdateCoordinator[CoordinatorDeviceState]):
    """Coordinator that manages a Meshtastic connection."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.entry = entry
        interval_seconds = entry.options.get(
            CONF_UPDATE_INTERVAL,
            entry.data.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL),
        )
        update_interval = timedelta(seconds=interval_seconds)
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} coordinator {entry.entry_id}",
            update_interval=update_interval,
        )

    @property
    def connection_config(self) -> MeshtasticConnectionConfig:
        """Return the connection configuration for this coordinator."""
        data = self.entry.data
        connection_type: str = data.get(CONF_CONNECTION_TYPE, CONNECTION_TYPE_SERIAL)
        serial_port = data.get(CONF_SERIAL_PORT, AUTODETECT_SERIAL)
        tcp_host = data.get(CONF_TCP_HOST)
        tcp_port = data.get(CONF_TCP_PORT, DEFAULT_TCP_PORT)
        return MeshtasticConnectionConfig(
            connection_type=connection_type,
            serial_port=serial_port,
            tcp_host=tcp_host,
            tcp_port=tcp_port,
        )

    async def _async_update_data(self) -> CoordinatorDeviceState:
        """Fetch the latest device data."""
        config = self.connection_config
        device = await self.hass.async_add_executor_job(_read_device_safe, config)
        return CoordinatorDeviceState(devices=[device])


def _read_device_safe(config: MeshtasticConnectionConfig) -> MeshtasticDevice:
    """Read device data with error handling suitable for the coordinator."""
    try:
        return read_meshtastic_device(config)
    except MeshtasticConnectionError as err:
        _LOGGER.error("Meshtastic connection error: %s", err)
        return MeshtasticDevice(
            connection_type=config.connection_type,
            serial_port=config.serial_port,
            tcp_host=config.tcp_host,
            tcp_port=config.tcp_port,
            error=str(err),
        )
    except Exception as err:  # pragma: no cover - defensive logging
        _LOGGER.exception("Unexpected error while updating Meshtastic data")
        return MeshtasticDevice(
            connection_type=config.connection_type,
            serial_port=config.serial_port,
            tcp_host=config.tcp_host,
            tcp_port=config.tcp_port,
            error=str(err),
        )

