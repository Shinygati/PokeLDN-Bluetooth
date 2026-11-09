# Gen 6/7 Mystery Gift today: the Local Distributor in azahar_uds, through an ESP32

Until pokeldn's own 3DS distributor exists ([3ds_uds.md](3ds_uds.md)), a PC can stand in for the
distribution 3DS: Gr3nSkyDragon's [azahar_uds](https://github.com/Gr3nSkyDragon/azahar_uds) runs
Nintendo's Local Distributor, and its ESP32 radio puts the session on the air for a real X/Y/OR/AS
or S/M/US/UM to receive with **Mystery Gift → Get via Local Wireless**.

azahar_uds has been verified hosting **trades** to retail consoles (X/Y, Sun/Moon). The
distributor is a different program on the same radio code, so the first run is the test.

## What you need

- A Windows build of azahar_uds (its GitHub Releases, or built from source), in its own folder with
  a portable `user` folder.
- An ESP32-S3 flashed with VC-Adapter's
  [esp32-uds-bridge](https://github.com/Gr3nSkyDragon/VC-Adapter/tree/main/firmware/esp32-uds-bridge)
  firmware, on the chip's native USB port. **This replaces the pokeldn firmware**; flash pokeldn's
  image again (Board page or `docs/flashing_bluetooth.md`) when you go back to Switch or DS gifts.
- Your Gen 6 and/or Gen 7 Local Distributor CIA and its extdata backup (Checkpoint), from your CFW 3DS.
- Keys: azahar_uds's trading works without your own keys. If anything asks for them, dump them with
  GodMode9's DumpKeys script and put the file in `user\sysdata\` as **`keys.txt`**.

## One-time setup

1. **Firmware.** Flash esp32-uds-bridge to the ESP32-S3 at offset `0x0` (the fork's flasher, or
   esptool). Plug it into the PC.
2. **Radio.** In azahar_uds: Emulation → Configure → General → Network, tick **ESP32**, press
   **Connect**; it should find the board.
3. **Distributor.** File → Install CIA → the distributor. Start it once and close it, so its
   extdata folders exist.
4. **Its extdata.** Copy the *contents* of your Checkpoint extdata backup into
   `user\sdmc\Nintendo 3DS\00000000000000000000000000000000\00000000000000000000000000000000\extdata\00000000\<id>\user\`.
   `<id>` is `00000ec5` for the Gen 6 distributor (it uses Pokemon X's extdata id); for Gen 7 it is
   the folder the distributor created in step 3 (Pokemon Sun's id).
5. **Clock.** The distributor only sends inside its distribution period. In Configure → System,
   set the clock to a **fixed time** inside the period it shows.

## Each time: pick a card and distribute

```powershell
cd "C:\Users\scar_\Documents\GitHub\PokeLDN-Bluetooth"
.\tools\uds\run_distributor.ps1 -Azahar "C:\Azahar-UDS" -Card "C:\cards\0566 XYORAS - GF Genesect (US) (ENG).wc6full"
```

The script swaps the card (keeping a `.bak-<time>` of the old one), then starts azahar_uds. Open the
distributor, hold **X+Y** to start distributing, and on the 3DS choose Mystery Gift → Receive Gift →
**Get via Local Wireless**.

Cards: `.wc6full`/`.wc7full` are used as they are. A bare `.wc6`/`.wc7` takes the header of the card
already in the distributor. `--version`/`--language` on `tools\uds\distributor_card.py` override the
header (Gen 6: 1 X, 2 Y, 4 OR, 8 AS; Gen 7: 1 S, 2 M, 4 US, 8 UM; 15 all; language 0 any). Only the
one card the distributor holds is sent; swap and restart for the next.

`--list` shows what is installed without changing anything:

```powershell
.\.venv\Scripts\python.exe tools\uds\distributor_card.py --dir "C:\Azahar-UDS\user" --list
```

## Record while you are at it

Add `-Record` to write the distributor's broadcast to `captures\` through the plaintext UDP bridge.
azahar_uds turns its ESP32 backend off while that bridge is on, so a `-Record` run is for recording
only: no 3DS sees it. Record, then run again without `-Record` to distribute. Those files are what pokeldn's own distributor
([3ds_uds.md](3ds_uds.md), phase 2) is built from; send them along.

## If the 3DS sees nothing

- Azahar's log (File → Open Log Folder): look for `UDS Real` lines. No beacon lines means the ESP32
  is not driving the radio (redo step 2).
- The distributor screen must show it is distributing (X+Y), and the clock must be inside the period.
- Keep the 3DS within a metre or two for the first try; the board's antenna matters.
- If the 3DS finds the distributor but fails mid-transfer, save Azahar's log and the `-Record`
  capture: that is the part azahar_uds has never been tested on.

## Without Azahar: replay a recorded distribution from the ESP32

A Gen 7 Local Distributor never lets the console join: it cycles its beacon's application data through
the card's fragments (each held about 0.55 s) and the game only listens. A recording of those beacons
is therefore the whole distribution, and the board can replay it alone.

1. Record once (`-Record`, above). Each distribution needs its own recording.
2. Make a gift pack, a small JSON file to keep:
   `python tools/uds/gift_replay.py pack captures\distributor-<time>.jsonl --name "Krookodile #665" --out gifts\krookodile-665.gift.json`
3. Close azahar_uds (it must not hold the board's COM port), then:
   `python tools/uds/gift_replay.py send gifts\krookodile-665.gift.json --port COM8`
4. On the 3DS: Mystery Gift → Receive Gift → Get via Local Wireless. Ctrl+C stops.

The board runs the same esp32-uds-bridge firmware. Packs keep the recorded host MAC, because the
beacon's encrypted node data is keyed to it. Gift packs hold Nintendo's distribution data from your
own distributor saves; keep them out of the public repository.

## On the PokeLDN board and in the app (no second computer)

The board's own radio firmware (1.10.0 or later) replays a gift pack with nothing attached, the way
it already hosts Switch and FireRed gifts. Flash PokeLDN's Bluetooth firmware (Board page), not the
azahar_uds bridge.

Command line:

    POKELDN_RADIO=esp32:auto python tools/uds/gift_send_board.py gifts/krookodile-665.gift.json

In the app, **Nintendo 3DS** appears in the Games list beside **Nintendo DS** (the `n3ds_plugin`
plugin; bundled in the Android APK, installed from `examples/android/n3ds_plugin` on the desktop).
Select it, pick a gift (a Wonder Card recorded into a gift pack in the `gifts/` folder), and press
Start in the Session tab: the board stores the pack's beacons and broadcasts them, and the board's
LED flashes while it distributes. Put more packs in the `gifts/` folder (or `$POKELDN_GIFTS`).

The bundled Gen 7 Wonder Card catalog (`scripts/gen_3ds_gift_catalog.py` builds it from a Project
Pokemon EventsGallery archive into `pokeldn/data/gift3ds`, grouped Sun / Moon and Ultra Sun / Ultra
Moon) names each recorded pack by its card and games; it is the library and the record source, not a
set of sendable cards on its own.

A card cannot be sent straight from its `.wc7full`: the distributor encrypts part of every beacon,
so each card is recorded once from a real distributor (above) and then replayed. The firmware image
is built by `pokeldn/uds/portable3ds.py` (ADVERT_KIND_3DS) and carries only the recorded beacons —
no console key or save data.
