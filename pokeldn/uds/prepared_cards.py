"""Resolve generated broadcast packs without carrying signing keys on the phone."""
import hashlib
from pathlib import Path
from .gift_pack import GiftPack

PACKS = Path(__file__).parents[1] / 'data/gift3ds/prepared'


def pack_path(card, root=PACKS):
    return Path(root) / (hashlib.sha256(card).hexdigest() + '.gift.json')


def load_card_pack(path):
    result = pack_path(Path(path).read_bytes())
    if not result.is_file():
        raise ValueError('Prepare this card on the PC with tools/uds/prepare_direct_cards.py, then import its gift pack')
    return GiftPack.load(result)
