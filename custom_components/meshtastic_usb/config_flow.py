"""Config flow for the Meshtastic integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback

from .connection import (
    DiscoveredTcpDevice,
    MeshtasticConnectionConfig,
    MeshtasticConnectionError,
    MeshtasticDevice,
    discover_tcp_devices,
    list_serial_ports,
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
    CONNECTION_TYPE_TCP,
    DEFAULT_TCP_PORT,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class MeshtasticUsbConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Meshtastic."""

    VERSION = 1

    def __init__(self) -> None:
        self._connection_type: str | None = None
        self._discovered_devices: dict[str, DiscoveredTcpDevice] = {}

    async def async_step_user(
        self, user_input: Mapping[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Handle the initial step where the connection type is selected."""
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_CONNECTION_TYPE): vol.In(
                            {
                                CONNECTION_TYPE_SERIAL: "serial",
                                CONNECTION_TYPE_TCP: "tcp",
                            }
                        )
                    }
                ),
            )

        self._connection_type = user_input[CONF_CONNECTION_TYPE]
        if self._connection_type == CONNECTION_TYPE_SERIAL:
            return await self.async_step_serial()
        if self._connection_type == CONNECTION_TYPE_TCP:
            return await self.async_step_tcp()
        return self.async_abort(reason="invalid_connection")

    async def async_step_serial(
        self, user_input: Mapping[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Handle configuration for serial connections."""
        assert self._connection_type == CONNECTION_TYPE_SERIAL

        errors: dict[str, str] = {}
        try:
            ports = await self.hass.async_add_executor_job(list_serial_ports)
        except MeshtasticConnectionError as err:
            _LOGGER.error("Unable to list Meshtastic serial ports: %s", err)
            ports = []
            errors["base"] = self._map_error(str(err))

        options: dict[str, str] = {AUTODETECT_SERIAL: "autodetect"}
        for port in ports:
            label = port.device
            if port.description:
                label = f"{port.device} ({port.description})"
            options[port.device] = label

        if user_input is not None:
            selected_port = user_input[CONF_SERIAL_PORT]
            update_interval = user_input[CONF_UPDATE_INTERVAL]
            if self._is_duplicate_serial(selected_port):
                return self.async_abort(reason="already_configured")

            config = MeshtasticConnectionConfig(
                connection_type=CONNECTION_TYPE_SERIAL,
                serial_port=selected_port,
            )
            device, error_key = await self._async_try_connect(config)
            if error_key is None and device is not None:
                return await self._async_create_entry(device, config, update_interval)
            errors["base"] = error_key or "cannot_connect"

        schema = vol.Schema(
            {
                vol.Required(CONF_SERIAL_PORT, default=AUTODETECT_SERIAL): vol.In(options),
                vol.Required(
                    CONF_UPDATE_INTERVAL, default=DEFAULT_UPDATE_INTERVAL
                ): vol.All(vol.Coerce(int), vol.Range(min=10, max=3600)),
            }
        )
        return self.async_show_form(step_id="serial", data_schema=schema, errors=errors)

    async def async_step_tcp(
        self, user_input: Mapping[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Show menu for TCP configuration options."""
        return self.async_show_menu(
            step_id="tcp",
            menu_options={
                "tcp_manual": "manual",
                "tcp_discovery": "discovery",
            },
        )

    async def async_step_tcp_manual(
        self, user_input: Mapping[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Handle manual TCP configuration."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_TCP_HOST]
            port = user_input.get(CONF_TCP_PORT, DEFAULT_TCP_PORT)
            update_interval = user_input[CONF_UPDATE_INTERVAL]

            if self._is_duplicate_tcp(host, port):
                return self.async_abort(reason="already_configured")

            config = MeshtasticConnectionConfig(
                connection_type=CONNECTION_TYPE_TCP,
                tcp_host=host,
                tcp_port=port,
            )
            device, error_key = await self._async_try_connect(config)
            if error_key is None and device is not None:
                return await self._async_create_entry(device, config, update_interval)
            errors["base"] = error_key or "cannot_connect"

        schema = vol.Schema(
            {
                vol.Required(CONF_TCP_HOST): str,
                vol.Required(CONF_TCP_PORT, default=DEFAULT_TCP_PORT): vol.All(
                    vol.Coerce(int), vol.Range(min=1, max=65535)
                ),
                vol.Required(
                    CONF_UPDATE_INTERVAL, default=DEFAULT_UPDATE_INTERVAL
                ): vol.All(vol.Coerce(int), vol.Range(min=10, max=3600)),
            }
        )
        return self.async_show_form(step_id="tcp_manual", data_schema=schema, errors=errors)

    async def async_step_tcp_discovery(
        self, user_input: Mapping[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Handle discovery of TCP devices."""
        errors: dict[str, str] = {}

        if user_input is not None:
            selection = user_input.get("device")
            update_interval = user_input[CONF_UPDATE_INTERVAL]
            if not selection or selection not in self._discovered_devices:
                errors["base"] = "device_not_found"
            else:
                discovered = self._discovered_devices[selection]
                if self._is_duplicate_tcp(discovered.host, discovered.port):
                    return self.async_abort(reason="already_configured")
                config = MeshtasticConnectionConfig(
                    connection_type=CONNECTION_TYPE_TCP,
                    tcp_host=discovered.host,
                    tcp_port=discovered.port,
                )
                device, error_key = await self._async_try_connect(config)
                if error_key is None and device is not None:
                    return await self._async_create_entry(device, config, update_interval)
                errors["base"] = error_key or "cannot_connect"

        if not errors:
            await self._async_run_discovery()
            if not self._discovered_devices:
                errors["base"] = "no_devices_found"

        options = {
            key: device.title for key, device in self._discovered_devices.items()
        }
        schema = vol.Schema(
            {
                vol.Required("device"): vol.In(options) if options else str,
                vol.Required(
                    CONF_UPDATE_INTERVAL, default=DEFAULT_UPDATE_INTERVAL
                ): vol.All(vol.Coerce(int), vol.Range(min=10, max=3600)),
            }
        )
        return self.async_show_form(
            step_id="tcp_discovery", data_schema=schema, errors=errors
        )

    async def _async_run_discovery(self) -> None:
        """Populate the discovered TCP devices cache."""
        try:
            devices = await self.hass.async_add_executor_job(discover_tcp_devices)
        except MeshtasticConnectionError as err:
            _LOGGER.error("Meshtastic TCP discovery failed: %s", err)
            self._discovered_devices = {}
            return
        except Exception as err:  # pragma: no cover - defensive logging
            _LOGGER.exception("Unexpected error during Meshtastic discovery")
            self._discovered_devices = {}
            return

        self._discovered_devices = {
            f"{device.host}:{device.port}": device for device in devices
        }

    async def _async_try_connect(
        self, config: MeshtasticConnectionConfig
    ) -> tuple[MeshtasticDevice | None, str | None]:
        """Attempt to connect to a Meshtastic device."""
        try:
            device = await self.hass.async_add_executor_job(read_meshtastic_device, config)
            return device, None
        except MeshtasticConnectionError as err:
            return None, self._map_error(str(err))
        except Exception as err:  # pragma: no cover - defensive logging
            _LOGGER.exception("Unexpected error during Meshtastic connection test")
            return None, "cannot_connect"

    async def _async_create_entry(
        self,
        device: MeshtasticDevice,
        config: MeshtasticConnectionConfig,
        update_interval: int,
    ) -> config_entries.FlowResult:
        """Create the config entry with populated data."""

        unique_id = self._derive_unique_id(device, config)
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()

        data: dict[str, Any] = {
            CONF_CONNECTION_TYPE: config.connection_type,
            CONF_UPDATE_INTERVAL: update_interval,
        }
        if config.connection_type == CONNECTION_TYPE_SERIAL:
            data[CONF_SERIAL_PORT] = config.serial_port or AUTODETECT_SERIAL
        else:
            data[CONF_TCP_HOST] = config.tcp_host
            data[CONF_TCP_PORT] = config.tcp_port or DEFAULT_TCP_PORT

        title = device.display_name if getattr(device, "display_name", None) else None
        if not title:
            if config.connection_type == CONNECTION_TYPE_SERIAL:
                title = "Meshtastic Serial"
            else:
                title = f"Meshtastic {config.tcp_host}:{config.tcp_port}"

        return self.async_create_entry(title=title, data=data)

    def _is_duplicate_serial(self, serial_port: str) -> bool:
        """Return True if a serial configuration already exists."""
        for entry in self._async_current_entries():
            if entry.data.get(CONF_CONNECTION_TYPE) != CONNECTION_TYPE_SERIAL:
                continue
            existing_port = entry.data.get(CONF_SERIAL_PORT, AUTODETECT_SERIAL)
            if existing_port == serial_port:
                return True
        return False

    def _is_duplicate_tcp(self, host: str, port: int) -> bool:
        """Return True if a TCP configuration already exists."""
        for entry in self._async_current_entries():
            if entry.data.get(CONF_CONNECTION_TYPE) != CONNECTION_TYPE_TCP:
                continue
            existing_host = entry.data.get(CONF_TCP_HOST)
            existing_port = int(entry.data.get(CONF_TCP_PORT, DEFAULT_TCP_PORT))
            if existing_host == host and existing_port == port:
                return True
        return False

    def _map_error(self, error: str) -> str:
        """Map connection errors to translation keys."""
        mapping = {
            "serial_port_not_found": "serial_port_not_found",
            "tcp_host_missing": "tcp_host_missing",
            "meshtastic_library_missing": "library_missing",
            "pyserial_not_available": "serial_library_missing",
        }
        return mapping.get(error, "cannot_connect")

    def _derive_unique_id(self, device, config: MeshtasticConnectionConfig) -> str:
        """Return the unique identifier for the config entry."""
        node = getattr(device, "node", None)
        if node and node.my_node_id:
            return node.my_node_id.lower()
        if config.connection_type == CONNECTION_TYPE_SERIAL:
            serial_port = getattr(device, "serial_port", None) or config.serial_port or AUTODETECT_SERIAL
            return f"serial:{serial_port}"
        tcp_host = config.tcp_host or "unknown"
        tcp_port = config.tcp_port or DEFAULT_TCP_PORT
        return f"tcp:{tcp_host}:{tcp_port}"

    @callback
    def async_get_options_flow(self, config_entry: config_entries.ConfigEntry):
        """Return the options flow handler."""
        return MeshtasticUsbOptionsFlow(config_entry)


class MeshtasticUsbOptionsFlow(config_entries.OptionsFlow):
    """Handle options for existing Meshtastic entries."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: Mapping[str, Any] | None = None
    ) -> config_entries.FlowResult:
        """Manage options for the integration."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current_interval = self.config_entry.options.get(
            CONF_UPDATE_INTERVAL,
            self.config_entry.data.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL),
        )
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_UPDATE_INTERVAL, default=current_interval
                ): vol.All(vol.Coerce(int), vol.Range(min=10, max=3600))
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
