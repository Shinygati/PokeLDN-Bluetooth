#!/usr/bin/env python3
"""Put a Wonder Card into a Gen 6 or Gen 7 Local Distributor's extdata (docs/3ds_local_distributor.md).

The distributor keeps its card as a 0x310-byte .wc6full/.wc7full file (Gen 6: hashin/1). This finds
that file by its distribution CRC, backs it up, and replaces it with your card. A bare .wc6/.wc7
borrows the header of the card already there. The CRC is recomputed.

    # See what is there (an Azahar user folder, or a Checkpoint extdata backup folder):
    python tools/uds/distributor_card.py --dir "C:/Azahar-A/user" --list
    # Swap in a card:
    python tools/uds/distributor_card.py --dir "C:/Azahar-A/user" --card "0566 XYORAS - GF Genesect (US) (ENG).wc6full"

--dir may be an Azahar user folder (searched under sdmc/Nintendo 3DS/.../extdata), an extdata folder
or a Checkpoint backup of one. --version and --language override the header's version mask
(Gen 6: 1 X, 2 Y, 4 OR, 8 AS; Gen 7: 1 S, 2 M, 4 US, 8 UM; 0 or 15 all) and language (0 = any).
"""
import argparse
import os
import re
import shutil
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from pokeldn.uds.cards import FULL_SIZE, card_id, is_full_card, title, to_full  # noqa: E402

# The Gen 6 distributor uses Pokemon X's extdata id 0xEC5: Azahar's folder 00000ec5, Checkpoint's "0x00EC5 ...".
GEN6_EXTDATA = re.compile(r"(^|[/\\])(0x)?0*ec5([/\\ ]|$)", re.IGNORECASE)


def is_gen6_path(path: str) -> bool:
    return bool(GEN6_EXTDATA.search(path))


def find_cards(root: str) -> list[str]:
    """Every 0x310-byte file with a valid distribution CRC under root (skipping our backups)."""
    found = []
    for folder, _dirs, files in os.walk(root):
        for name in files:
            if ".bak-" in name:
                continue
            path = os.path.join(folder, name)
            try:
                if os.path.getsize(path) != FULL_SIZE:
                    continue
                with open(path, "rb") as f:
                    if is_full_card(f.read()):
                        found.append(path)
            except OSError:
                continue
    return sorted(found)


def search_root(directory: str) -> str:
    """Narrow an Azahar user folder to its extdata container when it has one."""
    for sub in ("sdmc/Nintendo 3DS", "Nintendo 3DS"):
        candidate = os.path.join(directory, sub)
        if os.path.isdir(candidate):
            return candidate
    return directory


def describe(path: str) -> str:
    with open(path, "rb") as f:
        data = f.read()
    gen = "Gen 6" if is_gen6_path(path) else "Gen 6/7"
    return f"{path}\n    {gen} card #{card_id(data)}: {title(data)!r} (versions {data[0]:#x}, language {data[0x1FF]})"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dir", required=True, help="Azahar user folder, extdata folder, or Checkpoint backup")
    parser.add_argument("--card", help=".wc6full/.wc7full (or bare .wc6/.wc7) to install")
    parser.add_argument("--list", action="store_true", help="only list the cards found")
    parser.add_argument("--target", help="which found file to replace, when there is more than one")
    parser.add_argument("--version", type=lambda v: int(v, 0), help="version mask override")
    parser.add_argument("--language", type=lambda v: int(v, 0), help="language override (0 = any)")
    args = parser.parse_args(argv)

    cards = find_cards(search_root(args.dir))
    if not cards:
        print(f"No distributor card found under {args.dir}. Run the distributor once with a distribution "
              "loaded (or restore its Checkpoint extdata) and try again.")
        return 1
    if args.list or not args.card:
        for path in cards:
            print(describe(path))
        return 0

    if args.target:
        target = os.path.abspath(args.target)
        if target not in map(os.path.abspath, cards):
            print(f"--target {args.target} is not one of the cards found (run --list).")
            return 1
    elif len(cards) == 1:
        target = cards[0]
    else:
        print("More than one card found; pick one with --target:")
        for path in cards:
            print(describe(path))
        return 1

    with open(args.card, "rb") as f:
        new = f.read()
    with open(target, "rb") as f:
        old = f.read()
    ext = os.path.splitext(args.card)[1].lower()
    if ext.startswith(".wc7") and is_gen6_path(target):
        print("Warning: a .wc7 card going into the Gen 6 distributor's extdata; X/Y/OR/AS will not accept it.")
    try:
        full = to_full(new, old, args.version, args.language)
    except ValueError as error:
        print(error)
        return 1

    backup = f"{target}.bak-{time.strftime('%Y%m%d-%H%M%S')}"
    shutil.copy2(target, backup)
    with open(target, "wb") as f:
        f.write(full)
    print(f"Installed card #{card_id(full)} {title(full)!r} (versions {full[0]:#x}, language {full[0x1FF]})")
    print(f"  into {target}\n  previous card saved as {backup}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
