# Upstream sync — 11 November 2026

Merged Decryptu/pokeldn through `055152c8f145a46650dab8e98da19451e6ca11ea` (58 upstream commits since the shared base) into the DS/3DS fork at `2ddfcd8b41f99e22814fb4c96f4597dbfd7a7709`.

The merge retains both Bluetooth services, DS connection handoff, direct WC6/WC7 handling, one-time user-supplied Gen 7 distributor setup, all bundled cards, paired-game filtering, the 3DS icon and DS/3DS ordering. The protocol modules, Android sender classes and card library are unchanged from the working fork.

Shared-file resolutions keep the GPIO48 SPI status LED and DS raw-beacon transmitter alongside upstream's screen/speaker support and standby behavior. Release packaging includes both the fork's BLE targets and upstream's screen targets. CI's S3 BLE build explicitly sets GPIO48, matching the user's Lonely Binary board.

Firmware source version is 1.11.1 to distinguish this combined build from upstream 1.11.0 and the previously tested custom 1.10.7. This sync does not replace the user's existing working v0.8 APK or 1.10.7 firmware files.

Local validation: 38 core app/DS/3DS tests and 45 board tests passed. The ESP32-S3 BLE/GPIO48 firmware compiled with ESP-IDF 6.1. Broader local tests using Windows asyncio could not complete because this restricted execution environment stalls while creating its socket pair; the full CI suite remains a separate check. No claim is made that the newly combined build has been tested on hardware.

No signing keystore, distributor executable or private signing key was added by the merge. Existing private one-time setup remains outside the APK.
