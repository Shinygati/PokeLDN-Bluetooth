"""azahar_uds's plaintext UDP bridge, and a relay that records what two emulators say to each other.

Gr3nSkyDragon's azahar_uds (``src/core/hle/service/nwm/uds_bridge.h``) hands every UDS packet it
sends to 127.0.0.1 and takes packets back the same way, unencrypted, when ``AZAHAR_UDS_BRIDGE`` is
set: ``AZAHAR_UDS_BRIDGE=N`` makes it listen on N and send to N + 1. One datagram is one packet:

    0..3   'U' 'D' 'S' 'B'
    4      version (1)
    5      WifiPacket::PacketType
    6      channel
    7      reserved (0)
    8..13  transmitter MAC
    14..19 destination MAC
    20..   WifiPacket::data (a management body, or a data frame's LLC/SNAP body)

``Relay`` sits between two instances (say the Local Distributor on port A and Pokemon X on port B):
it listens on A + 1 and B + 1, forwards each side's packets to the other's listen port and writes
each one to a JSON-lines capture (``tools/uds/bridge_relay.py``).
"""

from __future__ import annotations

import json
import select
import socket
import time
from dataclasses import dataclass
from enum import IntEnum
from typing import Callable, TextIO

MAGIC = b"UDSB"
VERSION = 1
HEADER_SIZE = 20
LOOPBACK = "127.0.0.1"


class PacketType(IntEnum):
    BEACON = 0
    DATA = 1
    AUTHENTICATION = 2
    ASSOCIATION_RESPONSE = 3
    DEAUTHENTICATION = 4
    NODE_MAP = 5


@dataclass
class WifiPacket:
    type: int
    channel: int
    transmitter: bytes
    destination: bytes
    data: bytes

    def pack(self) -> bytes:
        return (MAGIC + bytes([VERSION, self.type, self.channel, 0]) + bytes(self.transmitter)
                + bytes(self.destination) + bytes(self.data))

    @classmethod
    def unpack(cls, datagram: bytes) -> "WifiPacket":
        if len(datagram) < HEADER_SIZE or datagram[:4] != MAGIC or datagram[4] != VERSION:
            raise ValueError("not a UDS bridge datagram")
        return cls(datagram[5], datagram[6], bytes(datagram[8:14]), bytes(datagram[14:20]), bytes(datagram[20:]))


def mac_text(mac: bytes) -> str:
    return ":".join(f"{b:02x}" for b in mac)


def capture_record(side: str, packet: WifiPacket, t: float | None = None) -> dict:
    """One capture line: which instance sent it, and the packet."""
    try:
        kind = PacketType(packet.type).name.lower()
    except ValueError:
        kind = str(packet.type)
    return {"t": round(time.time() if t is None else t, 6), "from": side, "type": kind,
            "channel": packet.channel, "src": mac_text(packet.transmitter), "dst": mac_text(packet.destination),
            "data": packet.data.hex()}


class Relay:
    """Forward between two bridge instances, recording every packet.

    ``port_a``/``port_b`` are the instances' AZAHAR_UDS_BRIDGE values (their listen ports). A side
    whose port is None is only recorded: nothing is forwarded to it.
    """

    def __init__(self, port_a: int, port_b: int | None, capture: TextIO | None,
                 on_packet: Callable[[str, WifiPacket], None] | None = None):
        self.ports = {"a": port_a, "b": port_b}
        self.capture = capture
        self.on_packet = on_packet
        self.sockets: dict[str, socket.socket] = {}
        self.counts = {"a": 0, "b": 0, "bad": 0}
        for side, port in self.ports.items():
            if port is None:
                continue
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.bind((LOOPBACK, port + 1))               # where that instance sends
            sock.setblocking(False)
            self.sockets[side] = sock

    def close(self) -> None:
        for sock in self.sockets.values():
            sock.close()

    def poll(self, timeout: float = 0.2) -> int:
        """Handle what has arrived; returns the number of packets."""
        ready, _, _ = select.select(list(self.sockets.values()), [], [], timeout)
        handled = 0
        for sock in ready:
            side = next(s for s, k in self.sockets.items() if k is sock)
            other = "b" if side == "a" else "a"
            while True:
                try:
                    datagram, _ = sock.recvfrom(65535)
                except (BlockingIOError, InterruptedError):
                    break
                except ConnectionResetError:              # Windows: the peer's port was closed
                    continue
                try:
                    packet = WifiPacket.unpack(datagram)
                except ValueError:
                    self.counts["bad"] += 1
                    continue
                self.counts[side] += 1
                handled += 1
                if self.capture:
                    self.capture.write(json.dumps(capture_record(side, packet)) + "\n")
                    self.capture.flush()
                if self.on_packet:
                    self.on_packet(side, packet)
                if self.ports[other] is not None:
                    # Send from the other side's socket, as if that instance's peer were local.
                    self.sockets[other].sendto(datagram, (LOOPBACK, self.ports[other]))
        return handled

    def run(self, stop: Callable[[], bool] = lambda: False) -> None:
        while not stop():
            self.poll()
