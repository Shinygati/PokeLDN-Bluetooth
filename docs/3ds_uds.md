# Gen 6 and Gen 7 Mystery Gift over 3DS local wireless (work in progress)

X/Y, Omega Ruby/Alpha Sapphire, Sun/Moon and Ultra Sun/Ultra Moon receive local Wonder Cards through
**Mystery Gift → Get via Local Wireless**, from a 3DS running Nintendo's Local Distributor. The goal is
for the ESP32 to be that distributor, with the phone app choosing the card, as it already does for
Gen 4 and Gen 5.

This is not the Switch's LDN protocol, and not the plain DS beacons the Gen 4/5 sender uses. 3DS local
wireless is **UDS**: an encrypted Nintendo beacon, open-system association, Nintendo's own
EAPoL-Start/Logoff node handshake, and CCMP-protected data frames carrying SecureData packets.

## What is already known

Gr3nSkyDragon's [azahar_uds](https://github.com/Gr3nSkyDragon/azahar_uds) fork of Azahar trades Gen 6
and Gen 7 Pokemon between the emulator and a retail 3DS, through a USB Wi-Fi adapter (`ldnd.exe`) or
an ESP32-S3 ([VC-Adapter `esp32-uds-bridge`](https://github.com/Gr3nSkyDragon/VC-Adapter/tree/main/firmware/esp32-uds-bridge)).
It has worked out, against real hardware:

| piece | where in azahar_uds | pokeldn |
|---|---|---|
| retail beacon: tag order, rates, TIM, country, ERP; NWM beacon key | `nwm/uds_beacon.cpp` | `pokeldn.uds.frames.Beacon`, `crypto.crypt_beacon_data` |
| CCMP key: AES-CTR with keyslot 0x2D over MD5(passphrase) | `nwm/uds_data.cpp` `GenerateDataCCMPKey` | `crypto.ccmp_key` |
| SecureData container: u16 size, **u16 packet count (1; 0 is ignored)**, aggregated sub-packets | `nwm/uds_data.h` | `frames.pack_secure_data` / `unpack_secure_data` |
| EAPoL-Start connection type is a big-endian **u16** | `nwm/uds_data.h` | `frames.EapolStart` |
| EAPoL-Logoff host status **6** (Sun/Moon leave on 0) | `nwm/uds_data.h` | `frames.EapolLogoff.host_status` |
| association response, `0xC000` AID bits, SSID = network id in hex | `nwm/uds_connection.cpp` | `frames.association_response_body` |
| a dumb ESP32 radio: raw TX, beacon template every 102.4 ms, twin-MAC capture | VC-Adapter `esp32-uds-bridge` | not yet |
| a standalone UDS client running on the ESP32 itself (Game Boy VC wrapper) | VC-Adapter `main/gbwrap/` | not yet |

`pokeldn.uds.crypto.ccmp_encrypt` reproduces the IEEE 802.11 CCMP test vector (`tests/test_uds.py`).
Neither console key is in this repository: `crypto.load_keys` reads `nwm_beacon_key=` and
`slot0x2DKeyN=` lines from a file you provide (Azahar's `aes_keys.txt` has the slot key).

## What is not known yet: the gift exchange

Trading is solved, but **Get via Local Wireless** is a different session. It has its own wlan comm id
and passphrase, its own beacon application data, and its own SecureData conversation that delivers
the `.wc6`/`.wc7` card. Nothing public describes it. The quickest way to learn it is to record it
from the official software in an emulator, where every packet is plaintext.

## Phase 1: record a Local Distributor session (now)

azahar_uds sends every UDS packet unencrypted over UDP when `AZAHAR_UDS_BRIDGE` is set: port N
listens on N and sends to N + 1 (`nwm/uds_bridge.h`). Run two instances and put
`tools/uds/bridge_relay.py` between them:

1. Make two portable copies of azahar_uds (each with its own `user` folder), and give them
   **different console MACs** (System settings: regenerate the console ID / MAC in one copy). Leave
   the ESP32 and ldnd backends off in both.
2. Copy A: install your Gen 6 (or Gen 7) Local Distributor and its save, with the card you want in it.
   Copy B: the matching game, with Mystery Gift unlocked.
3. Start the relay:
   `python tools/uds/bridge_relay.py --a 45710 --b 45720 --out captures/xy-gift.jsonl --quiet-beacons`
4. Start copy A with `AZAHAR_UDS_BRIDGE=45710` and the distributor running. Then start copy B with
   `AZAHAR_UDS_BRIDGE=45720`, and choose Mystery Gift → Get via Local Wireless → receive the card.
   (PowerShell: `$env:AZAHAR_UDS_BRIDGE = "45710"; .\azahar.exe`; the variable is read when a game starts.)
5. In copy B's log, save the line `UDS Real: ConnectToNetwork key-derivation input ...`. It holds the
   passphrase, wlan comm id and network id the real-air phase needs.
6. `python tools/uds/capture_dump.py captures/xy-gift.jsonl --payloads captures/xy-gift-payloads`

Record **two different cards** for each of Gen 6 and Gen 7, so the card bytes can be told apart from
the session's framing. If the relay shows A's beacons but B never joins, check that the two copies
have different MACs.

## Phase 2: a pokeldn distributor against the emulator (no radio, no keys)

`pokeldn.uds` plays the distributor's side of the recorded session over the same UDP bridge:
beacons with the recorded application data, the authentication/association replies, EAPoL-Logoff,
then the SecureData exchange with any `.wc6`/`.wc6full`/`.wc7`/`.wc7full` card substituted in. Copy B
(the game) is the test bench. Done when copy B receives a card that copy A never had.

## Phase 3: real air

The same host runs over the ESP32, adding the beacon key, 802.11 headers and CCMP:

- **Board firmware.** Either extend pokeldn's radio firmware (its AP mode already installs a host
  CCMP key in hardware without a 4-way handshake, as UDS needs, but its beacon cannot yet carry the
  four Nintendo vendor elements), or follow VC-Adapter's approach (raw beacon template and frames,
  CCMP in software). For the phone, the session should run on the board itself, like the FireRed
  host image (`docs/hardware_esp32.md`, "A host image"), so Bluetooth only uploads the card.
- **Keys.** The board needs the beacon key and the derived CCMP key (never the slot key itself: the
  host derives it once from the passphrase, as the LDN images hold derived keys and not `prod.keys`).

## Phase 4: the app

A "Nintendo 3DS" entry beside the Nintendo DS sender, with X/Y, OR/AS, S/M and US/UM, languages, and
the bundled card library.
