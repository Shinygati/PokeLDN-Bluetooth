# PokeLDN Gen 6/7 source update — verification status

This is a **source overlay**, not a complete, validated 3DS wireless distributor.
It does not modify your GitHub repository and does not include a compiled APK/ESP32 binary.

## Implemented in this archive
- 1,773 original EventsGallery Wonder Cards in `pokeldn/data/gift3ds/wondercards/`.
- Gen 6 and Gen 7 card scanning, title and game filtering, and an **Add Wonder Card** file-picker.
- Source-level card format validation and tests.
- A reproduction fixture and structural notes for the real Krookodile #665 UDS log.
- Removal of the record/import-gift-pack flow from the replacement desktop 3DS view.

## Not yet implemented (do not misrepresent)
- General `.wc6`/`.wc7` to UDS fragment encoder and full checksum/session derivation.
- Distribution of arbitrary WC6/WC7 through ESP32; **no new send operation is enabled**.
- Gen IV/V Android sender compatibility with the new `POKELDN-RADIO` BLE protocol.
- Firmware GPIO driver for red/green RGB LEDs (the actual board's LED pinout is unknown).
- Verified hardware tests or an Android APK build.

## How the overlay is laid out
Paths under this ZIP are relative to the root of `Shinygati/PokeLDN-Bluetooth`.
The main new UI code replaces `gui/views/gift3ds.py`; old recorded gift packs are not deleted.
This overlay was built against the repository version reviewed on 2026-11-10.

## Technical note
The uploaded real-hardware log contained 493 `SetApplicationData` events and exactly three unique
200-byte payloads with fragment IDs 0, 1 and 2. Their 24-byte headers include the card ID `0x0299`.
The first fragment has what appears to be an LZ10 stream for a 0x310-byte WC7Full, but its
reconstruction is not complete. A transmitter must not simply replay Krookodile fragments with
another card name or card ID.

## Continued protocol investigation (2026-11-10)
- Added `pokeldn/uds/uds_gift_analysis.py` fragment validation and compressed-stream extraction.
- The three Krookodile application-data payloads contain a recognizable LZ10 header (`10 10 03 00`) and a packed-size field of 346 bytes. A 24-byte common fragment header, 8-byte first-fragment size block, and 16-byte trailing alignment/padding on full fragments are observed.
- The partially decoded stream agrees with the provided 784-byte `.wc7full` through its first 0x202 bytes. Offsets 0x202 and 0x203 differ (full-card CRC). Remaining decoded bytes agree until the LZ10 decoder encounters a back-reference that is invalid if treated as one contiguous standard stream. This indicates that more format research is needed; *not* that arbitrary-card encoding is finished.
- Added `tools/uds/analyze_card_wire.py` for comparing fixture against original card.
- Eight offline pytest tests pass. No ESP32 or retail 3DS hardware test has been performed.

### Existing unimplemented items remain
Direct `.wc6`/`.wc7` broadcasting, native Gen 6/7 board firmware, the Android DS BLE protocol migration, and RGB LED GPIO mapping are **not** complete. This source update does not present a false 'send successfully' operation.
