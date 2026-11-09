"""Gen 6/7 local Mystery Gift as a "gift pack": the distributor's beacons, ready to replay.

A Local Distributor never lets a console join. It hosts a UDS network and changes the beacon's
application data every ~0.55 s, cycling through the card's fragments; the game only listens
(docs/3ds_uds.md). Replaying those beacons from the same host MAC, on the same channel and in the
same order, is therefore the whole distribution. The beacons' encrypted node data is keyed to the
host MAC, so the MAC must be kept.

A pack is JSON:
    {"format": "pokeldn-3ds-gift", "version": 1, "name": "...", "host_mac": "60:6b:ff:9b:51:dd",
     "channel": 11, "dwell_ms": 553, "wlan_comm_id": "0x00164810", "beacons": ["<beacon body hex>", ...]}
Each beacon is a body from its fixed parameters on (timestamp, interval, capabilities, elements),
as azahar_uds hands it to its UDP bridge; the radio refreshes the timestamp.
"""

from __future__ import annotations

import json
import statistics
from dataclasses import dataclass, field
from pathlib import Path

from .frames import Beacon

FORMAT = "pokeldn-3ds-gift"


@dataclass
class GiftPack:
    host_mac: bytes
    channel: int
    dwell_ms: int
    beacons: list[bytes]
    name: str = ""
    wlan_comm_id: int = 0
    extra: dict = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps({"format": FORMAT, "version": 1, "name": self.name,
                           "host_mac": ":".join(f"{b:02x}" for b in self.host_mac), "channel": self.channel,
                           "dwell_ms": self.dwell_ms, "wlan_comm_id": f"{self.wlan_comm_id:#010x}",
                           "beacons": [b.hex() for b in self.beacons]}, indent=1)

    @classmethod
    def from_json(cls, text: str) -> "GiftPack":
        data = json.loads(text)
        if data.get("format") != FORMAT:
            raise ValueError("not a pokeldn 3DS gift pack")
        return cls(bytes.fromhex(data["host_mac"].replace(":", "")), int(data["channel"]), int(data["dwell_ms"]),
                   [bytes.fromhex(b) for b in data["beacons"]], data.get("name", ""),
                   int(str(data.get("wlan_comm_id", "0")), 0))

    @classmethod
    def load(cls, path: str | Path) -> "GiftPack":
        return cls.from_json(Path(path).read_text(encoding="utf-8"))

    def save(self, path: str | Path) -> None:
        Path(path).write_text(self.to_json(), encoding="utf-8")

    def mpdu(self, index: int) -> bytes:
        """Beacon ``index`` as an 802.11 frame without FCS (sequence control left 0 for the radio)."""
        return beacon_mpdu(self.host_mac, self.beacons[index])


def beacon_mpdu(host_mac: bytes, body: bytes) -> bytes:
    """Frame control 0x0080, broadcast receiver, transmitter and BSSID the host MAC [azahar_uds
    GeneratePhysicalNintendoBeacon]."""
    return b"\x80\x00\x00\x00" + b"\xff" * 6 + bytes(host_mac) + bytes(host_mac) + b"\x00\x00" + bytes(body)


def from_capture(records: list[dict], side: str = "a", name: str = "") -> GiftPack:
    """A pack from bridge_relay.py capture records: the distinct beacons ``side`` sent, in cycle
    order, and how long each was held."""
    beacons = [r for r in records if r.get("from") == side and r.get("type") == "beacon"]
    if not beacons:
        raise ValueError("the capture has no beacons from that side")
    order: list[bytes] = []          # distinct bodies, keyed without the 8-byte timestamp
    runs: list[tuple[int, float, float]] = []   # (body index, first time, last time)
    for r in beacons:
        body = bytes.fromhex(r["data"])
        key = body[8:]
        if key not in order:
            order.append(key)
        index = order.index(key)
        if runs and runs[-1][0] == index:
            runs[-1] = (index, runs[-1][1], r["t"])
        else:
            runs.append((index, r["t"], r["t"]))
    # A run lasts from its first beacon to the next run's first beacon.
    held = [runs[i + 1][1] - runs[i][1] for i in range(1, len(runs) - 1)]
    dwell_ms = int(round(statistics.median(held) * 1000)) if held else 550
    first = Beacon.parse(bytes(8) + order[0])
    info = first.network_info
    return GiftPack(bytes.fromhex(beacons[0]["src"].replace(":", "")), int(beacons[0]["channel"]), dwell_ms,
                    [bytes(8) + key for key in order], name, info.wlan_comm_id if info else 0)
