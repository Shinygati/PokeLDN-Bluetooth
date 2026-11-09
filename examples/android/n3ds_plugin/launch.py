"""Store a recorded Gen 6/7 gift pack on the board and start it broadcasting.

Run by the Session tab's Start. The board keeps broadcasting after this exits (like the FireRed
host), with the LED flashing while it distributes, until a computer opens the board again.
"""
import argparse
import sys


def build_parser():
    parser = argparse.ArgumentParser(description="Broadcast a Nintendo 3DS Gen 6/7 Mystery Gift")
    parser.add_argument("--pack", default="", help="a recorded gift pack (.gift.json)")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)

    from pokeldn.uds.catalog3ds import load_packs, packs_dir

    pack_path = args.pack
    if not pack_path:
        found = [p for entries in load_packs(packs_dir()).values() for p, _ in entries]
        if len(found) == 1:
            pack_path = str(found[0])
        elif not found:
            print("No gift packs found. Record a Wonder Card from a Local Distributor on the PC "
                  "(see docs/3ds_local_distributor.md), then put its .gift.json in the gifts folder.")
            return 1
        else:
            print("Several gift packs are available; choose one in the options, then Start.")
            return 1

    from pokeldn.uds.board3ds import BoardError, send_pack
    from pokeldn.uds.gift_pack import GiftPack

    try:
        pack = GiftPack.load(pack_path)
        length = send_pack(pack, log=print)
    except (OSError, ValueError, BoardError) as error:
        print(str(error))
        return 1
    print(f"Broadcasting {pack.name or pack_path} ({length} bytes on the board).")
    print("On the 3DS: Mystery Gift, Receive Gift, Get via Local Wireless.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
