"""The bundled Nintendo 3DS Wonder Card catalog (pokeldn/data/gift3ds, built by
scripts/gen_3ds_gift_catalog.py) and the user's recorded gift packs, for the app's 3DS screen.

A catalogued card is display metadata plus the .wc7full itself. It becomes sendable once recorded
from a Local Distributor into a gift pack (docs/3ds_local_distributor.md); this module pairs cards
with the packs a user has, by card id.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from .gift_pack import GiftPack

DATA = Path(__file__).resolve().parent.parent / "data" / "gift3ds"


def packs_dir() -> Path:
    """Where recorded gift packs live: $POKELDN_GIFTS, else <app root>/gifts."""
    import os

    override = os.environ.get("POKELDN_GIFTS")
    if override:
        return Path(override)
    try:
        from pokeldn.app.paths import ROOT

        return Path(ROOT) / "gifts"
    except Exception:
        return Path.cwd() / "gifts"
GROUP_SM, GROUP_USUM = "sm", "usum"
GROUP_LABELS = {GROUP_SM: "Sun / Moon", GROUP_USUM: "Ultra Sun / Ultra Moon"}
SM_BIT, USUM_BIT = 0x3, 0xC


@dataclass(frozen=True)
class Card:
    id: int
    title: str
    mask: int
    games: tuple[str, ...]
    language: str
    language_code: str
    file: str

    @property
    def path(self) -> Path:
        return DATA / "cards" / self.file

    def in_group(self, group: str) -> bool:
        bit = USUM_BIT if group == GROUP_USUM else SM_BIT
        return bool(self.mask & bit)

    def read(self) -> bytes:
        return self.path.read_bytes()


@dataclass
class Catalog:
    cards: list[Card] = field(default_factory=list)

    @classmethod
    def load(cls, data_dir: Path | str = DATA) -> "Catalog":
        manifest = Path(data_dir) / "manifest.json"
        if not manifest.is_file():
            return cls([])
        raw = json.loads(manifest.read_text(encoding="utf-8"))
        cards = [Card(c["id"], c["title"], c["mask"], tuple(c["games"]), c["language"],
                      c["language_code"], c["file"]) for c in raw.get("cards", [])]
        return cls(cards)

    def group(self, group: str, *, language_code: str | None = None, query: str = "") -> list[Card]:
        """Cards a game in ``group`` can receive, optionally one language, matching ``query``."""
        text = query.strip().lower()
        out = []
        for card in self.cards:
            if not card.in_group(group):
                continue
            if language_code and card.language_code != language_code:
                continue
            if text and text not in card.title.lower() and text not in str(card.id):
                continue
            out.append(card)
        return out

    def languages(self) -> list[tuple[str, str]]:
        seen = {}
        for card in self.cards:
            seen.setdefault(card.language_code, card.language)
        return sorted(seen.items(), key=lambda kv: kv[1])


def load_packs(folder: Path | str) -> dict[int, list[tuple[Path, GiftPack]]]:
    """Every gift pack under ``folder``, grouped by the card id it carries (from its beacons)."""
    packs: dict[int, list[tuple[Path, GiftPack]]] = {}
    root = Path(folder)
    if not root.is_dir():
        return packs
    for path in sorted(root.rglob("*.gift.json")):
        try:
            pack = GiftPack.load(path)
            cid = pack_card_id(pack)
        except (ValueError, OSError, KeyError):
            continue
        packs.setdefault(cid, []).append((path, pack))
    return packs


def pack_card_id(pack: GiftPack) -> int:
    """The card id a pack distributes, read from the id/fragment header of its first beacon's
    application data (the distributor writes the card id at its start)."""
    from .frames import Beacon

    info = Beacon.parse(pack.beacons[0]).network_info
    app = info.application_data if info else b""
    # The distributor's fragment header holds the card id little-endian near its start; the id also
    # appears as the first field. We read it from the stored pack name when present, else 0.
    if pack.name:
        for token in pack.name.replace("#", " ").split():
            if token.isdigit():
                return int(token)
    return int.from_bytes(app[16:18], "little") if len(app) >= 18 else 0
