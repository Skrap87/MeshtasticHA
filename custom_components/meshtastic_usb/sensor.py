"""Sensor platform for the Meshtastic USB integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTR_DEVICES,
    ATTR_ERROR,
    DOMAIN,
    SENSOR_CHANNEL,
    SENSOR_FIRMWARE,
    SENSOR_LAST_MESSAGE,
    SENSOR_NODE_ID,
    SENSOR_RSSI,
    SENSOR_SNR,
)
from .coordinator import (
    MeshtasticDevice,
    MeshtasticNodeDetails,
    MeshtasticUsbCoordinator,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Meshtastic USB sensor."""
    coordinator: MeshtasticUsbCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            MeshtasticUsbSensor(coordinator),
            MeshtasticFirmwareSensor(coordinator),
            MeshtasticNodeIdSensor(coordinator),
            MeshtasticChannelSensor(coordinator),
            MeshtasticRssiSensor(coordinator),
            MeshtasticSnrSensor(coordinator),
            MeshtasticLastMessageSensor(coordinator),
        ],
        True,
    )


class MeshtasticCoordinatorEntity(CoordinatorEntity[MeshtasticUsbCoordinator]):
    """Coordinator mixin with helper properties."""

    def __init__(self, coordinator: MeshtasticUsbCoordinator) -> None:
        super().__init__(coordinator)

    @property
    def _primary_device(self) -> MeshtasticDevice | None:
        """Return the first device with node details."""
        devices = self.coordinator.data or []
        for device in devices:
            if device.node is not None:
                return device
        return devices[0] if devices else None


class MeshtasticUsbSensor(MeshtasticCoordinatorEntity, SensorEntity):
    """Sensor that exposes connected USB devices."""

    _attr_icon = "mdi:usb-port"
    _attr_name = "Meshtastic USB devices"
    _attr_native_unit_of_measurement = "devices"
    _attr_unique_id = "meshtastic_usb_devices"

    @property
    def native_value(self) -> int:
        """Return the number of connected USB devices."""
        data = self.coordinator.data or []
        return len(data)

    @property
    def extra_state_attributes(self) -> dict[str, list[dict[str, Any]]]:
        """Return details about the connected USB devices."""
        devices = []
        for device in self.coordinator.data or []:
            devices.append(device.as_dict())
        return {ATTR_DEVICES: devices}


class MeshtasticNodeSensor(MeshtasticCoordinatorEntity, SensorEntity):
    """Base class for sensors that expose Meshtastic node data."""

    def __init__(
        self,
        coordinator: MeshtasticUsbCoordinator,
        sensor_key: str,
        name: str,
        icon: str | None = None,
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"meshtastic_usb_{sensor_key}"
        self._attr_name = name
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
        if device.error:
            attrs[ATTR_ERROR] = device.error
        return attrs


class MeshtasticFirmwareSensor(MeshtasticNodeSensor):
    """Sensor exposing the firmware version."""

    _attr_icon = "mdi:chip"

    def __init__(self, coordinator: MeshtasticUsbCoordinator) -> None:
        super().__init__(coordinator, SENSOR_FIRMWARE, "Meshtastic firmware")

    def _value_from_node(self, node: MeshtasticNodeDetails) -> Any:
        return node.firmware


class MeshtasticNodeIdSensor(MeshtasticNodeSensor):
    """Sensor exposing the node ID."""

    _attr_icon = "mdi:identifier"

    def __init__(self, coordinator: MeshtasticUsbCoordinator) -> None:
        super().__init__(coordinator, SENSOR_NODE_ID, "Meshtastic node ID")

    def _value_from_node(self, node: MeshtasticNodeDetails) -> Any:
        return node.my_node_id


class MeshtasticChannelSensor(MeshtasticNodeSensor):
    """Sensor exposing the active channel."""

    _attr_icon = "mdi:radio-tower"

    def __init__(self, coordinator: MeshtasticUsbCoordinator) -> None:
        super().__init__(coordinator, SENSOR_CHANNEL, "Meshtastic channel")

    def _value_from_node(self, node: MeshtasticNodeDetails) -> Any:
        return node.channel


class MeshtasticRssiSensor(MeshtasticNodeSensor):
    """Sensor exposing the RSSI metric."""

    _attr_icon = "mdi:signal"
    _attr_device_class = SensorDeviceClass.SIGNAL_STRENGTH

    def __init__(self, coordinator: MeshtasticUsbCoordinator) -> None:
        super().__init__(coordinator, SENSOR_RSSI, "Meshtastic RSSI")

    def _value_from_node(self, node: MeshtasticNodeDetails) -> Any:
        return node.rssi


class MeshtasticSnrSensor(MeshtasticNodeSensor):
    """Sensor exposing the SNR metric."""

    _attr_icon = "mdi:chart-line"

    def __init__(self, coordinator: MeshtasticUsbCoordinator) -> None:
        super().__init__(coordinator, SENSOR_SNR, "Meshtastic SNR")

    def _value_from_node(self, node: MeshtasticNodeDetails) -> Any:
        return node.snr


class MeshtasticLastMessageSensor(MeshtasticNodeSensor):
    """Sensor exposing the last received message."""

    _attr_icon = "mdi:message-text"

    def __init__(self, coordinator: MeshtasticUsbCoordinator) -> None:
        super().__init__(coordinator, SENSOR_LAST_MESSAGE, "Meshtastic last message")

    def _value_from_node(self, node: MeshtasticNodeDetails) -> Any:
        return node.last_message

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attrs = dict(super().extra_state_attributes)
        device = self._primary_device
        if not device or not device.node:
            return attrs
        attrs.update(
            {
                "last_sender": device.node.last_sender,
                "last_gateway": device.node.last_gateway,
            }
        )
        return attrs
