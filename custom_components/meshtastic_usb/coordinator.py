"""Data update coordinator for the Meshtastic USB integration."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import timedelta
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    ATTR_ERROR,
    ATTR_NODE,
    ATTR_USB,
    DOMAIN,
    IGNORED_PORT_PREFIXES,
    MESHTASTIC_VID_PID,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class UsbDevice:
    """Representation of a USB serial device."""

    device: str
    description: str | None
    hwid: str | None
    manufacturer: str | None
    product: str | None
    serial_number: str | None
    vid: int | None
    pid: int | None
    location: str | None

    def as_dict(self) -> dict[str, Any]:
        """Return a dictionary with serializable values."""
        data = asdict(self)
        if self.vid is not None:
            data["vid"] = f"0x{self.vid:04x}"
        if self.pid is not None:
            data["pid"] = f"0x{self.pid:04x}"
        return {key: value for key, value in data.items() if value is not None}


@dataclass
class MeshtasticNodeDetails:
    """Details retrieved from a Meshtastic node."""

    firmware: str | None = None
    node_num: int | None = None
    hw_model: str | None = None
    my_node_id: str | None = None
    node_name: str | None = None
    region: str | None = None
    role: str | None = None
    route_table_size: int | None = None
    channel: str | None = None
    channels: list[str] = field(default_factory=list)
    ble_mac: str | None = None
    ble_name: str | None = None
    rssi: float | None = None
    snr: float | None = None
    airtime_utilization: float | None = None
    last_message: str | None = None
    last_sender: str | None = None
    last_gateway: str | None = None

    def as_dict(self) -> dict[str, Any]:
        """Serialize the node details."""
        data = asdict(self)
        return {key: value for key, value in data.items() if value not in (None, [], "")}


@dataclass
class MeshtasticDevice:
    """A Meshtastic-capable USB device and its node details."""

    usb: UsbDevice
    node: MeshtasticNodeDetails | None = None
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        """Return a serializable representation."""
        data: dict[str, Any] = {ATTR_USB: self.usb.as_dict()}
        if self.node:
            data[ATTR_NODE] = self.node.as_dict()
        if self.error:
            data[ATTR_ERROR] = self.error
        return data


class MeshtasticUsbCoordinator(DataUpdateCoordinator[list[MeshtasticDevice]]):
    """Coordinator that queries connected Meshtastic USB devices."""

    def __init__(self, hass: HomeAssistant, update_interval: timedelta) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} device scanner",
            update_interval=update_interval,
        )

    async def _async_update_data(self) -> list[MeshtasticDevice]:
        """Fetch the latest list of connected Meshtastic USB devices."""
        return await self.hass.async_add_executor_job(_scan_meshtastic_devices)


def _scan_meshtastic_devices() -> list[MeshtasticDevice]:
    """Return the connected Meshtastic USB devices."""
    from serial.tools.list_ports import comports

    devices: list[MeshtasticDevice] = []
    for port in comports():
        if _should_ignore_port(port.device, port.description):
            continue
        if port.vid is None or port.pid is None:
            continue
        if (port.vid, port.pid) not in MESHTASTIC_VID_PID:
            continue

        usb_device = UsbDevice(
            device=port.device,
            description=port.description,
            hwid=port.hwid,
            manufacturer=getattr(port, "manufacturer", None),
            product=getattr(port, "product", None),
            serial_number=getattr(port, "serial_number", None),
            vid=getattr(port, "vid", None),
            pid=getattr(port, "pid", None),
            location=getattr(port, "location", None),
        )

        device_entry = MeshtasticDevice(usb=usb_device)
        try:
            device_entry.node = _read_meshtastic_details(port.device)
        except Exception as err:  # pylint: disable=broad-except
            device_entry.error = str(err)
            _LOGGER.error("Failed to read Meshtastic node on %s: %s", port.device, err)
        devices.append(device_entry)
    return devices


def _should_ignore_port(device: str, description: str | None) -> bool:
    """Return True if the port should be ignored."""
    for prefix in IGNORED_PORT_PREFIXES:
        if device.startswith(prefix):
            return True
    if description and "virtualbox" in description.lower():
        return True
    return False


def _protobuf_to_dict(message: Any) -> dict[str, Any]:
    """Convert a protobuf message into a dictionary."""
    if message is None:
        return {}

    try:
        from google.protobuf.json_format import MessageToDict
    except ImportError:  # pragma: no cover - Home Assistant bundles protobuf
        MessageToDict = None

    if MessageToDict is not None:
        try:
            return MessageToDict(message, preserving_proto_field_name=True)
        except Exception:  # pragma: no cover - fallback below
            pass

    try:
        fields: dict[str, Any] = {}
        for descriptor, value in message.ListFields():
            if hasattr(value, "ListFields"):
                fields[descriptor.name] = _protobuf_to_dict(value)
            elif isinstance(value, list):
                fields[descriptor.name] = [
                    _protobuf_to_dict(item) if hasattr(item, "ListFields") else item
                    for item in value
                ]
            else:
                fields[descriptor.name] = value
        return fields
    except Exception:  # pragma: no cover - last resort fallback
        return {}


def _read_meshtastic_details(device_path: str) -> MeshtasticNodeDetails:
    """Return node details for a Meshtastic radio connected to the given path."""
    from meshtastic.serial_interface import SerialInterface

    interface = SerialInterface(device_path, noProto=False)
    try:
        node_details = MeshtasticNodeDetails()
        my_info = getattr(interface, "myInfo", None)
        radio_config = getattr(interface, "radioConfig", None)
        nodes = getattr(interface, "nodes", {}) or {}
        channels = getattr(interface, "channels", []) or []
        last_received = getattr(interface, "lastReceived", None)

        my_info_dict = _protobuf_to_dict(my_info)
        radio_config_dict = _protobuf_to_dict(radio_config)
        last_received_dict = _protobuf_to_dict(last_received)

        node_details.firmware = my_info_dict.get("firmware_version")
        node_details.node_num = my_info_dict.get("my_node_num")
        node_details.hw_model = my_info_dict.get("hw_model")
        node_details.my_node_id = my_info_dict.get("my_node_id")

        node_info = my_info_dict.get("node_info") or {}
        user_info = node_info.get("user") or {}
        node_details.node_name = user_info.get("long_name") or user_info.get("short_name")

        node_details.region = my_info_dict.get("region") or (
            (radio_config_dict.get("preferences") or {}).get("region")
        )
        node_details.role = (
            (radio_config_dict.get("preferences") or {}).get("role")
            or node_info.get("role")
        )
        node_details.route_table_size = len(nodes)

        ble_info = my_info_dict.get("ble") or my_info_dict.get("ble_info") or {}
        node_details.ble_mac = ble_info.get("macaddr") or ble_info.get("address") or ble_info.get("mac")
        node_details.ble_name = ble_info.get("name") or ble_info.get("hostname")

        node_details.channels = _extract_channel_names(channels)
        if node_details.channels:
            node_details.channel = node_details.channels[0]

        metrics_dict = my_info_dict.get("node_metrics") or {}
        node_details.rssi = (
            metrics_dict.get("rssi")
            or metrics_dict.get("rx_rssi")
            or metrics_dict.get("last_heard_rssi")
        )
        node_details.snr = (
            metrics_dict.get("snr")
            or metrics_dict.get("rx_snr")
            or metrics_dict.get("last_heard_snr")
        )
        node_details.airtime_utilization = (
            metrics_dict.get("air_util_tx")
            or metrics_dict.get("air_util")
            or metrics_dict.get("airtime")
        )

        # Attempt to derive metrics from the node table if missing
        if (node_details.rssi is None or node_details.snr is None) and nodes:
            my_node = nodes.get(node_details.node_num)
            if my_node is not None:
                node_dict = _protobuf_to_dict(my_node)
                node_details.rssi = node_details.rssi or node_dict.get("snr") or node_dict.get("rx_rssi")
                node_details.snr = node_details.snr or node_dict.get("snr") or node_dict.get("rx_snr")

        decoded = last_received_dict.get("decoded") or {}
        node_details.last_message = (
            decoded.get("text")
            or decoded.get("payload")
            or decoded.get("data")
        )
        node_details.last_sender = last_received_dict.get("from") or last_received_dict.get("from_id")
        node_details.last_gateway = last_received_dict.get("gateway_id") or last_received_dict.get("rx_gateway")

        return node_details
    finally:
        try:
            interface.close()
        except Exception:  # pragma: no cover - close best effort
            _LOGGER.debug("Failed to close Meshtastic interface for %s", device_path, exc_info=True)


def _extract_channel_names(channels: list[Any]) -> list[str]:
    """Return a list of channel names from protobuf channel definitions."""
    channel_names: list[str] = []
    for channel in channels:
        channel_dict = _protobuf_to_dict(channel)
        name = (
            (channel_dict.get("settings") or {}).get("name")
            or channel_dict.get("name")
        )
        if name:
            channel_names.append(name)
    return channel_names
