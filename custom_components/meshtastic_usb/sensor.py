"""Sensor platform for the Meshtastic integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, TIME_SECONDS, UnitOfElectricPotential, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .connection import MeshtasticDevice, MeshtasticNodeDetails
from .const import (
    ATTR_DEVICES,
    ATTR_ERROR,
    ATTR_TCP,
    DOMAIN,
    SENSOR_BATTERY_LEVEL,
    SENSOR_BATTERY_VOLTAGE,
    SENSOR_CHANNEL,
    SENSOR_FIRMWARE,
    SENSOR_LAST_MESSAGE,
    SENSOR_NODE_ID,
    SENSOR_RSSI,
    SENSOR_SNR,
    SENSOR_TEMPERATURE,
    SENSOR_UPTIME,
)
from .coordinator import CoordinatorDeviceState, MeshtasticUsbCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Meshtastic sensors from a config entry."""
    coordinator: MeshtasticUsbCoordinator = hass.data[DOMAIN]["coordinators"][
        entry.entry_id
    ]

    entities: list[SensorEntity] = [
        MeshtasticDeviceSensor(coordinator, entry),
        MeshtasticFirmwareSensor(coordinator, entry),
        MeshtasticNodeIdSensor(coordinator, entry),
        MeshtasticChannelSensor(coordinator, entry),
        MeshtasticRssiSensor(coordinator, entry),
        MeshtasticSnrSensor(coordinator, entry),
        MeshtasticLastMessageSensor(coordinator, entry),
        MeshtasticBatteryLevelSensor(coordinator, entry),
        MeshtasticBatteryVoltageSensor(coordinator, entry),
        MeshtasticTemperatureSensor(coordinator, entry),
        MeshtasticUptimeSensor(coordinator, entry),
    ]

    async_add_entities(entities, True)


class MeshtasticCoordinatorEntity(CoordinatorEntity[MeshtasticUsbCoordinator]):
    """Common base for Meshtastic coordinator entities."""

    def __init__(self, coordinator: MeshtasticUsbCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry

    @property
    def _state(self) -> CoordinatorDeviceState | None:
        return self.coordinator.data

    @property
    def _devices(self) -> list[MeshtasticDevice]:
        state = self._state
        if not state:
            return []
        return state.devices

    @property
    def _primary_device(self) -> MeshtasticDevice | None:
        devices = self._devices
        for device in devices:
            if device.node is not None:
                return device
        return devices[0] if devices else None

    @property
    def device_info(self) -> dict[str, Any]:
        device = self._primary_device
        identifier = self._entry.entry_id
        if device and device.identifier != "unknown":
            identifier = device.identifier
        identifiers = {(DOMAIN, identifier)}
        name = "Meshtastic"
        model = None
        sw_version = None

        if device:
            if device.node:
                node = device.node
                if node.node_name and node.my_node_id:
                    name = f"Meshtastic {node.node_name} ({node.my_node_id})"
                elif node.node_name:
                    name = f"Meshtastic {node.node_name}"
                elif node.my_node_id:
                    name = f"Meshtastic {node.my_node_id}"
                model = node.hw_model
                sw_version = node.firmware
            elif device.serial_port:
                name = f"Meshtastic Serial {device.serial_port}"
            elif device.tcp_host:
                port = device.tcp_port
                name = f"Meshtastic {device.tcp_host}:{port}" if port else f"Meshtastic {device.tcp_host}"

        info: dict[str, Any] = {
            "identifiers": identifiers,
            "manufacturer": "Meshtastic",
            "name": name,
        }
        if model:
            info["model"] = model
        if sw_version:
            info["sw_version"] = sw_version
        return info


class MeshtasticDeviceSensor(MeshtasticCoordinatorEntity, SensorEntity):
    """Sensor exposing the connection state."""

    _attr_icon = "mdi:radio-tower"
    _attr_native_unit_of_measurement = "devices"

    def __init__(self, coordinator: MeshtasticUsbCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_name = "Meshtastic devices"
        self._attr_unique_id = f"{entry.entry_id}_devices"

    @property
    def native_value(self) -> int:
        devices = self._devices
        if not devices:
            return 0
        available = [device for device in devices if device.node]
        return len(available)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {ATTR_DEVICES: [device.as_dict() for device in self._devices]}


class MeshtasticNodeSensor(MeshtasticCoordinatorEntity, SensorEntity):
    """Base class for sensors that read values from the node."""

    def __init__(
        self,
        coordinator: MeshtasticUsbCoordinator,
        entry: ConfigEntry,
        sensor_key: str,
        name: str,
        icon: str | None = None,
    ) -> None:
        super().__init__(coordinator, entry)
        self._sensor_key = sensor_key
        self._attr_name = name
        self._attr_unique_id = f"{entry.entry_id}_{sensor_key}"
        if icon:
            self._attr_icon = icon

    def _value_from_node(self, node: MeshtasticNodeDetails) -> Any:  # pragma: no cover
        raise NotImplementedError

    @property
    def native_value(self) -> Any:
        device = self._primary_device
        if not device or not device.node:
            return None
        return self._value_from_node(device.node)

    @property
    def available(self) -> bool:
        device = self._primary_device
        return bool(super().available and device and device.node)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        device = self._primary_device
        if not device:
            return {}
        attrs: dict[str, Any] = {}
        if device.node:
            attrs.update(device.node.as_dict())
        if device.serial_port:
            attrs["serial_port"] = device.serial_port
        if device.tcp_host:
            attrs[ATTR_TCP] = {
                "host": device.tcp_host,
                "port": device.tcp_port,
            }
        if device.error:
            attrs[ATTR_ERROR] = device.error
        return attrs


class MeshtasticFirmwareSensor(MeshtasticNodeSensor):
    """Sensor exposing the firmware version."""

    _attr_icon = "mdi:chip"

    def __init__(self, coordinator: MeshtasticUsbCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, SENSOR_FIRMWARE, "Meshtastic firmware")

    def _value_from_node(self, node: MeshtasticNodeDetails) -> Any:
        return node.firmware


class MeshtasticNodeIdSensor(MeshtasticNodeSensor):
    """Sensor exposing the node ID."""

    _attr_icon = "mdi:identifier"

    def __init__(self, coordinator: MeshtasticUsbCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, SENSOR_NODE_ID, "Meshtastic node ID")

    def _value_from_node(self, node: MeshtasticNodeDetails) -> Any:
        return node.my_node_id


class MeshtasticChannelSensor(MeshtasticNodeSensor):
    """Sensor exposing the active channel."""

    _attr_icon = "mdi:radio"

    def __init__(self, coordinator: MeshtasticUsbCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, SENSOR_CHANNEL, "Meshtastic channel")

    def _value_from_node(self, node: MeshtasticNodeDetails) -> Any:
        return node.channel


class MeshtasticRssiSensor(MeshtasticNodeSensor):
    """Sensor exposing the RSSI value."""

    _attr_device_class = SensorDeviceClass.SIGNAL_STRENGTH
    _attr_icon = "mdi:signal"

    def __init__(self, coordinator: MeshtasticUsbCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, SENSOR_RSSI, "Meshtastic RSSI")

    def _value_from_node(self, node: MeshtasticNodeDetails) -> Any:
        return node.rssi


class MeshtasticSnrSensor(MeshtasticNodeSensor):
    """Sensor exposing the SNR value."""

    _attr_icon = "mdi:chart-line"

    def __init__(self, coordinator: MeshtasticUsbCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, SENSOR_SNR, "Meshtastic SNR")

    def _value_from_node(self, node: MeshtasticNodeDetails) -> Any:
        return node.snr


class MeshtasticLastMessageSensor(MeshtasticNodeSensor):
    """Sensor exposing the last received message."""

    _attr_icon = "mdi:message-text"

    def __init__(self, coordinator: MeshtasticUsbCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, SENSOR_LAST_MESSAGE, "Meshtastic last message")

    def _value_from_node(self, node: MeshtasticNodeDetails) -> Any:
        return node.last_message

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attrs = super().extra_state_attributes
        device = self._primary_device
        if not device or not device.node:
            return attrs
        attrs.update(
            {
                "last_sender": device.node.last_sender,
                "last_gateway": device.node.last_gateway,
                "last_message_type": device.node.last_message_type,
                "last_message_time": device.node.last_message_time,
            }
        )
        return attrs


class MeshtasticBatteryLevelSensor(MeshtasticNodeSensor):
    """Sensor exposing the battery level."""

    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_native_unit_of_measurement = PERCENTAGE

    def __init__(self, coordinator: MeshtasticUsbCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, SENSOR_BATTERY_LEVEL, "Meshtastic battery")

    def _value_from_node(self, node: MeshtasticNodeDetails) -> Any:
        return node.battery_level


class MeshtasticBatteryVoltageSensor(MeshtasticNodeSensor):
    """Sensor exposing the battery voltage."""

    _attr_device_class = SensorDeviceClass.VOLTAGE
    _attr_native_unit_of_measurement = UnitOfElectricPotential.VOLT

    def __init__(self, coordinator: MeshtasticUsbCoordinator, entry: ConfigEntry) -> None:
        super().__init__(
            coordinator,
            entry,
            SENSOR_BATTERY_VOLTAGE,
            "Meshtastic battery voltage",
        )

    def _value_from_node(self, node: MeshtasticNodeDetails) -> Any:
        return node.battery_voltage


class MeshtasticTemperatureSensor(MeshtasticNodeSensor):
    """Sensor exposing the device temperature."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    def __init__(self, coordinator: MeshtasticUsbCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, SENSOR_TEMPERATURE, "Meshtastic temperature")

    def _value_from_node(self, node: MeshtasticNodeDetails) -> Any:
        return node.temperature


class MeshtasticUptimeSensor(MeshtasticNodeSensor):
    """Sensor exposing node uptime in seconds."""

    _attr_native_unit_of_measurement = TIME_SECONDS
    _attr_icon = "mdi:clock-outline"

    def __init__(self, coordinator: MeshtasticUsbCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, SENSOR_UPTIME, "Meshtastic uptime")

    def _value_from_node(self, node: MeshtasticNodeDetails) -> Any:
        return node.uptime

