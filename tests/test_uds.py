"""3DS UDS frames, crypto and the azahar_uds bridge relay (pokeldn.uds)."""

import hashlib
import io
import json
import socket
import struct

import pytest

from pokeldn.uds import crypto
from pokeldn.uds.bridge import Relay, WifiPacket, PacketType
from pokeldn.uds.decode import describe
from pokeldn.uds.frames import (Beacon, BeaconNode, EapolLogoff, EapolNode, EapolStart, NetworkInfo, SecureData,
                                association_response_body, beacon_plain_data, pack_secure_data,
                                parse_association_response, parse_beacon_plain_data, split_llc, unpack_secure_data)

HOST = bytes.fromhex("40f407112233")
INFO = NetworkInfo(wlan_comm_id=0x00055D00, id=0x55, attributes=0x0001, network_id=0x1A2B3C4D,
                   total_nodes=1, max_nodes=2, application_data=bytes(range(16)))


def test_network_info_tag_round_trips_and_hashes_like_azahar():
    tag = INFO.build_tag()
    assert tag[0] == 0xDD and tag[1] == len(tag) - 2 == 0x34 + 16   # NetworkInfoTag (54) - header + appdata
    body = tag[2:]
    # Azahar: SHA-1 from network_info to the end, the hash field zero while hashing.
    assert body[0x1F:0x33] == hashlib.sha1(body[:0x1F] + bytes(20) + body[0x33:]).digest()
    parsed = NetworkInfo.parse_tag_body(body)
    assert parsed.sha1_ok and parsed.network_id == INFO.network_id and parsed.application_data == INFO.application_data
    # Big-endian comm id at NetworkInfo 0x10, i.e. tag offset 4.
    assert body[4:8] == b"\x00\x05\x5d\x00"


def test_beacon_parse_finds_nintendo_tags_and_encrypted_node_data():
    key = bytes(range(16))
    nodes = [BeaconNode(0x1122334455667788, "PokeLDN", 1), BeaconNode(0, "", 0)]
    plain = beacon_plain_data(nodes, 0x0001)
    sealed = crypto.crypt_beacon_data(key, HOST, INFO, plain)
    body = (struct.pack("<QHH", 900000000, 100, 0x0431) + b"\x00\x08" + bytes(8)
            + bytes([0xDD, 7]) + b"\x00\x1f\x32\x14\x0a\x00\x00"
            + INFO.build_tag() + bytes([0xDD, 4 + len(sealed)]) + b"\x00\x1f\x32\x18" + sealed)
    beacon = Beacon.parse(body)
    assert beacon.network_info.wlan_comm_id == INFO.wlan_comm_id
    ok, bitmask, parsed = parse_beacon_plain_data(crypto.crypt_beacon_data(key, HOST, INFO, beacon.encrypted_data))
    assert ok and bitmask == 1 and parsed[0].username == "PokeLDN" and parsed[0].network_node_id == 1
    assert len(crypto.beacon_counter(HOST, INFO)) == 16


def test_secure_data_container_and_aggregation():
    one = SecureData(channel=1, sequence=7, dest_node=0xFFFF, src_node=1, payload=b"hello")
    body = split_llc(one.pack())[1]
    # Container: size of everything after the LLC header, packet count 1, then the sub-packet.
    assert struct.unpack_from(">HH", body) == (4 + 10 + 5, 1)
    assert struct.unpack_from(">H", body, 4)[0] == 15
    two = pack_secure_data([one, SecureData(2, 8, 2, 1, b"\x01\x02", is_management=1)])
    packets = unpack_secure_data(split_llc(two)[1])
    assert [(p.channel, p.payload, p.is_management) for p in packets] == [(1, b"hello", 0), (2, b"\x01\x02", 1)]


def test_eapol_sizes_and_retail_fields():
    start = EapolStart(association_id=1, connection_type=1, node=EapolNode(0xABCDEF, "Serena", 0))
    packed = start.pack()
    assert len(packed) == 8 + 0x30
    assert packed[8 + 4:8 + 6] == b"\x00\x01"             # connection type, big-endian u16
    assert EapolStart.unpack(packed[8:]).node.username == "Serena"

    logoff = EapolLogoff(2, HOST, 2, 2, [EapolNode(1, "Host", 1), EapolNode(0xABCDEF, "Serena", 2)])
    packed = logoff.pack()
    assert len(packed) == 8 + 0x298
    assert packed[8 + 0x0E] == 6                           # retail host status
    parsed = EapolLogoff.unpack(packed[8:])
    assert parsed.assigned_node_id == 2 and [n.username for n in parsed.nodes] == ["Host", "Serena"]


def test_association_response():
    body = association_response_body(1, 0x1A2B3C4D)
    assert parse_association_response(body) == (0x0431, 0, 1)
    assert body[6:16] == b"\x00\x081A2B3C4D"


def test_ccmp_matches_ieee_80211_test_vector():
    # IEEE 802.11-2012 M.6.4: CCMP encapsulation test vector.
    key = bytes.fromhex("c97c1f67ce371185514a8a19f2bdd52f")
    header = bytes.fromhex("0848c32c0fd2e128a57c5030f1844408abaea5b8fcba8033")
    plain = bytes.fromhex("f8ba1a55d02f85ae967bb62fb6cda8eb7e78a050")
    frame = crypto.ccmp_encrypt(key, header, 0xB5039776E70C, plain)
    assert frame[24:].hex() == ("0ce70020769703b5f3d0a2fe9a3dbf2342a643e43246e80c3c04d019"
                                "7845ce0b16f97623")
    assert crypto.ccmp_decrypt(key, frame) == (0xB5039776E70C, plain)
    with pytest.raises(ValueError):
        crypto.ccmp_decrypt(key, frame[:-1] + bytes([frame[-1] ^ 1]))


def test_ccmp_key_derivation_inputs():
    counter = crypto.data_counter(HOST, INFO)
    plain = struct.pack("<II", INFO.wlan_comm_id, INFO.network_id) + HOST + struct.pack("<H", INFO.id)
    assert counter == hashlib.md5(plain).digest()
    key = crypto.ccmp_key(bytes(16), b"passphrase\0", HOST, INFO)
    assert len(key) == 16 and key != crypto.ccmp_key(bytes(16), b"other\0", HOST, INFO)


def test_load_keys(tmp_path):
    path = tmp_path / "keys.txt"
    path.write_text("# mine\nnwm_beacon_key=" + "11" * 16 + "\nslot0x2DKeyN = " + "22" * 16 + "\nslot0x2CKeyX=" + "33" * 16 + "\n")
    keys = crypto.load_keys(path)
    assert keys.beacon == bytes([0x11] * 16) and keys.data == bytes([0x22] * 16)


def _free_port_pair():
    """A port N with N + 1 also free (the bridge's listen/send convention)."""
    for _ in range(50):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        if port % 2 == 0 and port < 65000:
            try:
                for p in (port, port + 1):
                    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    s.bind(("127.0.0.1", p))
                    s.close()
                return port
            except OSError:
                continue
    pytest.skip("no free UDP port pair")


def test_relay_forwards_both_ways_and_records():
    a, b = _free_port_pair(), None
    while b is None or abs(b - a) < 2:
        b = _free_port_pair()
    emulator_a = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    emulator_b = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    emulator_a.bind(("127.0.0.1", a))
    emulator_b.bind(("127.0.0.1", b))
    emulator_a.settimeout(2)
    emulator_b.settimeout(2)
    capture = io.StringIO()
    relay = Relay(a, b, capture)
    try:
        hello = WifiPacket(PacketType.DATA, 11, HOST, b"\xff" * 6,
                           SecureData(1, 0, 0xFFFF, 1, b"gift").pack())
        emulator_a.sendto(hello.pack(), ("127.0.0.1", a + 1))
        relay.poll(1.0)
        assert WifiPacket.unpack(emulator_b.recv(4096)) == hello
        reply = WifiPacket(PacketType.AUTHENTICATION, 11, b"\x02" * 6, HOST, b"\x00\x00\x01\x00\x00\x00")
        emulator_b.sendto(reply.pack(), ("127.0.0.1", b + 1))
        relay.poll(1.0)
        assert WifiPacket.unpack(emulator_a.recv(4096)) == reply
    finally:
        relay.close()
        emulator_a.close()
        emulator_b.close()
    records = [json.loads(line) for line in capture.getvalue().splitlines()]
    assert [r["from"] for r in records] == ["a", "b"]
    assert "SD ch=1" in describe(records[0])[0] and "seq=1" in describe(records[1])[0]
