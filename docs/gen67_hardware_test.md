# Nintendo DS and 3DS Android sender

Current working pair: Android app **0.8-ds-bluetooth-unified** (version code 8) and ESP32-S3 firmware **1.10.7**. The user confirmed this pair works on 11 November 2026. No per-card or per-game receipt matrix has been recorded.

Nintendo DS and Nintendo 3DS appear at the bottom of Games, in that order. The DS sender recognises POKELDN-RADIO and the older DS sender name. While the DS screen is open, the main app releases its Bluetooth connection. Firmware provides both the original radio service and the FFF0 DS service; DS uploads stay in RAM and stop when disconnected.

For 3DS, choose X/Y, Omega Ruby/Alpha Sapphire, Sun/Moon or Ultra Sun/Ultra Moon, then a language and bundled Wonder Card. Each pair lists the union of its two games' compatible cards. Game-exclusive cards retain their restriction. Alternatively import WC6/WC6Full or WC7/WC7Full. The library includes 1,773 cards from the supplied EventsGallery archive.

Gen 7 requires the user's own verified decrypted distributor `.code` once in Options. It is saved in app-private storage. Distributor executables and private signing material must never be bundled in the APK or committed. Gen 6 does not require that setup. Android APK signing keys are separate from distributor signing material.

The paired list uses platform-independent bundled-card identifiers and accepts paths saved by the preceding APK containing Windows backslashes.

Firmware uses the dim GPIO48 GRB SPI LED driver for the Lonely Binary ESP32-S3 Gold board: disconnected red, phone connected solid green and distributing slow blinking green. Flash the merged S3 image at address 0x0. Keep firmware 1.10.7 for the unified DS/3DS APK.

Validation: 29 targeted tests passed. Actual Java Gen IV/V encoder output was passed through the compiled C firmware parser and beacon builder. All 836 Gen 6 cards passed offline generation/decoding and image-size checks. The packaged APK, DEX changes, firmware and signatures were verified. European Gen IV GGID mappings remain provisional, inherited from the DS sender source.

Build Android with `python examples/android/build.py --release`; configure Android signing using the existing POKELDN_ANDROID_RELEASE_* environment variables. Build BLE firmware with POKELDN_BLE=1 and POKELDN_RGB_GPIO=48 on ESP32-S3. Do not commit local signing credentials. No external plugin package, firmware backup UI or firmware restore UI is part of this release.
