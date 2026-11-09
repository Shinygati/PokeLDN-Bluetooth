#!/usr/bin/env python3
"""Bundle the Gen 7 Wonder Cards from a Project Pokemon EventsGallery archive, grouped by game, for
the app's Nintendo 3DS Mystery Gift screen.

    python scripts/gen_3ds_gift_catalog.py EventsGallery-20221119.zip

Reads every .wc7full under "Gen 7/3DS/Wondercards/<LANG>/", copies it into
pokeldn/data/gift3ds/cards/ and writes manifest.json: each card's id, title, game set (from the
version mask), language and file. The cards are Nintendo's distribution data; the app displays and
groups them, and a card is sent only once it has been recorded from a Local Distributor into a gift
pack (docs/3ds_local_distributor.md).
"""
import argparse
import json
import os
import re
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pokeldn.uds.cards import FULL_SIZE, HEADER_SIZE, card_id, is_full_card, title  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "pokeldn", "data", "gift3ds")
# Gen 7 version-mask bits.
SM, USUM = 0x3, 0xC
GAME_BIT = [(0x1, "Sun"), (0x2, "Moon"), (0x4, "Ultra Sun"), (0x8, "Ultra Moon")]
LANGS = {"ENG": "English", "JPN": "Japanese", "FRE": "French", "GER": "German", "ITA": "Italian",
         "SPA": "Spanish", "KOR": "Korean", "CHS": "Chinese (Simplified)", "CHT": "Chinese (Traditional)"}


def games_of(mask: int) -> list[str]:
    return [name for bit, name in GAME_BIT if mask & bit]


def group_of(mask: int) -> str:
    """Which screen section a card belongs to: it may appear in both."""
    if mask & SM and mask & USUM:
        return "both"
    return "usum" if mask & USUM else "sm"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("archive", help="an EventsGallery .zip (or an extracted folder)")
    parser.add_argument("--out", default=DATA, help="output data folder")
    args = parser.parse_args(argv)

    cards_dir = os.path.join(args.out, "cards")
    os.makedirs(cards_dir, exist_ok=True)
    entries = []
    seen = set()

    for name, data in _iter_wc7full(args.archive):
        if len(data) != FULL_SIZE or not is_full_card(data):
            continue
        mask = data[0]
        lang_code = _language_code(name)
        cid = card_id(data)
        key = (cid, lang_code, mask)
        if key in seen:
            continue
        seen.add(key)
        filename = f"{cid:04d}_{lang_code}_{mask:x}.wc7full"
        with open(os.path.join(cards_dir, filename), "wb") as out:
            out.write(data)
        entries.append({"id": cid, "title": title(data), "mask": mask, "games": games_of(mask),
                        "group": group_of(mask), "language": LANGS.get(lang_code, lang_code),
                        "language_code": lang_code, "file": filename})

    entries.sort(key=lambda e: (e["id"], e["language_code"]))
    manifest = {"format": "pokeldn-3ds-gift-catalog", "version": 1, "source": os.path.basename(args.archive),
                "groups": {"sm": "Sun / Moon", "usum": "Ultra Sun / Ultra Moon"}, "cards": entries}
    with open(os.path.join(args.out, "manifest.json"), "w", encoding="utf-8") as out:
        json.dump(manifest, out, ensure_ascii=False, indent=1)

    by_group = {"sm": 0, "usum": 0, "both": 0}
    for e in entries:
        by_group[e["group"]] += 1
    print(f"{len(entries)} cards -> {args.out}")
    print(f"  Sun/Moon only {by_group['sm']}, Ultra Sun/Moon only {by_group['usum']}, both {by_group['both']}")
    return 0


def _language_code(path: str) -> str:
    for part in re.split(r"[\\/]", path):
        if part.upper() in LANGS:
            return part.upper()
    return "UNK"


def _iter_wc7full(archive: str):
    if os.path.isdir(archive):
        for folder, _dirs, files in os.walk(archive):
            for name in files:
                if name.lower().endswith(".wc7full") and "3DS" in folder.replace("\\", "/"):
                    with open(os.path.join(folder, name), "rb") as f:
                        yield os.path.join(folder, name), f.read()
        return
    with zipfile.ZipFile(archive) as zf:
        for info in zf.infolist():
            if info.filename.lower().endswith(".wc7full") and "/3DS/" in info.filename.replace("\\", "/"):
                yield info.filename, zf.read(info)


if __name__ == "__main__":
    sys.exit(main())
