"""Inspect a Nintendo 3DS Local Distributor beacon-data cycle offline.

These functions deliberately do not broadcast, forge, or claim a valid WC6/WC7
transmission. The captured Krookodile fixture is a protocol regression test.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

APPLICATION_LENGTH = 200
FRAGMENT_HEADER = 24
FIRST_META_LENGTH = 8
FRAGMENT_DATA_LIMIT = 160


@dataclass(frozen=True)
class Fragment:
    packet: bytes
    card_id: int
    index: int
    count: int
    application_size: int
    session_header: bytes
    leading_word: bytes


def parse_fragment(packet: bytes) -> Fragment:
    if len(packet) != APPLICATION_LENGTH:
        raise ValueError(f"Expected {APPLICATION_LENGTH} application bytes, got {len(packet)}")
    card_id = int.from_bytes(packet[20:22], 'little')
    count = packet[22]
    index = packet[23]
    if not 0 < count <= 8 or index >= count:
        raise ValueError(f"Invalid fragment index/count {index}/{count}")
    return Fragment(packet, card_id, index, count, len(packet), packet[2:20], packet[:2])


def validate_cycle(fragments: list[Fragment]) -> list[Fragment]:
    if not fragments:
        raise ValueError("Empty distribution cycle")
    ordered = sorted(fragments, key=lambda x: x.index)
    if len(ordered) != ordered[0].count or [x.index for x in ordered] != list(range(len(ordered))):
        raise ValueError("Distribution cycle is incomplete or has duplicate fragments")
    if len({x.card_id for x in ordered}) != 1:
        raise ValueError("Distribution cycle contains different Wonder Card IDs")
    if len({x.session_header for x in ordered}) != 1:
        raise ValueError("Distribution cycle contains different session headers")
    return ordered


def load_fixture(path: str | Path) -> list[Fragment]:
    blob = json.loads(Path(path).read_text(encoding='utf-8'))
    return validate_cycle([parse_fragment(bytes.fromhex(s)) for s in blob['payloads_hex']])


def packed_card_stream(fragments: list[Fragment]) -> bytes:
    """Recover the captured compressed stream, NOT a valid sendable distribution.

    Observed framing in the supplied three-fragment Krookodile capture:
    fragment 0: 24-byte common header + 8-byte size metadata + up to 152 data bytes
    later ones: 24-byte common header + up to 160 data bytes
    The last 16 bytes of a full fragment are zero padding.
    These offsets are based on one verified sample; other distribution versions may vary.
    """
    cycle = validate_cycle(fragments)
    first = cycle[0].packet
    uncompressed_size = int.from_bytes(first[24:28], 'little')
    packed_size = int.from_bytes(first[28:32], 'little')
    if not 1 <= uncompressed_size <= 0x10000 or not 4 <= packed_size <= 0x10000:
        raise ValueError("Unexpected compressed-card length metadata")
    pieces = [first[32:184]] + [f.packet[24:184] for f in cycle[1:]]
    stream = b''.join(pieces)
    if packed_size > len(stream):
        raise ValueError("Fragment cycle lacks enough compressed data")
    stream = stream[:packed_size]
    if stream[0] != 0x10 or int.from_bytes(stream[1:4], 'little') != uncompressed_size:
        raise ValueError("Not a matching LZ10-card stream")
    return stream


def lz10_prefix(stream: bytes) -> tuple[bytes, int]:
    """Return only safely decoded bytes and source bytes consumed.

    Some captured data beyond the card header does not decode as a contiguous
    standard LZ10 stream. Stop at the first invalid back-reference or truncation
    rather than inventing missing data. This is a *diagnostic*, not an encoder.
    """
    if len(stream) < 4 or stream[0] != 0x10:
        raise ValueError('Expected LZ10 stream')
    expected = int.from_bytes(stream[1:4], 'little')
    output = bytearray()
    pos = 4
    while pos < len(stream) and len(output) < expected:
        flags = stream[pos]
        pos += 1
        for bit in range(7, -1, -1):
            if len(output) >= expected:
                break
            if flags & (1 << bit):
                if pos + 2 > len(stream):
                    return bytes(output), pos
                val = int.from_bytes(stream[pos:pos + 2], 'big')
                length = (val >> 12) + 3
                distance = (val & 0x0FFF) + 1
                if distance > len(output):
                    return bytes(output), pos
                pos += 2
                for _ in range(min(length, expected - len(output))):
                    output.append(output[-distance])
            else:
                if pos >= len(stream):
                    return bytes(output), pos
                output.append(stream[pos])
                pos += 1
    return bytes(output), pos


def compare_to_full_card(fragments: list[Fragment], full_card: bytes) -> dict:
    """Report comparison without assuming the captured header CRC must equal the archive CRC."""
    if len(full_card) != 0x310:
        raise ValueError("Provide a 784-byte .wc6full or .wc7full")
    cycle = validate_cycle(fragments)
    if int.from_bytes(full_card[0x208:0x20A], 'little') != cycle[0].card_id:
        raise ValueError("The supplied card ID differs from the captured distribution")
    output, consumed = lz10_prefix(packed_card_stream(cycle))
    differences = [i for i in range(min(len(output), len(full_card))) if output[i] != full_card[i]]
    return {
        'card_id': cycle[0].card_id,
        'fragments': len(cycle),
        'decoded_prefix_length': len(output),
        'compressed_bytes_consumed': consumed,
        'different_offsets': differences[:32],
        'fully_decoded': len(output) == len(full_card),
        'complete_card_match': output == full_card,
    }
