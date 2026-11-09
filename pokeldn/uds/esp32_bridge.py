"""Host side of VC-Adapter's esp32-uds-bridge firmware (firmware/esp32-uds-bridge in Gr3nSkyDragon/VC-Adapter).

One frame: | version 1 | type | seq | flags | u16 LE length | payload | CRC-32 (zlib) LE |, COBS
encoded and ended by one 0x00 byte (main/uds_wire.c). The board is a raw radio: START brings it up
on a channel with a MAC, SET_BEACON hands it a beacon MPDU that it sends every 102.4 ms with a fresh
timestamp and sequence number.
"""

from __future__ import annotations

import struct
import time
import zlib

VERSION = 1
HELLO, START, STOP, SET_CHANNEL, TX_FRAME, SET_BEACON = 0x01, 0x02, 0x03, 0x04, 0x06, 0x07
HELLO_ACK, STATUS, RX, LOG, STATS, PONG, TXDONE = 0x81, 0x82, 0x83, 0x84, 0x85, 0x86, 0x87


def cobs_encode(data: bytes) -> bytes:
    out, block = bytearray(), bytearray()
    for byte in data:
        if byte == 0:
            out += bytes([len(block) + 1]) + block
            block = bytearray()
        else:
            block.append(byte)
            if len(block) == 254:
                out += b"\xff" + block
                block = bytearray()
    out += bytes([len(block) + 1]) + block
    return bytes(out)


def cobs_decode(data: bytes) -> bytes:
    """The firmware's cobs_decode: each code byte gives code - 1 data bytes, then a zero unless it
    was 0xFF or the input ends."""
    out, i = bytearray(), 0
    while i < len(data):
        code = data[i]
        i += 1
        if code == 0 or i + code - 1 > len(data):
            raise ValueError("bad COBS")
        out += data[i:i + code - 1]
        i += code - 1
        if code != 0xFF and i < len(data):
            out.append(0)
    return bytes(out)


def encode(msg_type: int, seq: int, payload: bytes = b"", flags: int = 0) -> bytes:
    raw = struct.pack("<BBBBH", VERSION, msg_type, seq & 0xFF, flags, len(payload)) + payload
    raw += struct.pack("<I", zlib.crc32(raw) & 0xFFFFFFFF)
    return cobs_encode(raw) + b"\0"


def decode(frame: bytes) -> tuple[int, int, bytes] | None:
    """(type, seq, payload) of one COBS frame without its delimiter, or None if it is damaged."""
    try:
        raw = cobs_decode(frame)
    except ValueError:
        return None
    if len(raw) < 10 or raw[0] != VERSION:
        return None
    if struct.unpack_from("<I", raw, len(raw) - 4)[0] != zlib.crc32(raw[:-4]) & 0xFFFFFFFF:
        return None
    length, = struct.unpack_from("<H", raw, 4)
    return raw[1], raw[2], raw[6:6 + length]


class Bridge:
    """A board on a serial port (pyserial)."""

    def __init__(self, port: str, log=print):
        import serial                       # pyserial, in requirements.txt
        self._serial_mod = serial
        self.port_name = port
        self.log = log
        self.port = None
        self.seq = 0
        self.pending = bytearray()
        self.firmware = ""

    def open(self, timeout: float = 20.0) -> None:
        """Open the port and say HELLO until the board answers. A board in GB-Link's Switch mode
        restarts into 3DS mode on HELLO, so its port can vanish and come back meanwhile."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                if self.port is None:
                    self.port = self._serial_mod.Serial(self.port_name, 115200, timeout=0.05)
                self.port.write(b"\0" + encode(HELLO, self._next_seq()))
                reply = self.wait_for(HELLO_ACK, 1.0)
                if reply is not None:
                    proto, major, minor = reply[0], reply[1], reply[2]
                    self.firmware = f"{major}.{minor}"
                    self.log(f"board: protocol {proto}, firmware {self.firmware}")
                    return
            except (OSError, self._serial_mod.SerialException):
                self.close()
                time.sleep(0.5)
        raise TimeoutError(f"no answer from an esp32-uds-bridge board on {self.port_name}")

    def close(self) -> None:
        if self.port is not None:
            try:
                self.port.close()
            except Exception:
                pass
            self.port = None

    def _next_seq(self) -> int:
        self.seq = (self.seq + 1) & 0xFF
        return self.seq

    def command(self, msg_type: int, payload: bytes = b"", timeout: float = 2.0) -> int:
        """Send a command and return the board's esp_err_t from its STATUS."""
        seq = self._next_seq()
        self.port.write(encode(msg_type, seq, payload))
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            for kind, rseq, body in self.read_frames():
                if kind == STATUS and rseq == seq and len(body) >= 5:
                    return struct.unpack_from("<i", body, 1)[0]
        raise TimeoutError(f"no STATUS for command {msg_type:#04x}")

    def wait_for(self, msg_type: int, timeout: float) -> bytes | None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            for kind, _seq, body in self.read_frames():
                if kind == msg_type:
                    return body
        return None

    def read_frames(self):
        data = self.port.read(4096)
        if data:
            self.pending += data
        frames = []
        while b"\0" in self.pending:
            raw, _, rest = self.pending.partition(b"\0")
            self.pending = bytearray(rest)
            if raw:
                frame = decode(bytes(raw))
                if frame is None:
                    continue
                if frame[0] == LOG:
                    self.log("board log: " + frame[2].decode("utf-8", "replace").rstrip())
                    continue
                frames.append(frame)
        return frames

    def start(self, channel: int, mac: bytes) -> int:
        return self.command(START, bytes([channel]) + bytes(mac))

    def set_beacon(self, mpdu: bytes) -> int:
        return self.command(SET_BEACON, mpdu)

    def stop(self) -> int:
        self.command(SET_BEACON, b"")
        return self.command(STOP)
