"""Build a portable-beacon image (firmware/esp32/main/advert.c, ADVERT_KIND_3DS) from a 3DS gift
pack. The image is the PKSA container the board already stores for Switch and FireRed gifts, with a
new kind: each fragment is a whole 802.11 beacon body, recorded from a Local Distributor, that the
board broadcasts in turn with no host (docs/3ds_local_distributor.md, the ESP32 replay).

No key or console data goes into the image: the beacons are replayed exactly as the distributor
sent them.
"""

from __future__ import annotations

import struct
import zlib

from .gift_pack import GiftPack

MAGIC = b"PKSA"
LAYOUT = 1
KIND_3DS = 3
HEADER_LEN = 40
IMAGE_MAX = 12288
FRAGMENTS_MAX = 8
FORMAT_PLAIN = 1
PLAIN_MAX = 0x500
DEFAULT_SSID = b"PokeLDN-3DS"
# A 3DS beacon carries its interval as 100 TU (102.4 ms); the board re-sends on the same cadence.
DEFAULT_INTERVAL_MS = 102


def build_image(pack: GiftPack, *, interval_ms: int = DEFAULT_INTERVAL_MS,
                ssid: bytes = DEFAULT_SSID) -> bytes:
    """The stored image for ``pack``. Raises ValueError if it would be refused by advert_parse."""
    if not 1 <= len(pack.beacons) <= FRAGMENTS_MAX:
        raise ValueError(f"{len(pack.beacons)} beacons; the board stores 1 to {FRAGMENTS_MAX}")
    if len(pack.host_mac) != 6 or pack.host_mac[0] & 1:
        raise ValueError("the host MAC must be six bytes and unicast")
    if not 1 <= pack.channel <= 13:
        raise ValueError(f"channel {pack.channel} is outside 1..13")
    dwell_ms = pack.dwell_ms
    if not 20 <= interval_ms <= 1000:
        raise ValueError("the interval is 20 to 1000 ms")
    if dwell_ms < interval_ms:
        raise ValueError("the dwell must be at least the interval")
    for body in pack.beacons:
        if not 12 <= len(body) <= PLAIN_MAX:
            raise ValueError(f"a beacon body of {len(body)} bytes is outside 12..{PLAIN_MAX}")

    header = bytearray(HEADER_LEN)
    header[33] = FORMAT_PLAIN

    body = bytearray()
    body += MAGIC + bytes((LAYOUT, KIND_3DS)) + bytes(2)                 # magic, layout, kind, size
    body += bytes((pack.channel,)) + bytes(pack.host_mac)               # channel, bssid
    body += ssid[:32].ljust(32, b"\0")                                 # ssid (AP label; unused by game)
    body += bytes(16)                                                   # data key: none
    body += bytes((1,))                                                 # max stations: no joins, keep >0
    body += bytes(16)                                                   # advertise key: none
    body += bytes(header)
    body += struct.pack("<HHBBH", interval_ms, dwell_ms, len(pack.beacons), 0, 0)
    assert len(body) == 128

    for beacon in pack.beacons:
        body += struct.pack("<H", len(beacon)) + bytes(beacon)

    struct.pack_into("<H", body, 6, len(body) + 4)
    body += struct.pack("<I", zlib.crc32(bytes(body)) & 0xFFFFFFFF)
    if len(body) > IMAGE_MAX:
        raise ValueError(f"the image is {len(body)} bytes; the board stores at most {IMAGE_MAX}")
    return bytes(body)
