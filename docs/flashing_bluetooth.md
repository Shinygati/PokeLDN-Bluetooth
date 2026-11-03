---
title: Flash Bluetooth firmware
parent: Hardware and setup
nav_order: 2
---

# Flash Bluetooth firmware on Windows or Linux

Flash the board once over a **USB data cable**. Afterward it needs power and connects to the phone
over Bluetooth LE. Flashing replaces its current firmware and can clear stored board settings/gifts.
These are merged images: write the whole matching `.bin` at **`0x0`**, including on classic ESP32,
C5 and S31. Their internal bootloader offsets are already included in the file's padding.

## Choose the matching image

| Board chip | esptool `--chip` | File |
|---|---|---|
| Classic ESP32 (WROOM/WROVER/PICO/SOLO-1) | `esp32` | `pokeldn-radio-ble.bin` |
| ESP32-S3 | `esp32s3` | `pokeldn-radio-ble-s3.bin` |
| ESP32-C2 / ESP8684 | `esp32c2` | `pokeldn-radio-ble-c2.bin` |
| ESP32-C3 / ESP8685 | `esp32c3` | `pokeldn-radio-ble-c3.bin` |
| ESP32-C5 | `esp32c5` | `pokeldn-radio-ble-c5.bin` |
| ESP32-C6 | `esp32c6` | `pokeldn-radio-ble-c6.bin` |
| ESP32-C61 | `esp32c61` | `pokeldn-radio-ble-c61.bin` |
| ESP32-S31 (preview) | `esp32s31` | `pokeldn-radio-ble-s31.bin` |

Use a board with at least 2 MB flash. No PSRAM is required. S2/P4 lack built-in Bluetooth;
Bluetooth-only H-series chips lack the Wi-Fi required for the Switch link. S31 support and the
Espressif Clang builds are experimental. These files were compiled, not hardware-tested.

## Windows PowerShell

Install Python 3.10 or newer with its Python launcher. Open PowerShell in the directory containing
the firmware files (the local repository build puts them in `dist/bluetooth/firmware/`). Close any
serial monitor or desktop app holding the board's COM port.

```powershell
py -3 -m venv .flash-venv
.\.flash-venv\Scripts\python.exe -m pip install esptool==5.6.0
.\.flash-venv\Scripts\python.exe -m serial.tools.list_ports
```

Identify the new COM port in that list or Device Manager → Ports (COM & LPT). Connect the board and
replace `COM5` below with its actual port. This read-only command identifies the chip:

```powershell
.\.flash-venv\Scripts\python.exe -m esptool --port COM5 chip-id
```

Example for an **ESP32-S3**:

```powershell
.\.flash-venv\Scripts\python.exe -m esptool --chip esp32s3 --port COM5 --baud 460800 write-flash 0x0 .\pokeldn-radio-ble-s3.bin
```

For another chip, replace **both** `esp32s3` and the filename using the table. For S31, also place
`--no-stub` before `write-flash`. If no port appears, try a data cable and the appropriate CP210x/CH34x
driver from the manufacturer's site; see [Windows USB drivers](gui.md#windows-usb-drivers).

## Linux terminal

Install your distribution's Python 3 and venv package (for example `python3-venv` on Debian/Ubuntu).
Open a terminal in the firmware directory and close programs holding the serial port.

```sh
python3 -m venv .flash-venv
.flash-venv/bin/python -m pip install esptool==5.6.0
.flash-venv/bin/python -m serial.tools.list_ports
```

Native USB usually appears as `/dev/ttyACM0`; USB-to-UART adapters often appear as `/dev/ttyUSB0`.
Use the actual port from the list. Identify the chip first:

```sh
.flash-venv/bin/python -m esptool --port /dev/ttyACM0 chip-id
```

Example for an **ESP32-S3**:

```sh
.flash-venv/bin/python -m esptool --chip esp32s3 --port /dev/ttyACM0 --baud 460800 write-flash 0x0 ./pokeldn-radio-ble-s3.bin
```

Replace the chip and filename together using the table; S31 also needs `--no-stub` before
`write-flash`. If Linux reports permission denied, inspect the port's owning group:

```sh
ls -l /dev/ttyACM0
# Only if that port belongs to dialout:
sudo usermod -a -G dialout "$USER"
```

Log out and back in after adding the group. Some distributions use `uucp` instead; use the group
shown for your port. Do not run the whole app as root to work around serial permissions.

## If connection fails

Most development boards enter the ROM bootloader automatically. If yours does not, hold **BOOT**,
press and release **RESET/EN**, then release BOOT and retry. A native USB board can appear on a new
port in bootloader mode, so list the ports again. If it has separate UART and native USB sockets,
use its native USB socket for S3/C3/C5/C6/C61/S31; classic ESP32 and C2 use their USB-UART bridge.

For interrupted or unreliable writes, retry at `--baud 115200`, use a short data cable, and close
serial monitors. Wait for esptool's successful verification before disconnecting. Release BOOT and
press RESET, or unplug and reconnect power, to leave the bootloader.

## Connect from Android

Power the flashed board near the phone. Disconnect the USB data connection to the phone when using
Bluetooth. In **PokeLDN Bluetooth**, open **Board → Use a Bluetooth board**, grant Nearby devices
permission (location on older Android) and enable Bluetooth. The app discovers `POKELDN-RADIO` on
its own; no manual Android pairing is needed. Only one host can hold the board at a time.

Reference: Espressif's [flashing guide](https://docs.espressif.com/projects/esptool/en/latest/esp32/esptool/flashing-firmware.html),
[boot-mode guide](https://docs.espressif.com/projects/esptool/en/latest/esp32/advanced-topics/boot-mode-selection.html),
and [troubleshooting guide](https://docs.espressif.com/projects/esptool/en/latest/esp32/troubleshooting.html).
