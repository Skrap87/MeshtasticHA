# Meshtastic Home Assistant Integration 

This repository provides a custom Home Assistant integration for monitoring Meshtastic radios that are attached over USB. The integration automatically discovers supported adapters, connects to the radio using the Meshtastic Python API, and exposes detailed telemetry and message metadata in Home Assistant sensors.

## Features

- Detect Meshtastic-compatible USB adapters by USB VID/PID while ignoring VirtualBox serial shims.
- Query the radio over the official Meshtastic Python API to obtain firmware information, node identity, channels, BLE details, and mesh routing statistics.
- Surface live radio metrics (RSSI, SNR, airtime utilisation) alongside the most recent received message, sender, and gateway information.
- Provide multiple Home Assistant sensors so dashboards can display firmware, node ID, active channel, signal strength, and the last received text.

## Created entities

| Entity | Description |
| --- | --- |
| `sensor.meshtastic_usb_devices` | Number of detected Meshtastic-capable USB adapters with full device details in the attributes. |
| `sensor.meshtastic_firmware` | Firmware version reported by the connected radio. |
| `sensor.meshtastic_node_id` | Node ID of the locally connected radio. |
| `sensor.meshtastic_channel` | Active primary channel name and a list of all configured channels in the attributes. |
| `sensor.meshtastic_rssi` | Current RSSI reported by the node (signal strength device class). |
| `sensor.meshtastic_snr` | Current SNR value reported by the node. |
| `sensor.meshtastic_last_message` | Payload of the last received text along with sender and gateway attributes. |

Each sensor also publishes extended attributes such as hardware model, region, role, BLE information, airtime utilisation, and mesh route table size.

## Installation (Home Assistant OS via HACS)

1. Install [HACS](https://hacs.xyz/) if it is not already available in your Home Assistant instance.
2. In Home Assistant, open **HACS → Integrations → ⋮ (three dots) → Custom repositories**.
3. Enter `https://github.com/Skrap87/MeshtasticHA` as the repository URL, choose **Integration** as the category, and click **Add**.
4. The repository now appears in HACS. Click **Download** on the Meshtastic USB card and restart Home Assistant when prompted.
5. After Home Assistant restarts, go to **Settings → Devices & Services → + Add Integration**, search for **Meshtastic USB**, and complete the setup wizard.

## Manual installation

1. Copy the `custom_components/meshtastic_usb` folder into the `custom_components` directory of your Home Assistant configuration. If the directory does not exist, create it.
2. Restart Home Assistant.
3. In Home Assistant, navigate to **Settings → Devices & Services → Integrations** and click **Add Integration**.
4. Search for **Meshtastic USB** and complete the setup wizard.

## USB passthrough tips

The integration communicates directly with the USB serial device. When running Home Assistant inside a hypervisor ensure the radio is passed through to the guest operating system.

### VirtualBox (Home Assistant OS)

1. Shut down the Home Assistant OS VM.
2. In VirtualBox Manager open the VM **Settings → Ports → USB** panel.
3. Enable the USB controller that matches your adapter (USB 2.0 for most radios) and add a USB device filter for the adapter. The VID/PID list below can help you identify the correct device.
4. Start the VM, open Home Assistant, and re-run the Meshtastic USB config flow.

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

## Troubleshooting

- VirtualBox host serial ports (`/dev/ttyS*`) are intentionally ignored to avoid false positives. Ensure your adapter is passed through as a USB device, not a legacy serial port.
- If the integration reports an `error` attribute for the detected device, check the Home Assistant logs for the corresponding stack trace. The integration closes and reopens the port on each poll, so the device should recover automatically after transient failures.
