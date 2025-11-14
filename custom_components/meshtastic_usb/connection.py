"""Helpers for working with Meshtastic connections."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import ipaddress
import logging
import socket
from contextlib import closing, suppress
from typing import Any, Iterable

from .const import (
    AUTODETECT_SERIAL,
    CONNECTION_TYPE_SERIAL,
    CONNECTION_TYPE_TCP,
    DEFAULT_TCP_PORT,
    IGNORED_PORT_PREFIXES,
    MESHTASTIC_VID_PID,
)

_LOGGER = logging.getLogger(__name__)


class MeshtasticConnectionError(Exception):
    """Raised when a Meshtastic connection could not be established."""


@dataclass
class UsbDevice:
    """Representation of a USB serial device."""

    device: str
    description: str | None = None
    hwid: str | None = None
    manufacturer: str | None = None
    product: str | None = None
    serial_number: str | None = None
    vid: int | None = None
    pid: int | None = None
    location: str | None = None

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
    last_message_type: str | None = None
    last_message_time: int | None = None
    battery_level: float | None = None
    battery_voltage: float | None = None
    temperature: float | None = None
    uptime: int | None = None

    def as_dict(self) -> dict[str, Any]:
        """Serialize the node details."""
        data = asdict(self)
        return {key: value for key, value in data.items() if value not in (None, [], "")}


@dataclass
class MeshtasticDevice:
    """Representation of a Meshtastic device connection."""

    connection_type: str
    serial_port: str | None = None
    tcp_host: str | None = None
    tcp_port: int | None = None
    usb: UsbDevice | None = None
    node: MeshtasticNodeDetails | None = None
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        """Return a serializable representation."""
        data: dict[str, Any] = {"connection_type": self.connection_type}
        if self.serial_port:
            data["serial_port"] = self.serial_port
        if self.tcp_host:
            data["tcp_host"] = self.tcp_host
        if self.tcp_port:
            data["tcp_port"] = self.tcp_port
        if self.usb:
            data["usb"] = self.usb.as_dict()
        if self.node:
            data["node"] = self.node.as_dict()
        if self.error:
            data["error"] = self.error
        return data

    @property
    def identifier(self) -> str:
        """Return an identifier suitable for the device registry."""
        if self.node and self.node.my_node_id:
            return self.node.my_node_id.lower()
        if self.connection_type == CONNECTION_TYPE_SERIAL and self.serial_port:
            return f"serial:{self.serial_port}"
        if self.connection_type == CONNECTION_TYPE_TCP and self.tcp_host:
            port = self.tcp_port or DEFAULT_TCP_PORT
            return f"tcp:{self.tcp_host}:{port}"
        return "unknown"

    @property
    def display_name(self) -> str:
        """Return a human readable name for the device."""
        node = self.node
        name = node.node_name if node and node.node_name else None
        node_id = node.my_node_id if node and node.my_node_id else None
        if name and node_id:
            return f"{name} ({node_id})"
        if name:
            return name
        if node_id:
            return node_id
        if self.connection_type == CONNECTION_TYPE_SERIAL and self.serial_port:
            return f"Serial {self.serial_port}"
        if self.connection_type == CONNECTION_TYPE_TCP and self.tcp_host:
            port = self.tcp_port or DEFAULT_TCP_PORT
            return f"TCP {self.tcp_host}:{port}"
        return "Meshtastic"


@dataclass
class MeshtasticConnectionConfig:
    """Configuration used to establish a Meshtastic connection."""

    connection_type: str
    serial_port: str | None = None
    tcp_host: str | None = None
    tcp_port: int | None = None


@dataclass
class DiscoveredTcpDevice:
    """Representation of a discovered Meshtastic TCP device."""

    host: str
    port: int
    node: MeshtasticNodeDetails | None

    @property
    def title(self) -> str:
        """Return a friendly title for config flow selection."""
        node = self.node
        if node and (node.node_name or node.my_node_id):
            name = node.node_name or node.my_node_id
            return f"{name} ({self.host}:{self.port})"
        return f"{self.host}:{self.port}"


def list_serial_ports() -> list[UsbDevice]:
    """Return a list of available Meshtastic serial ports."""
    try:
        from serial.tools import list_ports
    except ImportError as err:  # pragma: no cover - provided by Home Assistant
        raise MeshtasticConnectionError("pyserial_not_available") from err

    ports: list[UsbDevice] = []
    for port in list_ports.comports():
        if _should_ignore_port(port.device, port.description):
            continue
        if port.vid is None or port.pid is None:
            continue
        if (port.vid, port.pid) not in MESHTASTIC_VID_PID:
            continue
        ports.append(
            UsbDevice(
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
        )
    return ports


def find_serial_device(serial_port: str | None) -> UsbDevice | None:
    """Return the matching USB device for the provided port."""
    desired = None if serial_port in (None, AUTODETECT_SERIAL) else serial_port
    ports = list_serial_ports()
    if desired is None:
        return ports[0] if ports else None
    for port in ports:
        if port.device == desired:
            return port
    return None


def read_meshtastic_device(config: MeshtasticConnectionConfig) -> MeshtasticDevice:
    """Read details for a Meshtastic device described by the config."""
    usb_device: UsbDevice | None = None
    resolved_serial: str | None = None
    tcp_host: str | None = None
    tcp_port: int | None = None

    if config.connection_type == CONNECTION_TYPE_SERIAL:
        usb_device = find_serial_device(config.serial_port)
        if usb_device is None:
            raise MeshtasticConnectionError("serial_port_not_found")
        interface = _create_serial_interface(usb_device.device)
        resolved_serial = usb_device.device
    elif config.connection_type == CONNECTION_TYPE_TCP:
        if not config.tcp_host:
            raise MeshtasticConnectionError("tcp_host_missing")
        port = config.tcp_port or DEFAULT_TCP_PORT
        interface = _create_tcp_interface(config.tcp_host, port)
        tcp_host = config.tcp_host
        tcp_port = port
    else:
        raise MeshtasticConnectionError("invalid_connection_type")

    try:
        node_details = _read_node_details(interface)
    finally:
        with suppress(Exception):
            interface.close()

    device = MeshtasticDevice(
        connection_type=config.connection_type,
        serial_port=resolved_serial,
        tcp_host=tcp_host,
        tcp_port=tcp_port,
        usb=usb_device,
        node=node_details,
    )
    return device


def send_text_message(config: MeshtasticConnectionConfig, message: str, target: str | None) -> None:
    """Send a text message using the provided configuration."""
    interface, _device = _open_interface_from_config(config)
    try:
        if not hasattr(interface, "sendText"):
            raise MeshtasticConnectionError("send_text_not_supported")
        kwargs: dict[str, Any] = {}
        if target:
            kwargs["destinationId"] = target
        interface.sendText(message, **kwargs)
    finally:
        with suppress(Exception):
            interface.close()


def reboot_node(config: MeshtasticConnectionConfig) -> None:
    """Reboot the node referenced by the configuration."""
    interface, _device = _open_interface_from_config(config)
    try:
        if not hasattr(interface, "reboot"):
            raise MeshtasticConnectionError("reboot_not_supported")
        interface.reboot()
    finally:
        with suppress(Exception):
            interface.close()


def set_primary_channel(config: MeshtasticConnectionConfig, channel_name: str) -> None:
    """Set the primary channel by name."""
    interface, _device = _open_interface_from_config(config)
    try:
        if not hasattr(interface, "setPrimaryChannel"):
            raise MeshtasticConnectionError("set_channel_not_supported")
        interface.setPrimaryChannel(channel_name)
    finally:
        with suppress(Exception):
            interface.close()


def discover_tcp_devices(
    port: int = DEFAULT_TCP_PORT,
    timeout: float = 0.5,
    subnet: str | None = None,
) -> list[DiscoveredTcpDevice]:
    """Discover Meshtastic nodes that expose a TCP interface."""
    hosts = _iter_discovery_hosts(subnet)
    discovered: list[DiscoveredTcpDevice] = []
    for host in hosts:
        if host in {"127.0.0.1", "0.0.0.0"}:
            continue
        if not _is_port_open(host, port, timeout):
            continue
        try:
            device = read_meshtastic_device(
                MeshtasticConnectionConfig(
                    connection_type=CONNECTION_TYPE_TCP,
                    tcp_host=host,
                    tcp_port=port,
                )
            )
        except MeshtasticConnectionError:
            continue
        except Exception as exc:  # pragma: no cover - defensive logging
            _LOGGER.debug("Unexpected error while probing %s:%s: %s", host, port, exc)
            continue
        discovered.append(DiscoveredTcpDevice(host=host, port=port, node=device.node))
    return discovered


def _open_interface_from_config(config: MeshtasticConnectionConfig):
    """Return an open interface and associated USB device for the config."""
    if config.connection_type == CONNECTION_TYPE_SERIAL:
        usb_device = find_serial_device(config.serial_port)
        if usb_device is None:
            raise MeshtasticConnectionError("serial_port_not_found")
        return _create_serial_interface(usb_device.device), usb_device
    if config.connection_type == CONNECTION_TYPE_TCP:
        if not config.tcp_host:
            raise MeshtasticConnectionError("tcp_host_missing")
        port = config.tcp_port or DEFAULT_TCP_PORT
        return _create_tcp_interface(config.tcp_host, port), None
    raise MeshtasticConnectionError("invalid_connection_type")


def _create_serial_interface(device_path: str):
    try:
        from meshtastic.serial_interface import SerialInterface
    except ImportError as err:  # pragma: no cover - dependency provided by manifest
        raise MeshtasticConnectionError("meshtastic_library_missing") from err

    try:
        return SerialInterface(device_path, noProto=False)
    except Exception as err:  # pragma: no cover - serial errors originate here
        raise MeshtasticConnectionError(str(err)) from err


def _create_tcp_interface(host: str, port: int):
    try:
        from meshtastic.tcp_interface import TCPInterface
    except ImportError as err:  # pragma: no cover - dependency provided by manifest
        raise MeshtasticConnectionError("meshtastic_library_missing") from err

    try:
        return TCPInterface(host, port=port)
    except Exception as err:  # pragma: no cover - tcp errors originate here
        raise MeshtasticConnectionError(str(err)) from err


def _read_node_details(interface) -> MeshtasticNodeDetails:
    """Populate node details from an open interface."""
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

    device_metrics = my_info_dict.get("device_metrics") or {}
    node_details.battery_level = device_metrics.get("battery_level")
    node_details.battery_voltage = device_metrics.get("voltage") or device_metrics.get("battery_voltage")
    node_details.temperature = device_metrics.get("temperature")
    node_details.uptime = my_info_dict.get("uptime") or device_metrics.get("uptime")

    if (node_details.rssi is None or node_details.snr is None) and nodes:
        my_node = nodes.get(node_details.node_num)
        if my_node is not None:
            node_dict = _protobuf_to_dict(my_node)
            node_details.rssi = node_details.rssi or node_dict.get("rx_rssi")
            node_details.snr = node_details.snr or node_dict.get("rx_snr")

    decoded = last_received_dict.get("decoded") or {}
    node_details.last_message = (
        decoded.get("text")
        or decoded.get("payload")
        or decoded.get("data")
    )
    node_details.last_sender = last_received_dict.get("from") or last_received_dict.get("from_id")
    node_details.last_gateway = last_received_dict.get("gateway_id") or last_received_dict.get("rx_gateway")
    node_details.last_message_type = (
        decoded.get("portnum")
        or last_received_dict.get("portnum")
        or last_received_dict.get("type")
    )
    node_details.last_message_time = (
        last_received_dict.get("rx_time")
        or last_received_dict.get("time")
        or decoded.get("rx_time")
    )

    return node_details


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
            elif isinstance(value, Iterable) and not isinstance(value, (bytes, str)):
                fields[descriptor.name] = [
                    _protobuf_to_dict(item) if hasattr(item, "ListFields") else item
                    for item in value
                ]
            else:
                fields[descriptor.name] = value
        return fields
    except Exception:  # pragma: no cover - last resort fallback
        return {}


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


def _should_ignore_port(device: str, description: str | None) -> bool:
    """Return True if the port should be ignored."""
    for prefix in IGNORED_PORT_PREFIXES:
        if device.startswith(prefix):
            return True
    if description and "virtualbox" in description.lower():
        return True
    return False


def _iter_discovery_hosts(subnet: str | None) -> Iterable[str]:
    """Yield candidate hosts for discovery."""
    if subnet:
        try:
            network = ipaddress.ip_network(subnet, strict=False)
        except ValueError:
            _LOGGER.warning("Invalid subnet '%s' provided for discovery", subnet)
            return []
        return (str(host) for host in network.hosts())

    local_ip = _get_local_ip()
    try:
        network = ipaddress.ip_network(f"{local_ip}/24", strict=False)
    except ValueError:
        return []
    return (str(host) for host in network.hosts())


def _get_local_ip() -> str:
    """Return the best-effort local IP address for the host."""
    with suppress(Exception):
        with closing(socket.socket(socket.AF_INET, socket.SOCK_DGRAM)) as sock:
            with suppress(Exception):
                sock.connect(("8.8.8.8", 80))
                return sock.getsockname()[0]
    with suppress(Exception):
        return socket.gethostbyname(socket.gethostname())
    return "127.0.0.1"


def _is_port_open(host: str, port: int, timeout: float) -> bool:
    """Check if the given TCP port is open."""
    try:
        with closing(socket.create_connection((host, port), timeout=timeout)):
            return True
    except OSError:
        return False

