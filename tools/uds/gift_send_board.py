#!/usr/bin/env python3
"""Store a 3DS gift pack on the PokeLDN board and have it replay the distribution on its own.

This drives the board's own radio firmware (1.10.0 or later), not the azahar_uds bridge. The board
keeps the image and, 3 s after power-up or at once over Bluetooth, broadcasts the distributor's
beacons for any 3DS to receive with Mystery Gift -> Get via Local Wireless.

    POKELDN_RADIO=esp32:auto python tools/uds/gift_send_board.py gifts/krookodile-665.gift.json

Build a pack from a recording first with gift_replay.py (docs/3ds_local_distributor.md).
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from pokeldn.ldn import esp32, esp32_wlan  # noqa: E402
from pokeldn.uds.gift_pack import GiftPack  # noqa: E402
from pokeldn.uds.portable3ds import build_image  # noqa: E402


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("pack", help="a gift pack .json from gift_replay.py")
    parser.add_argument("--interval-ms", type=int, default=None, help="beacon cadence (default 102)")
    args = parser.parse_args(argv)

    pack = GiftPack.load(args.pack)
    try:
        image = build_image(pack, interval_ms=args.interval_ms or 102)
    except ValueError as error:
        print(f"the pack cannot be stored: {error}", file=sys.stderr)
        return 1

    radio = esp32_wlan.use_from_environment(log=print)
    if radio is None:
        print("set POKELDN_RADIO=esp32:auto (or esp32:COM8) to pick the board", file=sys.stderr)
        return 1
    try:
        if esp32.firmware_version(radio.hello()) < esp32.BEACON_3DS_FIRMWARE:
            need = ".".join(map(str, esp32.BEACON_3DS_FIRMWARE))
            print(f"the board's firmware sends no 3DS gift; install radio firmware {need} or later "
                  "from the Board page", file=sys.stderr)
            return 1
        state = radio.store_beacon(image)
        started = esp32_wlan.keep_running(radio)
    except (OSError, RuntimeError, esp32.RadioError) as error:
        print(str(error), file=sys.stderr)
        return 1

    where = f"{pack.name or args.pack}: {len(pack.beacons)} beacons, {state.length} bytes on the board"
    if started:
        print(f"{where}. {esp32_wlan.KEPT_OVER_BLUETOOTH}")
    else:
        print(f"{where}. Unplug it and power it from any USB charger; 3 s after power-up it replays "
              "the distribution for every 3DS, until a computer opens it.")
    print("On the 3DS: Mystery Gift -> Receive Gift -> Get via Local Wireless.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
