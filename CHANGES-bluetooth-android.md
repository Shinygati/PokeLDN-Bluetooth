# Bluetooth ESP32 support for the Android app ("PokeLDN BT Companion")

Based on upstream Decryptu/pokeldn at 3707414 (Release 0.56.0).

## What changed

- **Android Bluetooth link.** `BleStream.java` connects to a board running the Bluetooth wireless
  firmware (`POKELDN-RADIO`), with the 2M PHY, high connection priority and a 247-byte MTU. `Bridge.java`
  scans while the app is open, keeps one connection, and lists the board as the port `android://ble`,
  so every page and launcher uses it unchanged. A session closing leaves the connection up.
- **Board page.** With no USB board plugged in: Use a Bluetooth board, Allow Bluetooth, Turn on
  Bluetooth, or Looking for the Bluetooth radio. A connected board shows its address, signal strength
  and a Disconnect button. Firmware installs are disabled over Bluetooth (a board cannot be reset into
  its loader that way); install over USB.
- **ESP32-S3 Bluetooth firmware** (`pokeldn-radio-ble-s3.bin`): added to the release build, the
  desktop and Android Board pages, the packer and its checks. Built and checked with ESP-IDF v6.1:
  867 KB in the 1.5 MB app partition.
- **Kept Mystery Gifts over Bluetooth** (FireRed/LeafGreen and Sword/Shield): "Keep it on the board"
  starts the gift at once instead of waiting for the next power-up, and it keeps going after the app
  disconnects. Over USB nothing changes.
- **App name** on Android: PokeLDN BT Companion in Settings, the notification, the setup screens and
  the permission help; the home-screen icon says PokeLDN BT, since launchers cut longer labels. The package id stays `org.pokeldn.usbprobe` so it installs over pokeldn's
  Android app and keeps its files.
- Manifest: Bluetooth scan/connect permissions (location on Android 11 and earlier); USB host and
  Bluetooth LE are both optional features.
- Docs: `docs/gui.md` (Bluetooth on Android), `docs/hardware_esp32.md`, `examples/android/README.md`.

## Already supported, unchanged

Uploading `.wc3` (FireRed/LeafGreen) and `.wc8` (Sword/Shield) Wonder Cards and `.pk3`/`.pk8`
Pokemon for trades, and storing a gift on the board with "Keep it on the board".

## Checked

- `tests/test_android_ble.py`: the Bluetooth port, through `Radio.open_serial`, against the simulated
  board; no line rate or BAUD over Bluetooth; the connection survives a closed session.
- `tests/test_kept_gift_bluetooth.py`: which radio specs count as Bluetooth, and the immediate start.
- Full test suite: the same 79 failures as untouched upstream in this environment (they need the
  PKHeX service built with .NET), no new ones.
- All Android Java compiles against the Android 36 SDK.
- Not tested on hardware: a phone, a board or a console. The S3's Bluetooth link loop has no upstream
  measurement yet; the C6 is the proven Bluetooth board.

## Build

APK: `python examples/android/build.py --install DEVICE` (JDK 21, Android SDK 36, NDK, .NET 10,
Gradle 8.13 to 9.5). Flash `pokeldn-radio-ble-s3.bin` once over USB (Board page, Install from a file,
or esptool at offset 0x0).
