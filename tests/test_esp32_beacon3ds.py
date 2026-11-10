"""The 3DS portable beacon: the board's image parser and beacon-frame builder
(firmware/esp32/main/advert.c, compiled here) against a gift pack built by pokeldn.uds.portable3ds."""
import ctypes
import os
import struct
import subprocess

import pytest

from pokeldn.uds import portable3ds
from pokeldn.uds.gift_pack import GiftPack, beacon_mpdu

SOURCE = os.path.join(os.path.dirname(__file__), "..", "firmware", "esp32", "main", "advert.c")


class Image(ctypes.Structure):
    _fields_ = [("channel", ctypes.c_uint8), ("bssid", ctypes.c_uint8 * 6),
                ("ssid", ctypes.c_uint8 * 32), ("data_key", ctypes.c_uint8 * 16),
                ("max_stations", ctypes.c_uint8), ("advertise_key", ctypes.c_uint8 * 16),
                ("header", ctypes.c_uint8 * 40), ("interval_ms", ctypes.c_uint16),
                ("dwell_ms", ctypes.c_uint16), ("count", ctypes.c_uint8),
                ("display_count", ctypes.c_uint8), ("plain", ctypes.c_void_p * 10),
                ("plain_len", ctypes.c_uint16 * 10), ("display", ctypes.c_void_p * 4),
                ("display_len", ctypes.c_uint16 * 4), ("kind", ctypes.c_uint8),
                ("records", ctypes.c_void_p), ("records_len", ctypes.c_uint16)]


@pytest.fixture(scope="module")
def lib(tmp_path_factory):
    out = tmp_path_factory.mktemp("beacon3ds") / "advert.so"
    cc = os.environ.get("CC", "cc")
    try:
        subprocess.run([cc, "-shared", "-fPIC", "-O2", "-std=c11", "-I",
                        os.path.dirname(SOURCE), SOURCE, "-o", str(out)], check=True,
                       capture_output=True)
    except (OSError, subprocess.CalledProcessError) as error:
        pytest.skip(f"no C compiler for advert.c: {error}")
    dll = ctypes.CDLL(str(out))
    dll.advert_parse.restype = ctypes.c_int
    dll.advert_parse.argtypes = [ctypes.c_char_p, ctypes.c_size_t, ctypes.POINTER(Image)]
    dll.advert_beacon_frame.restype = ctypes.c_size_t
    dll.advert_beacon_frame.argtypes = [ctypes.POINTER(Image), ctypes.c_uint, ctypes.c_uint64,
                                        ctypes.c_uint16, ctypes.c_char_p]
    return dll


def _pack():
    mac = bytes.fromhex("606bff9b51dd")
    beacons = []
    for frag in range(3):
        body = bytearray(struct.pack("<QHH", 0, 100, 0x0431))     # timestamp, interval, caps
        body += bytes([0xDD, 10]) + b"\x00\x1f\x32\x15" + bytes([frag]) * 6   # a vendor tag
        beacons.append(bytes(body))
    return GiftPack(mac, 11, 553, beacons, name="Test #665", wlan_comm_id=0x00164810)


def test_image_parses_as_3ds(lib):
    pack = _pack()
    data = portable3ds.build_image(pack)
    image = Image()
    assert lib.advert_parse(data, len(data), ctypes.byref(image)) == 0
    assert image.kind == portable3ds.KIND_3DS
    assert image.count == 3 and image.channel == 11
    assert bytes(image.bssid) == pack.host_mac
    assert image.dwell_ms == 553 and image.interval_ms == portable3ds.DEFAULT_INTERVAL_MS


def test_beacon_frame_matches_the_host_mpdu(lib):
    pack = _pack()
    data = portable3ds.build_image(pack)
    image = Image()
    assert lib.advert_parse(data, len(data), ctypes.byref(image)) == 0
    out = ctypes.create_string_buffer(24 + portable3ds.PLAIN_MAX)
    for index, beacon in enumerate(pack.beacons):
        n = lib.advert_beacon_frame(ctypes.byref(image), index, 0x1122334455667788, index, out)
        frame = out.raw[:n]
        expected = bytearray(beacon_mpdu(pack.host_mac, beacon))
        expected[22] = (index << 4) & 0xFF
        expected[23] = (index >> 4) & 0xFF
        expected[24:32] = struct.pack("<Q", 0x1122334455667788)      # the refreshed TSF timestamp
        assert frame == bytes(expected)
    # An index past the end yields nothing.
    assert lib.advert_beacon_frame(ctypes.byref(image), 9, 0, 0, out) == 0
