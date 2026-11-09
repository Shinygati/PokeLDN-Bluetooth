"""Gen 6 and Gen 7 Wonder Cards in the Local Distributor's form (.wc6full / .wc7full).

A full card is 0x310 bytes: a 0x208-byte distribution header, then the 0x108-byte .wc6/.wc7 card.
PKHeX reads the version mask at 0x000 and the language at 0x1FF (WC6Full.cs, WC7Full.cs). The header's
u16 at 0x202 is a CRC-16/CCITT-FALSE (initial 0xFFFF) of the whole 0x310 bytes with that field zero,
stored little-endian; it matches every released card checked (tests/test_uds_cards.py).
"""

from __future__ import annotations

FULL_SIZE = 0x310
CARD_SIZE = 0x108
HEADER_SIZE = FULL_SIZE - CARD_SIZE      # 0x208
CRC_OFFSET = 0x202
VERSION_OFFSET = 0x000
LANGUAGE_OFFSET = 0x1FF


def crc16_ccitt(data: bytes, crc: int = 0xFFFF) -> int:
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


def full_crc(full: bytes) -> int:
    blank = bytearray(full[:FULL_SIZE])
    blank[CRC_OFFSET:CRC_OFFSET + 2] = b"\0\0"
    return crc16_ccitt(bytes(blank))


def is_full_card(data: bytes) -> bool:
    """A 0x310-byte file whose distribution CRC is right."""
    return len(data) == FULL_SIZE and int.from_bytes(data[CRC_OFFSET:CRC_OFFSET + 2], "little") == full_crc(data)


def fix_crc(full: bytes) -> bytes:
    out = bytearray(full)
    out[CRC_OFFSET:CRC_OFFSET + 2] = full_crc(out).to_bytes(2, "little")
    return bytes(out)


def to_full(card: bytes, template: bytes, version: int | None = None, language: int | None = None) -> bytes:
    """A full card from a .wc6full/.wc7full (returned with its CRC rechecked) or from a bare .wc6/.wc7,
    which takes ``template``'s distribution header (normally the card already in the distributor)."""
    if len(card) == FULL_SIZE:
        out = bytearray(card)
    elif len(card) == CARD_SIZE:
        if len(template) != FULL_SIZE:
            raise ValueError("a bare .wc6/.wc7 needs a full card's header as a template")
        out = bytearray(template[:HEADER_SIZE]) + bytearray(card)
    else:
        raise ValueError(f"not a Gen 6/7 Wonder Card: {len(card)} bytes (want 0x108 or 0x310)")
    if version is not None:
        out[VERSION_OFFSET] = version
    if language is not None:
        out[LANGUAGE_OFFSET] = language
    return fix_crc(bytes(out))


def title(full_or_card: bytes) -> str:
    """The card's title: UTF-16LE at 0x02 of the .wc6/.wc7 portion, up to 0x48 bytes."""
    card = full_or_card[HEADER_SIZE:] if len(full_or_card) == FULL_SIZE else full_or_card
    text = card[0x02:0x02 + 0x48].decode("utf-16-le", "replace")
    return text.split("\0", 1)[0].strip()


def card_id(full_or_card: bytes) -> int:
    card = full_or_card[HEADER_SIZE:] if len(full_or_card) == FULL_SIZE else full_or_card
    return int.from_bytes(card[0:2], "little")
