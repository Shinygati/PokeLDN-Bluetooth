"""3DS UDS frame bodies, as Azahar's nwm::UDS and a retail 3DS lay them out.

Byte orders follow the console: the 802.11 fixed fields and authentication/association bodies are
little-endian, the Nintendo network info, SecureData and EAPoL structures big-endian.
"""

from __future__ import annotations

import hashlib
import struct
from dataclasses import dataclass, field
from enum import IntEnum

NINTENDO_OUI = b"\x00\x1f\x32"
BROADCAST_NODE = 0xFFFF
MAX_NODES = 16
APPLICATION_DATA_MAX = 0xC8
ENCRYPTED_TAG_CAPACITY = 0xFA       # bytes of encrypted beacon data the first tag (24) carries


class TagId(IntEnum):
    SSID = 0
    SUPPORTED_RATES = 1
    DS_PARAMETER_SET = 2
    TIM = 5
    COUNTRY = 7
    ERP = 42
    VENDOR = 221


class NintendoTag(IntEnum):
    DUMMY = 20
    NETWORK_INFO = 21
    ENCRYPTED_DATA_0 = 24
    ENCRYPTED_DATA_1 = 25


class EtherType(IntEnum):
    SECURE_DATA = 0x876D
    EAPOL = 0x888E


EAPOL_START = 0x0201
EAPOL_LOGOFF = 0x0202
LLC_SNAP = b"\xaa\xaa\x03\x00\x00\x00"


# -------------------------------------------------------------------------------------------------
# Beacons

@dataclass
class NetworkInfo:
    """The NetworkInfo tag (Nintendo type 21): the 0x1F bytes from the OUI on, its SHA-1, app data."""
    wlan_comm_id: int
    id: int
    attributes: int
    network_id: int
    total_nodes: int
    max_nodes: int
    application_data: bytes = b""
    reserved: bytes = bytes(13)       # NetworkInfo 0x1E..0x2A, zero in Azahar's hosts
    sha1_ok: bool | None = None       # set by parsing: did the tag's hash match

    def tag_fields(self) -> bytes:
        """The tag's first 0x1F bytes (NetworkInfo from its OUI)."""
        return (NINTENDO_OUI + bytes([NintendoTag.NETWORK_INFO])
                + struct.pack(">IBBHIBB", self.wlan_comm_id, self.id, 0, self.attributes,
                              self.network_id, self.total_nodes, self.max_nodes)
                + self.reserved)

    def build_tag(self) -> bytes:
        if len(self.application_data) > APPLICATION_DATA_MAX:
            raise ValueError("application data is larger than 0xC8 bytes")
        fields = self.tag_fields()
        assert len(fields) == 0x1F
        size = bytes([len(self.application_data)])
        digest = hashlib.sha1(fields + bytes(20) + size + self.application_data).digest()
        body = fields + digest + size + self.application_data
        return bytes([TagId.VENDOR, len(body)]) + body

    @classmethod
    def parse_tag_body(cls, body: bytes) -> "NetworkInfo":
        """``body`` is the vendor tag's contents from the OUI (the tag header already removed)."""
        if len(body) < 0x1F + 20 + 1:
            raise ValueError("network info tag is too short")
        comm_id, ident, _pad, attributes, network_id, total, maximum = struct.unpack_from(">IBBHIBB", body, 4)
        size = body[0x1F + 20]
        app = body[0x1F + 21:0x1F + 21 + size]
        expected = hashlib.sha1(body[:0x1F] + bytes(20) + bytes([size]) + app).digest()
        return cls(comm_id, ident, attributes, network_id, total, maximum, bytes(app),
                   bytes(body[18:0x1F]), sha1_ok=expected == bytes(body[0x1F:0x1F + 20]))


@dataclass
class Beacon:
    """A beacon body from its fixed parameters on (what azahar_uds puts in a Beacon WifiPacket)."""
    timestamp: int
    interval: int
    capabilities: int
    tags: list[tuple[int, bytes]]

    @classmethod
    def parse(cls, body: bytes) -> "Beacon":
        if len(body) < 12:
            raise ValueError("beacon body is shorter than its fixed parameters")
        timestamp, interval, capabilities = struct.unpack_from("<QHH", body)
        tags, at = [], 12
        while at + 2 <= len(body):
            tag, length = body[at], body[at + 1]
            tags.append((tag, bytes(body[at + 2:at + 2 + length])))
            at += 2 + length
        return cls(timestamp, interval, capabilities, tags)

    def nintendo(self, kind: int) -> bytes | None:
        """A Nintendo vendor tag's body from its OUI, or None."""
        for tag, body in self.tags:
            if tag == TagId.VENDOR and body[:3] == NINTENDO_OUI and len(body) > 3 and body[3] == kind:
                return body
        return None

    @property
    def network_info(self) -> NetworkInfo | None:
        body = self.nintendo(NintendoTag.NETWORK_INFO)
        return NetworkInfo.parse_tag_body(body) if body else None

    @property
    def encrypted_data(self) -> bytes:
        """Tags 24 and 25 joined, still encrypted (crypto.decrypt_beacon_data opens them)."""
        out = b""
        for kind in (NintendoTag.ENCRYPTED_DATA_0, NintendoTag.ENCRYPTED_DATA_1):
            body = self.nintendo(kind)
            if body:
                out += body[4:]
        return out


@dataclass
class BeaconNode:
    """One node of the decrypted beacon data (BeaconNodeInfo, big-endian)."""
    friend_code_seed: int
    username: str
    network_node_id: int

    def pack(self) -> bytes:
        name = self.username.encode("utf-16-be")[:20].ljust(20, b"\0")
        return struct.pack(">Q", self.friend_code_seed) + name + struct.pack(">H", self.network_node_id)

    @classmethod
    def unpack(cls, data: bytes) -> "BeaconNode":
        seed, = struct.unpack_from(">Q", data)
        node, = struct.unpack_from(">H", data, 28)
        return cls(seed, _utf16be(data[8:28]), node)


def beacon_plain_data(nodes: list[BeaconNode], bitmask: int) -> bytes:
    """The beacon's node data before encryption: MD5 over the rest, u16 BE bitmask, the nodes."""
    rest = struct.pack(">H", bitmask) + b"".join(n.pack() for n in nodes)
    return hashlib.md5(rest).digest() + rest


def parse_beacon_plain_data(data: bytes) -> tuple[bool, int, list[BeaconNode]]:
    """(MD5 valid, bitmask, nodes) of decrypted beacon node data."""
    ok = hashlib.md5(data[16:]).digest() == data[:16]
    bitmask, = struct.unpack_from(">H", data, 16)
    nodes = [BeaconNode.unpack(data[at:at + 0x1E]) for at in range(18, len(data) - 0x1D, 0x1E)]
    return ok, bitmask, nodes


# -------------------------------------------------------------------------------------------------
# Data frames: LLC/SNAP, then SecureData or Nintendo's EAPoL

@dataclass
class SecureData:
    """One SecureData packet. A frame holds a container header (u16 size of what follows the LLC
    header, u16 packet count; retail sends 1, and a count of 0 is ignored by a retail console), then
    that many packets, each: u16 size counting itself, u8 management, u8 channel, u16 sequence,
    u16 destination node, u16 source node, payload [azahar_uds uds_data.h]."""
    channel: int
    sequence: int
    dest_node: int
    src_node: int
    payload: bytes
    is_management: int = 0

    SUB = struct.Struct(">HBBHHH")           # 10 bytes

    def pack_sub(self) -> bytes:
        return self.SUB.pack(self.SUB.size + len(self.payload), self.is_management, self.channel,
                             self.sequence, self.dest_node, self.src_node) + self.payload

    def pack(self) -> bytes:
        return pack_secure_data([self])

    @classmethod
    def unpack(cls, body: bytes) -> "SecureData":
        """The first packet of a SecureData body (after the LLC header)."""
        return unpack_secure_data(body)[0]


def pack_secure_data(packets: list[SecureData]) -> bytes:
    subs = b"".join(p.pack_sub() for p in packets)
    return llc(EtherType.SECURE_DATA) + struct.pack(">HH", len(subs) + 4, len(packets)) + subs


def unpack_secure_data(body: bytes) -> list[SecureData]:
    """Every packet of a SecureData body (after the LLC header)."""
    if len(body) < 4:
        raise ValueError("SecureData body is shorter than its container header")
    size, count = struct.unpack_from(">HH", body)
    end, at, out = min(len(body), size), 4, []
    for _ in range(count):
        if at + SecureData.SUB.size > end:
            break
        sub, mgmt, channel, seq, dest, src = SecureData.SUB.unpack_from(body, at)
        if sub < SecureData.SUB.size or at + sub > end:
            raise ValueError(f"malformed SecureData sub-packet of {sub} bytes at {at}")
        out.append(SecureData(channel, seq, dest, src, bytes(body[at + SecureData.SUB.size:at + sub]), mgmt))
        at += sub
    return out


@dataclass
class EapolNode:
    friend_code_seed: int
    username: str
    network_node_id: int

    def pack(self) -> bytes:
        name = self.username.encode("utf-16-be")[:20].ljust(20, b"\0")
        return struct.pack(">Q", self.friend_code_seed) + name + bytes(4) + struct.pack(">H", self.network_node_id) + bytes(6)

    @classmethod
    def unpack(cls, data: bytes) -> "EapolNode":
        seed, = struct.unpack_from(">Q", data)
        node, = struct.unpack_from(">H", data, 32)
        return cls(seed, _utf16be(data[8:28]), node)


@dataclass
class EapolStart:
    association_id: int
    connection_type: int
    node: EapolNode

    def pack(self) -> bytes:
        # The connection type is a big-endian u16 on the air (0 to 3), not a byte [azahar_uds].
        return llc(EtherType.EAPOL) + struct.pack(">HHH2x", EAPOL_START, self.association_id,
                                                   self.connection_type) + self.node.pack()

    @classmethod
    def unpack(cls, packet: bytes) -> "EapolStart":
        magic, aid, conn = struct.unpack_from(">HHH", packet)
        if magic != EAPOL_START:
            raise ValueError(f"not an EAPoL-Start (magic {magic:#06x})")
        return cls(aid, conn, EapolNode.unpack(packet[8:0x30]))


@dataclass
class EapolLogoff:
    assigned_node_id: int
    client_mac: bytes
    connected_nodes: int
    max_nodes: int
    nodes: list[EapolNode] = field(default_factory=list)
    # Retail hosts send 6 (NetworkStatus ConnectedAsHost); Sun/Moon's joiner leaves at once on 0.
    host_status: int = 6

    def pack(self) -> bytes:
        nodes = b"".join(n.pack() for n in self.nodes[:MAX_NODES]).ljust(MAX_NODES * 0x28, b"\0")
        return (llc(EtherType.EAPOL) + struct.pack(">HxxH", EAPOL_LOGOFF, self.assigned_node_id)
                + bytes(self.client_mac) + bytes(2) + bytes([self.host_status]) + bytes(3)
                + bytes([self.connected_nodes, self.max_nodes]) + bytes(4) + nodes)

    @classmethod
    def unpack(cls, packet: bytes) -> "EapolLogoff":
        magic, assigned = struct.unpack_from(">HxxH", packet)
        if magic != EAPOL_LOGOFF:
            raise ValueError(f"not an EAPoL-Logoff (magic {magic:#06x})")
        nodes = [EapolNode.unpack(packet[0x18 + i * 0x28:0x18 + (i + 1) * 0x28])
                 for i in range(MAX_NODES) if 0x18 + (i + 1) * 0x28 <= len(packet)]
        return cls(assigned, bytes(packet[6:12]), packet[0x12], packet[0x13],
                   [n for n in nodes if n.network_node_id], packet[0x0E])


def llc(ethertype: int) -> bytes:
    return LLC_SNAP + struct.pack(">H", ethertype)


def split_llc(body: bytes) -> tuple[int, bytes]:
    """(EtherType, the rest) of an LLC/SNAP data body."""
    if len(body) < 8 or body[:6] != LLC_SNAP:
        raise ValueError("data body does not start with an LLC/SNAP header")
    return struct.unpack_from(">H", body, 6)[0], body[8:]


# -------------------------------------------------------------------------------------------------
# Authentication and association response bodies

def authentication_body(sequence: int, status: int = 0, algorithm: int = 0) -> bytes:
    return struct.pack("<HHH", algorithm, sequence, status)


def association_response_body(association_id: int, network_id: int, status: int = 0,
                              capabilities: int = 0x0431) -> bytes:
    ssid = f"{network_id:08X}".encode()
    return struct.pack("<HHH", capabilities, status, association_id | 0xC000) + bytes([TagId.SSID, 8]) + ssid


def parse_association_response(body: bytes) -> tuple[int, int, int]:
    """(capabilities, status, association id) of an association response body."""
    caps, status, aid = struct.unpack_from("<HHH", body)
    return caps, status, aid & 0x3FFF


def _utf16be(data: bytes) -> str:
    text = bytes(data).decode("utf-16-be", "replace")
    return text.split("\0", 1)[0]
