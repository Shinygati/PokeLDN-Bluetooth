<p align="center">
  <img src=".github/assets/banner.png" alt="pokeldn: ESP32-powered local wireless toolkit for Pokémon on Nintendo Switch" width="100%">
</p>

<p align="center">
  <a href="https://pokeldn.app"><img alt="Website" src="https://img.shields.io/badge/website-pokeldn.app-fd474d?style=flat-square"></a>
  <a href="https://discord.gg/PyvaVYnpXC"><img alt="Discord" src="https://img.shields.io/badge/discord-join-5865F2?style=flat-square&logo=discord&logoColor=white"></a>
  <a href="https://decryptu.github.io/pokeldn/"><img alt="Documentation" src="https://img.shields.io/badge/docs-decryptu.github.io%2Fpokeldn-3fa9f5?style=flat-square&logo=readthedocs&logoColor=white"></a>
  <img alt="Python 3.13" src="https://img.shields.io/badge/python-3.13-3fa9f5?style=flat-square&logo=python&logoColor=white">
</p>

# PokeLDN Bluetooth

This fork adds an Android Bluetooth LE connection to the ESP32 radio. The app is named
**PokeLDN Bluetooth** in the launcher, welcome screen, permission prompts and session notifications.
The welcome screen now explains Bluetooth setup and that console keys stay on the phone.

## Bluetooth setup

1. Install `PokeLDN-Bluetooth-arm64.apk` on an ARM64 Android phone (Android 8.0 or later).
2. Flash the **Bluetooth wireless** image matching the ESP32 chip over USB once. The files are
   merged images: with esptool, write the matching file at **offset `0x0`**. Do not flash an S3 image
   onto another chip. A desktop app whose chip list predates this fork may need esptool instead.
3. Power the board near the phone. Disconnect the USB data connection between phone and board
   when using Bluetooth; a USB charger can supply the board's power.
4. Open **Board → Use a Bluetooth board** and grant Nearby devices permission (location permission
   on older Android). Enable Bluetooth when prompted. The app finds `POKELDN-RADIO` automatically;
   no manual pairing in Android Settings is required.
5. When connected, the Board page shows the firmware, address and signal strength. Add your own
   `prod.keys` in Settings, choose a game and tool, and follow the console instructions.

The board connects to one host at a time. Close other apps or computers holding its Bluetooth link.
Firmware is installed over USB, not over Bluetooth.

For PowerShell and Linux terminal commands, chip/port identification, BOOT/RESET recovery and Linux
serial permissions, follow [Flash Bluetooth firmware on Windows or Linux](docs/flashing_bluetooth.md).
Locally compiled deliverables are stored in `dist/bluetooth/` (APK) and `dist/bluetooth/firmware/`
(merged images); these generated build outputs are ignored by Git.

## Bluetooth firmware by chip

Each chip family needs its own image. These builds use a 2 MB flash layout and require at least
2 MB flash; external PSRAM is not required. Hardware must provide **both Bluetooth LE and Wi-Fi**.

| Chip family | Merged Bluetooth image |
|---|---|
| Classic ESP32, including WROOM-32 / WROVER / PICO / SOLO-1 | `pokeldn-radio-ble.bin` |
| ESP32-S3 | `pokeldn-radio-ble-s3.bin` |
| ESP32-C2 / ESP8684 | `pokeldn-radio-ble-c2.bin` |
| ESP32-C3 / ESP8685 | `pokeldn-radio-ble-c3.bin` |
| ESP32-C5 | `pokeldn-radio-ble-c5.bin` |
| ESP32-C6 | `pokeldn-radio-ble-c6.bin` |
| ESP32-C61 | `pokeldn-radio-ble-c61.bin` |
| ESP32-S31 (preview, single core) | `pokeldn-radio-ble-s31.bin` |

ESP32-S2 and P4 have no built-in Bluetooth. Bluetooth-only H-series chips have no Wi-Fi for the
Switch connection, so this application cannot use them as standalone radios. The S31 is an ESP-IDF
preview target; its image compiled, but remains experimental. It and the classic ESP32 image use
one core (classic ESP32 also covers single-core SOLO-1); S3 retains its usual dual-core build.

## Changes in this fork

- Android Bluetooth discovery, permissions, reconnects and the `android://ble` radio port.
- Board-page Bluetooth setup, status, signal strength and disconnect controls.
- Classic ESP32 and newer BLE PHY compatibility: keep 1M available and request 2M only when
  supported, rather than requiring a Bluetooth 5 PHY from every device.
- Firmware target support for the chip families listed above, with matching chip detection and
  firmware selection in the app. The flasher validates the image against the detected chip.
- Capability-based USB serial selection and no assumed LED/button wiring on the new chip targets.
- Explicit 2.4 GHz operation on dual-band Wi-Fi chips for the Switch local-wireless protocol.
- Portable Mystery Gifts kept on the board can start immediately over Bluetooth and continue
  after the phone disconnects, as described in `CHANGES-bluetooth-android.md`.
- Corrected Android welcome text and renamed the app to make Bluetooth support visible.

## Build status and rebuilding

The Android APK, PKHeX helper, Unicorn library and the seven standard Bluetooth firmware targets
and the S31 preview firmware were compiled locally. **No app launch, installation, unit tests, emulator tests or hardware tests
were run for these deliverables.** A successful compile does not verify radio timing, available
runtime heap, board-specific wiring, or trades on each chip. New target support needs device testing.

Firmware was built with ESP-IDF 6.1 and Espressif Clang because the installed Windows GCC executables
could not start. ESP-IDF labels Clang support experimental. Compiler warnings are retained in the
build logs; PKHeX also reports NativeAOT warnings around JSON handling and some upstream methods.
The APK uses a local development signing key, so it updates only installations signed with that key.

With ESP-IDF 6.1 activated, build the standard Bluetooth firmware set using:

```sh
python scripts/build_bluetooth_firmware.py
# Or build just the chips you own:
python scripts/build_bluetooth_firmware.py --targets esp32 esp32s3 esp32c3
# Preview S31 (single-core configuration avoids an SDK 6.1 Clang SMP-retention issue):
python scripts/build_bluetooth_firmware.py --targets esp32s31
```

Images are written to `gui/firmware/`. Then build the Android APK with the repository's Python 3.13
environment and the Android prerequisites in [the Android build guide](examples/android/README.md):

```sh
python examples/android/build.py --release
```

The Android build script normalizes duplicate console aliases in its local wheels so Windows does
not generate conflicting `.exe` files during Chaquopy packaging. The Android protocol is unchanged; the application
ID stays `org.pokeldn.usbprobe` so changing the display name does not create a separate app.

## Upstream pokeldn

pokeldn trades with retail Pokémon games on Switch and Switch 2 through an ESP32 board connected to a
computer by USB. Nothing is installed on the console.

The desktop app runs on macOS (Apple silicon), Windows and Linux. The same app runs on Android, with
the board on the phone's USB port, and on iPhone and iPad, with the board reached over Bluetooth.
Command-line tools run from source, and the docs describe the games' local wireless protocols. AI tools helped reverse engineer
those protocols and write parts of the code.

## Supported games

| | [FRLG](docs/frlg.md) | [LGPE](docs/lgpe.md) | [SwSh](docs/swsh.md) | [BDSP](docs/bdsp.md) | [PLA](docs/pla.md) | [SV](docs/sv.md) | [PLZA](docs/za.md) |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| Trade | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Online trade | ✓ | ○ | ○ | ○ | ○ | ✓ | ○ |
| Mystery Gift | ✓ | ∅ | ✓ | ∅ | ∅ | ∅ | ∅ |
| Event Pokemon | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Link battle | ✓ | ✗ | ✗ | ✗ | ∅ | ✗ | ✗ |
| Console code and save read/write | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |

✓ verified on retail hardware · ○ tested offline only · ✗ not implemented · ∅ unavailable over local wireless

FRLG: FireRed/LeafGreen · LGPE: Let's Go Pikachu/Eevee · SwSh: Sword/Shield ·
BDSP: Brilliant Diamond/Shining Pearl · PLA: Legends Arceus · SV: Scarlet/Violet · PLZA: Legends Z-A

Scarlet/Violet also supports [local Tera Raids](docs/sv_raid.md) and the
[Union Circle](docs/sv_union_circle.md) as a guest, and Sword/Shield
[Max Raid Battles and Dynamax Adventures](docs/swsh_raid.md), hosted with a chosen boss or legendary
or joined as the console's partner. Sword/Shield also trades, raids and runs Dynamax Adventures in
its hidden LAN mode over the computer's own network, joining or hosting, with no board
([LAN mode](docs/swsh_session.md#lan-mode)). Event Pokemon arrive through Mystery
Gift on FRLG and SwSh, and elsewhere as an official gift traded by the host
([Simulated Mystery Gifts](docs/gift_simulated.md)).

## Get started

<img src=".github/assets/desktop-app.webp" alt="The pokeldn desktop app offering a shiny Chansey for a FireRed trade" width="100%">

You need a [supported ESP32 board](docs/hardware_esp32.md#supported-boards), a USB data cable,
Switch `prod.keys`, and a Switch or Switch 2 with a supported game.

1. Download the app from [Releases](https://github.com/Decryptu/pokeldn/releases) or [pokeldn.app](https://pokeldn.app).
2. Choose `prod.keys` in Settings.
3. Connect the board and install the Wireless firmware from the Board page.
4. Choose a game and tool, then follow the console instructions in the app.

On a phone:

- **Android**: install `pokeldn-android-arm64.apk` from Releases and plug an ESP32-S3, C3 or C6, or a
  classic ESP32 with a CP210x USB chip, into the phone with a USB data cable
  ([Android setup](docs/gui.md#android-setup-requirements)).
- **iPhone and iPad**: install `pokeldn-ios.ipa` with AltStore or SideStore (the app's
  [AltStore source](https://raw.githubusercontent.com/Decryptu/pokeldn/main/.github/altstore/source.json)).
  Flash the board once with the **Bluetooth wireless** firmware from the desktop app's Board page; it
  then needs USB only for power ([iOS setup](docs/gui.md#ios-setup)).

Platform notes: [first launch](docs/gui.md#first-launch), [Windows USB drivers](docs/gui.md#windows-usb-drivers),
[Linux serial ports](docs/gui.md#linux-serial-ports).

## Documentation

| Topic | Guide |
|---|---|
| Command-line setup and game commands | [Usage](docs/usage.md) |
| Bank, Pokémon imports and conversion | [Bank](docs/gui.md#the-bank) |
| Online trades and GTS | [Online trade](docs/online.md), [GTS](docs/online.md#the-gts) |
| Building and sharing Mystery Gifts | [Gift files](docs/gifts.md) |
| FireRed/LeafGreen save backups and restores | [Save backup and restore](docs/frlg_gift.md#save-backup-and-restore) |
| Controller and macros | [Controller](docs/gui.md#the-controller) |
| Installing or writing plugins | [Plugins](docs/plugins.md) |
| Windows USB Wi-Fi adapters | [ldnrs setup](docs/hardware_adapters.md#windows-usb-wi-fi-through-ldnrs) |
| Boards, firmware and optional screens | [ESP32 radio](docs/hardware_esp32.md) |
| Running and building the desktop app from source | [Desktop builds](docs/gui.md#run-from-source) |
| Building the Android app | [Android app](examples/android/README.md) |
| Building the iOS app (Bluetooth radio, AltStore) | [iOS app](examples/ios/README.md) |
| Code layout, Pokémon legality and tests | [Code organization](docs/architecture.md) |
| Wireless protocols and reverse engineering | [Documentation index](docs/index.md) |

The docs are also published at [decryptu.github.io/pokeldn](https://decryptu.github.io/pokeldn/).

## Credits

pokeldn is a fork of [MercuryEnigma/frlg-ldn-trade](https://github.com/MercuryEnigma/frlg-ldn-trade)
by [MercuryEnigma](https://github.com/MercuryEnigma), itself a fork of
[tornadus/frlg-ldn-trade](https://github.com/tornadus/frlg-ldn-trade) by
[tornadus](https://github.com/tornadus), with contributions from
[trowgundam](https://github.com/trowgundam).

Contributors to this repository (GitHub does not list contributors on a fork):

- [Gr3nSkyDragon](https://github.com/Gr3nSkyDragon): ESP32-S3 firmware
- [ismailhasannnnnn](https://github.com/ismailhasannnnnn): Scarlet/Violet Tera Raid hosting and joining,
  reverse engineering and reconstruction of the RaidPoint structure, including reward encoding and
  raid bootstrap compression, and hosted raid reward templates, with mint, battle item, berry and
  evolution item bundles
- [easyworld](https://github.com/easyworld): ESP32 serial reconnects after a high-baud session,
  language packs that translate game names, module messages, tool help, the documentation and its
  page titles, game choices and raid partners' names, the language pack checker, CJK tooltips, and
  game names, gift summaries, encounter places and original-trainer notes in the display language
- [capito27](https://github.com/capito27): Scarlet/Violet event Tera Raids, the raid finder's reward
  filter, its full seed search, its ranking by rewards and its size mark filter, and the Tera Raid
  NPC partners: their draw from the RaidPoint and the host's choice of them; Simulated Mystery Gifts
  made for the receiving save, pop-ups for programs, Pokemon HOME's gifts among Sword/Shield's
  official events, a Tera Raid boss's scripted actions, Legends Arceus's trainer gender, the
  ESP32 credit for a frame still being written, near doubling USB upload speed, and the
  Scarlet/Violet Union Circle guest: Blueberry Quest clears, Snacksworth's legendaries and
  crafted wild encounters
- [DedHapp3n](https://github.com/DedHapp3n): classic ESP32 boards with a CP210x USB chip in the Android
  app
- [elsardine6k7](https://github.com/elsardine6k7): friendship in the Pokemon builder, Showdown sets and
  the Simulated Mystery Gift queue
- [junkmailkeep](https://github.com/junkmailkeep): Mystery Gift sprites and form previews in the gift
  and trade editors
- [MarcJa420](https://github.com/MarcJa420): the E32R40T 4-inch screen build, the firmware version on
  the idle screen, hosted raid and Dynamax Adventure lobbies on the board's screen, and Gigantamax
  sprites
- [axechaso](https://github.com/axechaso): the one-shot A press at an exact RNG frame behind the
  FireRed/LeafGreen Shiny Mewtwo boost, and the FireRed/LeafGreen RNG in the plugin API

- [unlimitedcoder2](https://github.com/unlimitedcoder2): [ldnrs](https://github.com/unlimitedcoder2/ldnrs),
  the external Windows USB Wi-Fi daemon supported by the optional radio backend
- [kinnay](https://github.com/kinnay): the [LDN library](https://github.com/kinnay/LDN) this builds on,
  and the [NintendoClients wiki](https://github.com/kinnay/NintendoClients/wiki)
- [pokefirered](https://github.com/pret/pokefirered): decompilation of FireRed/LeafGreen, including
  the Switch port
- [GB-Link Team](https://github.com/GB-Link/GB-Link-Switch-LDN): the custom FireRed/LeafGreen Wonder
  Cards in `vendor/gblink-cards/` (GPL-3.0)
- [xCyrusBR](https://github.com/xCyrusBR): [TeraLoop-Bridge](https://github.com/xCyrusBR/TeraLoop-Bridge),
  [SV-Past-Tera-Raid](https://github.com/xCyrusBR/SV-Past-Tera-Raid) and
  [pokeldn-TeraLoop-](https://github.com/xCyrusBR/pokeldn-TeraLoop-), Scarlet/Violet Tera Raid
  work, including the raid host waiting for the console's Ready
- [Project Pokemon](https://github.com/projectpokemon): the [EventsGallery](https://github.com/projectpokemon/EventsGallery)
  of Scarlet/Violet raid event deliveries the app downloads, with pkNX's text of each
- [Matcore962](https://github.com/Matcore962): importing Pokemon files and game saves into the Bank

## Code signing policy

Free code signing provided by [SignPath.io](https://about.signpath.io), certificate by [SignPath Foundation](https://signpath.org).
What is signed, the team roles and the privacy policy are on the
[Code signing policy](https://decryptu.github.io/pokeldn/code_signing.html) page.

## License

The code is licensed under AGPLv3. The license covers this repository's code and nothing else.

pokeldn is an unofficial fan project. It is not affiliated with, endorsed by or sponsored by
Nintendo, The Pokemon Company, Game Freak or Creatures. Pokemon, Nintendo Switch and the related
names and characters are trademarks of their owners. Under section 7(e) of the AGPL, no right to
use those trademarks or any other Pokemon intellectual property is granted.

The authors do not endorse using pokeldn for commercial, promotional or branded events, including
Mystery Gift distributions. Anyone who does so is responsible for obtaining the rights it requires.
