#!/usr/bin/env python3
"""Print a bridge_relay.py capture as a timeline, and save each side's SecureData payloads.

    python tools/uds/capture_dump.py captures/xy-gift.jsonl
    python tools/uds/capture_dump.py captures/xy-gift.jsonl --payloads captures/xy-gift-payloads

Repeated beacons are folded into one line with a count. With --payloads every SecureData payload is
written as <n>-<side>-ch<channel>.bin, in order, for side-by-side diffing of two captures.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from pokeldn.uds.decode import describe  # noqa: E402
from pokeldn.uds.frames import split_llc, unpack_secure_data, EtherType  # noqa: E402


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("capture")
    parser.add_argument("--payloads", help="folder for the SecureData payloads")
    args = parser.parse_args(argv)

    if args.payloads:
        os.makedirs(args.payloads, exist_ok=True)
    start, beacon_key, beacon_count, saved = None, None, 0, 0

    def flush_beacons():
        nonlocal beacon_count
        if beacon_count > 1:
            print(f"          ... the same beacon {beacon_count - 1} more times")
        beacon_count = 0

    with open(args.capture, encoding="utf-8") as lines:
        for line in lines:
            if not line.strip():
                continue
            record = json.loads(line)
            start = record["t"] if start is None else start
            stamp = f"{record['t'] - start:9.3f}"
            if record["type"] == "beacon":
                key = (record["from"], record["data"][16:])
                if key == beacon_key:
                    beacon_count += 1
                    continue
                flush_beacons()
                beacon_key, beacon_count = key, 1
            else:
                flush_beacons()
                beacon_key = None
            for text in describe(record):
                print(stamp, text)
            if args.payloads and record["type"] == "data":
                try:
                    ethertype, body = split_llc(bytes.fromhex(record["data"]))
                    packets = unpack_secure_data(body) if ethertype == EtherType.SECURE_DATA else []
                except ValueError:
                    packets = []
                for packet in packets:
                    saved += 1
                    name = f"{saved:04d}-{record['from']}-ch{packet.channel}.bin"
                    with open(os.path.join(args.payloads, name), "wb") as out:
                        out.write(packet.payload)
    flush_beacons()
    if args.payloads:
        print(f"{saved} payloads written to {args.payloads}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
