"""Gen 6 unsigned LZ10 beacon distribution, verified against two distributor captures."""
import binascii
import struct
from dataclasses import replace
from pathlib import Path
from .card_codec import lz10_encode, lz10_decode
from .cards import to_full, card_id, title
from .frames import Beacon, NintendoTag, NINTENDO_OUI, TagId
from .gift_pack import GiftPack

ENVELOPE = Path(__file__).parents[1] / 'data/gift3ds/gen6-envelope.json'


def unpack_card(pack):
    fragments = {}
    for body in pack.beacons:
        info = Beacon.parse(body).network_info
        if not info or not info.sha1_ok:
            raise ValueError('Invalid Gen 6 network tag')
        a = info.application_data
        if len(a) != 184 or binascii.crc_hqx(a[2:], 0xffff) != int.from_bytes(a[:2], 'little'):
            raise ValueError('Invalid Gen 6 application checksum')
        if a[23] in fragments or a[23] >= a[22]:
            raise ValueError('Duplicate or invalid fragment')
        fragments[a[23]] = a
    if not fragments or set(fragments) != set(range(fragments[0][22])):
        raise ValueError('Incomplete Gen 6 card')
    if len({a[2:22] for a in fragments.values()}) != 1:
        raise ValueError('Mixed Gen 6 card fragments')
    stream = b''.join(fragments[i][24:] for i in range(len(fragments)))
    size, packed = struct.unpack_from('<II', stream)
    if size != 784 or packed > len(stream)-8:
        raise ValueError('Invalid card length')
    result = lz10_decode(stream[8:8+packed])
    if len(result) != size or card_id(result) != int.from_bytes(fragments[0][20:22], 'little'):
        raise ValueError('Card identity mismatch')
    return result


def build_pack(card, *, template=None, version=None, language=None):
    template = template or GiftPack.load(ENVELOPE)
    original = unpack_card(template)
    full = to_full(card, original, version=version, language=language)
    packed = lz10_encode(full)
    stream = struct.pack('<II', len(full), len(packed)) + packed
    count = len(stream)//160+1
    if count > 8:
        raise ValueError('Card exceeds radio fragment capacity')
    beacon = Beacon.parse(template.beacons[0])
    info = beacon.network_info
    beacons = []
    for index in range(count):
        a = bytearray(info.application_data[:20])
        a += struct.pack('<HBB', card_id(full), count, index)
        a += stream[index*160:(index+1)*160].ljust(160, b'\0')
        struct.pack_into('<H', a, 0, binascii.crc_hqx(a[2:], 0xffff))
        updated = replace(info, application_data=bytes(a)).build_tag()
        body = bytearray(struct.pack('<QHH', 0, beacon.interval, beacon.capabilities))
        for kind, data in beacon.tags:
            body += updated if kind == TagId.VENDOR and data[:4] == NINTENDO_OUI+bytes([NintendoTag.NETWORK_INFO]) else bytes([kind, len(data)])+data
        beacons.append(bytes(body))
    result = GiftPack(template.host_mac, template.channel, template.dwell_ms, beacons, title(full), template.wlan_comm_id)
    if unpack_card(result) != full:
        raise ValueError('Generated card verification failed')
    return result
