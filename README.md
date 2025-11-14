# Meshtastic Home Assistant Integration

This repository provides a custom Home Assistant integration for managing Meshtastic radios from Home Assistant. The integration can communicate with nodes connected locally over USB serial adapters or remotely over TCP/Wi-Fi, optionally discovering nodes on the local network. Each configured node exposes rich telemetry and message metadata to Home Assistant and can be controlled through dedicated services.

## Features

- Configure multiple Meshtastic nodes, each using either USB serial or TCP (Wi-Fi) connectivity.
- Automatically detect compatible USB adapters by VID/PID, or scan the local /24 network for Meshtastic TCP nodes before selecting one in the config flow.
- Query the radio through the official Meshtastic Python API to gather firmware information, hardware model, node identity, channels, BLE details, mesh routing statistics, and device metrics.
- Surface live radio metrics (RSSI, SNR, airtime utilisation, battery level/voltage, temperature, uptime) alongside the most recent received message, sender, gateway, type, and timestamp.
- Register all sensors under a Home Assistant device with manufacturer/model/firmware metadata for easy dashboard grouping.
- Provide Home Assistant services to send messages, reboot the node, change the primary channel, and trigger an immediate refresh.

## Created entities

| Entity | Description |
| --- | --- |
| `sensor.meshtastic_devices` | Number of configured Meshtastic nodes that are currently reachable. Attributes include the raw node details, connection information, and any connection error. |
| `sensor.meshtastic_firmware` | Firmware version reported by the connected node. |
| `sensor.meshtastic_node_id` | Node ID of the local radio. |
| `sensor.meshtastic_channel` | Primary channel name with the full channel list in attributes. |
| `sensor.meshtastic_rssi` | Current RSSI reported by the node (signal strength device class). |
| `sensor.meshtastic_snr` | Current SNR reported by the node. |
| `sensor.meshtastic_last_message` | Text of the last received message plus sender, gateway, message type, and timestamp attributes. |
| `sensor.meshtastic_battery` | Battery level reported by the node (percentage). |
| `sensor.meshtastic_battery_voltage` | Battery voltage reported by the node. |
| `sensor.meshtastic_temperature` | Device temperature reported by the node. |
| `sensor.meshtastic_uptime` | Node uptime in seconds. |

All sensors include extensive attributes such as hardware model, region, role, BLE information, airtime utilisation, route table size, and the raw connection details.

## Home Assistant services

| Service | Description |
| --- | --- |
| `meshtastic_usb.send_message` | Send a text message through the selected Meshtastic node (optionally target a specific node ID). |
| `meshtastic_usb.reboot` | Reboot the node. |
| `meshtastic_usb.set_channel` | Change the primary channel by name. |
| `meshtastic_usb.refresh` | Request an immediate data refresh from the node. |

All services accept an optional `entry_id` when multiple nodes are configured; otherwise the single configured node is used.

## Installation (Home Assistant OS via HACS)

1. Install [HACS](https://hacs.xyz/) if it is not already available in your Home Assistant instance.
2. In Home Assistant, open **HACS → Integrations → ⋮ (three dots) → Custom repositories**.
3. Enter `https://github.com/Skrap87/MeshtasticHA` as the repository URL, choose **Integration** as the category, and click **Add**.
4. The repository now appears in HACS. Click **Download** on the Meshtastic card and restart Home Assistant when prompted. The integration bundles the Meshtastic Python API directly from the official GitHub repository so HACS will fetch the dependency automatically.
5. After Home Assistant restarts, go to **Settings → Devices & Services → + Add Integration**, search for **Meshtastic**, and complete the setup wizard. Choose USB serial or TCP connectivity per node and (optionally) run network discovery for TCP radios.

## Manual installation

1. Copy the `custom_components/meshtastic_usb` folder into the `custom_components` directory of your Home Assistant configuration. If the directory does not exist, create it.
2. Restart Home Assistant. The integration will download the Meshtastic Python API from the official GitHub repository (tag `2.2.27`) on first start so outbound internet access is required for the initial setup.
3. In Home Assistant, navigate to **Settings → Devices & Services → Integrations** and click **Add Integration**.
4. Search for **Meshtastic** and complete the setup wizard.

## USB passthrough tips

The integration communicates directly with the USB serial device. When running Home Assistant inside a hypervisor ensure the radio is passed through to the guest operating system.

### VirtualBox (Home Assistant OS)

1. Shut down the Home Assistant OS VM.
2. In VirtualBox Manager open the VM **Settings → Ports → USB** panel.
3. Enable the USB controller that matches your adapter (USB 2.0 for most radios) and add a USB device filter for the adapter. The VID/PID list below can help you identify the correct device.
4. Start the VM, open Home Assistant, and re-run the Meshtastic config flow.

### Proxmox VE

1. Locate the adapter on the Proxmox host using `lsusb`.
2. Edit the VM configuration (either via the web UI **Hardware → Add → USB Device** or by editing the VM `.conf` file) and attach the USB device using its VID/PID pair.
3. Restart the VM so Home Assistant can access the forwarded USB device.

## Supported USB VID/PID pairs

The integration recognises the following adapters out of the box:

- CP2102 (`10C4:EA60`)
- CH340 (`1A86:7523`)
- CH9102 (`1A86:55D4`)
- RAK4631 bootloader (`239A:8029`)
- RAK4631 application firmware (`239A:8109`)
- Seeed XIAO nRF52840 (`2886:0045`)
- Seeed XIAO RP2040 (`2886:0046`)

If your adapter exposes a different VID/PID pair you can submit an issue or pull request so it can be added to the detection list.

## Versioning

The integration uses calendar-style version numbers that encode the build timestamp in the format `YYYY.MM.DD.HHMM`. The current release is stored in the [`VERSION`](./VERSION) file and mirrored in `custom_components/meshtastic_usb/version.py` so both Home Assistant and human readers can easily determine the installed release.

## Troubleshooting

- VirtualBox host serial ports (`/dev/ttyS*`) are intentionally ignored to avoid false positives. Ensure your adapter is passed through as a USB device, not a legacy serial port.
- If the integration reports an `error` attribute for the detected device, check the Home Assistant logs for the corresponding stack trace. The integration closes and reopens the port on each poll, so the device should recover automatically after transient failures.
