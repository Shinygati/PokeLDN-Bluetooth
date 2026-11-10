"""Generate new card payloads inside an existing distributor network envelope."""
import struct
from dataclasses import replace
from .card_codec import lz10_encode, sign_payload
from .cards import to_full, card_id, title
from .frames import Beacon, NintendoTag, NINTENDO_OUI, TagId
from .gift_pack import GiftPack


def packet_crc(data):
    value = 0xffff
    for byte in data:
        value ^= byte
        for _ in range(8):
            value = (value >> 1) ^ (0xa001 if value & 1 else 0)
    return value ^ 0xffff


def build_pack(card, template, private_der, public_der, header_template=None):
    """Keep the recorded network identity; generate and sign all card fragments anew.

    The template must be a compatible distributor envelope for the target games.
    It supplies encrypted node data; no NWM console key is required.
    """
    beacon = Beacon.parse(template.beacons[0])
    info = beacon.network_info
    if info is None or len(info.application_data) != 200 or not info.sha1_ok:
        raise ValueError('Template lacks a valid 200-byte distributor application tag')
    old = info.application_data
    if old[16:20] != bytes.fromhex('a80b0000'):
        raise ValueError('Unsupported distributor envelope')
    if packet_crc(old[2:]) != int.from_bytes(old[:2], 'little'):
        raise ValueError('Template application checksum is invalid')
    if len(card) == 264 and header_template is None:
        raise ValueError('Bare cards require a full-card distribution header')
    full = to_full(card, header_template or bytes(784))
    packed = lz10_encode(full)
    signed = sign_payload(packed, private_der, public_der)
    body = struct.pack('<II', len(full), len(packed)) + signed
    count = len(body) // 160 + 1
    if count > 8:
        raise ValueError('Card exceeds firmware fragment capacity')
    beacons = []
    for index in range(count):
        app = bytearray(old[:20])
        app += struct.pack('<HBB', card_id(full), count, index)
        app += body[index*160:(index+1)*160].ljust(160, b'\0') + bytes(16)
        struct.pack_into('<H', app, 0, packet_crc(app[2:]))
        network_tag = replace(info, application_data=bytes(app)).build_tag()
        out = bytearray(struct.pack('<QHH', 0, beacon.interval, beacon.capabilities))
        for kind, data in beacon.tags:
            if kind == TagId.VENDOR and data[:4] == NINTENDO_OUI + bytes([NintendoTag.NETWORK_INFO]):
                out += network_tag
            else:
                out += bytes([kind, len(data)]) + data
        beacons.append(bytes(out))
    return GiftPack(template.host_mac, template.channel, template.dwell_ms, beacons,
                    title(full), template.wlan_comm_id)
