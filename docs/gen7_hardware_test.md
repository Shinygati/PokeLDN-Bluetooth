# Gen 7 experimental hardware test

This build generates new signed Wonder Card payloads on the PC, preserving a captured distributor network envelope. The phone carries generated broadcast data, not the distributor private key. All 937 bundled Gen 7 entries (922 distinct file hashes) were generated and independently recovered and compared offline. Real-console reception has not been tested.

## Install and test

1. Flash the merged `pokeldn-radio-ble-s3-gpio48-test.bin` to an ESP32-S3 at offset `0x0`, using esptool or the PokeLDN firmware installer. This image uses a 2 MB partition layout. GPIO48 must connect to a WS2812B for RGB status; other board wiring needs a separate build.
2. Install `PokeLDN-Gen7-hardware-test.apk`. It is version code 5, version name `0.5-3ds-hardware-test`, signed with the user's `pokeldn` Android release alias. A matching signing certificate is required to update an installed app.
3. In Board, select **Use a Bluetooth board** and connect to `POKELDN-RADIO`. The board should report firmware 1.10.1. GPIO48 shows red while disconnected, green while connected, and blinking green during 3DS broadcasting.
4. In Games, choose **Nintendo 3DS → Mystery Gift**. Choose a Gen 7 Wonder Card matching your game's version and language. The list includes both full cards and bare cards; bare cards use the verified capture's distribution header during PC preparation.
5. Open Session and select **Start**. The app uploads a portable beacon image. On Sun/Moon, open **Mystery Gift → Receive Gift → Get via Local Wireless**. Keep the console close to the board for the first test. Ultra Sun/Ultra Moon compatibility remains a hardware test too.
6. Record whether the console discovers the card, its displayed title, and whether receiving and collecting it succeeds. Save the app Session log if it fails. Test a card different from the captured Krookodile to validate new payload generation.

The board can keep a stored gift broadcasting after the app session ends. To stop it, reconnect and remove the kept gift in Board, or disconnect power. LED activity and a successful upload do not prove that the console received the card.

## Custom cards

From the repository root, using its Python environment:

```powershell
.venv\Scripts\python.exe -m tools.uds.prepare_direct_cards --code "path\to\00040000001A8900.code" --template "gifts\krookodile-665.gift.json" --cards "path\to\card.wc7full" --out "prepared-custom"
```

This extractor accepts the exact Gen 7 executable verified in the investigation. Copy the resulting `.gift.json` to the phone, leave the card selector on **Use a gift pack file**, choose that file, then Start. No signing key is exported. New cards added only through a WC file picker are not automatically prepared.

## Rebuild details

Set `POKELDN_3DS_PREPARED` to the generated pack folder before running the Android builder. It validates and stages only `.gift.json` files. Firmware was built with ESP-IDF 6.1, its Clang toolchain, `POKELDN_BLE=1`, and `POKELDN_RGB_GPIO=48`. Android was built with the user's existing release keystore via environment variables; no password or keystore is stored in source.

Gen 6, DS Gen IV/V BLE protocol migration, and a unified DS/3DS radio are outside this Gen 7 test build. The outer distributor session header and encrypted node data are preserved from the provided envelope; independent session synthesis is not implemented.
