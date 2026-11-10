# Current implementation status

The current Android app is version **0.8-ds-bluetooth-unified** (version code 8), paired with ESP32-S3 firmware **1.10.7**. The user confirmed that pair works on 11 November 2026.

Implemented: Gen 6 WC6 and Gen 7 WC7 encoding, one-time private Gen 7 distributor setup, 1,773 bundled cards filtered by four game pairs and language, Android bundled-path repair, a recognisable 3DS icon, DS/3DS list ordering, unified DS FFF0 and POKELDN-RADIO Bluetooth services, Bluetooth ownership handoff and the dim GPIO48 SPI LED driver.

29 targeted tests passed, including real Java DS encoders against the compiled C firmware parser. All 836 Gen 6 cards passed offline round trips. Complete per-game, language and card hardware receipt testing remains outstanding. European Gen IV GGID mappings remain provisional.

See [setup and limitations](docs/gen67_hardware_test.md). No distributor executable, private distributor key, Android keystore or password is included in the source update.
