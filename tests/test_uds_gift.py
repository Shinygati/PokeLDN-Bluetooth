"""3DS gift packs and the esp32-uds-bridge serial framing."""

import json
import struct
import zlib

from pokeldn.uds.esp32_bridge import HELLO_ACK, SET_BEACON, cobs_decode, cobs_encode, decode, encode
from pokeldn.uds.frames import NetworkInfo
from pokeldn.uds.gift_pack import GiftPack, beacon_mpdu, from_capture


def firmware_cobs_encode(data: bytes) -> bytes:
    """A line-by-line transliteration of VC-Adapter main/uds_wire.c cobs_encode."""
    out = bytearray([0])
    code_index, code = 0, 1
    for byte in data:
        if byte == 0:
            out[code_index] = code
            code_index = len(out)
            out.append(0)
            code = 1
        else:
            out.append(byte)
            code += 1
            if code == 0xFF:
                out[code_index] = code
                code_index = len(out)
                out.append(0)
                code = 1
    out[code_index] = code
    return bytes(out)


def _payload(n, k):
    return bytes(0 if (i * 37 + k) % 251 == 0 else (i * 37 + k) % 251 for i in range(n))


def test_cobs_matches_the_firmware_and_round_trips():
    for k, n in enumerate((0, 1, 7, 253, 254, 255, 422, 508, 509, 600)):
        data = _payload(n, k)
        assert cobs_encode(data) == firmware_cobs_encode(data), n
        assert cobs_decode(cobs_encode(data)) == data, n
        zeros = bytes(n)
        assert cobs_encode(zeros) == firmware_cobs_encode(zeros) and cobs_decode(cobs_encode(zeros)) == zeros


def test_frame_layout_and_crc():
    frame = encode(SET_BEACON, 5, b"\x01\x02")
    assert frame.endswith(b"\0") and b"\0" not in frame[:-1]
    raw = cobs_decode(frame[:-1])
    assert raw[:6] == bytes([1, SET_BEACON, 5, 0, 2, 0]) and raw[6:8] == b"\x01\x02"
    assert struct.unpack_from("<I", raw, 8)[0] == zlib.crc32(raw[:8]) & 0xFFFFFFFF
    assert decode(frame[:-1]) == (SET_BEACON, 5, b"\x01\x02")
    damaged = bytearray(frame[:-1])
    damaged[3] ^= 0x40
    assert decode(bytes(damaged)) is None
    assert decode(encode(HELLO_ACK, 1, bytes([1, 1, 8]))[:-1]) == (HELLO_ACK, 1, bytes([1, 1, 8]))


def _beacon_body(fragment: int) -> bytes:
    info = NetworkInfo(0x00164810, 2, 0x8000, 0x6837DABF, 1, 2, bytes([fragment]) * 200)
    return struct.pack("<QHH", 0, 100, 0x0431) + b"\x00\x08" + bytes(8) + info.build_tag()


def test_pack_from_capture_keeps_cycle_order_and_dwell():
    mac = "60:6b:ff:9b:51:dd"
    records, t = [], 1000.0
    for cycle in range(4):
        for fragment in range(3):
            for _ in range(5):
                body = bytearray(_beacon_body(fragment))
                body[0:8] = struct.pack("<Q", int(t * 1e6))          # timestamps differ per beacon
                records.append({"t": t, "from": "a", "type": "beacon", "channel": 11, "src": mac,
                                "dst": "ff:ff:ff:ff:ff:ff", "data": bytes(body).hex()})
                t += 0.1024
    pack = from_capture(records, name="test")
    assert len(pack.beacons) == 3 and pack.channel == 11 and pack.wlan_comm_id == 0x00164810
    assert 500 <= pack.dwell_ms <= 530
    assert [NetworkInfoBody(b) for b in pack.beacons] == [0, 1, 2]
    again = GiftPack.from_json(pack.to_json())
    assert again.beacons == pack.beacons and again.host_mac == bytes.fromhex("606bff9b51dd")
    mpdu = pack.mpdu(1)
    assert mpdu[:4] == b"\x80\x00\x00\x00" and mpdu[4:10] == b"\xff" * 6
    assert mpdu[10:16] == mpdu[16:22] == pack.host_mac and mpdu[24:] == pack.beacons[1]
    assert beacon_mpdu(pack.host_mac, b"x" * 12)[22:24] == b"\0\0"
    json.loads(pack.to_json())


def NetworkInfoBody(body: bytes) -> int:
    from pokeldn.uds.frames import Beacon
    return Beacon.parse(body).network_info.application_data[0]


class FakeBoard:
    """Answers like esp32-uds-bridge: HELLO -> HELLO_ACK, any other command -> STATUS 0."""

    def __init__(self, *args, **kwargs):
        self.inbox, self.outbox, self.commands = bytearray(), bytearray(), []

    def write(self, data):
        self.inbox += data
        while b"\0" in self.inbox:
            raw, _, rest = self.inbox.partition(b"\0")
            self.inbox = bytearray(rest)
            if not raw:
                continue
            kind, seq, payload = decode(bytes(raw))
            self.commands.append((kind, payload))
            if kind == 0x01:
                self.outbox += encode(HELLO_ACK, seq, bytes([1, 1, 8]) + bytes(6))
            else:
                self.outbox += encode(0x82, seq, bytes([kind]) + struct.pack("<i", 0))

    def read(self, n):
        data, self.outbox = bytes(self.outbox[:n]), self.outbox[n:]
        return data

    def close(self):
        pass


def test_bridge_conversation(monkeypatch):
    import serial
    from pokeldn.uds.esp32_bridge import Bridge
    board = FakeBoard()
    monkeypatch.setattr(serial, "Serial", lambda *a, **k: board)
    bridge = Bridge("COM8", log=lambda *_: None)
    bridge.open(timeout=2)
    assert bridge.firmware == "1.8"
    mac = bytes.fromhex("606bff9b51dd")
    assert bridge.start(11, mac) == 0
    assert bridge.set_beacon(beacon_mpdu(mac, _beacon_body(0))) == 0
    assert bridge.stop() == 0
    kinds = [k for k, _ in board.commands]
    assert kinds == [0x01, 0x02, 0x07, 0x07, 0x03]
    assert board.commands[1][1] == bytes([11]) + mac
    assert board.commands[3][1] == b""                      # stop clears the beacon first
