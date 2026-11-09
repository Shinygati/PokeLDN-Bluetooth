#!/usr/bin/env python3
"""Record a 3DS local wireless session between two azahar_uds instances (docs/3ds_uds.md).

Start each emulator with its own bridge port, then this relay between them:

    AZAHAR_UDS_BRIDGE=45710  azahar   (instance A: the Gen 6 or Gen 7 Local Distributor)
    AZAHAR_UDS_BRIDGE=45720  azahar   (instance B: Pokemon X/Y/OR/AS/S/M/US/UM)
    python tools/uds/bridge_relay.py --a 45710 --b 45720 --out captures/xy-gift.jsonl

On Windows PowerShell set the variable with  $env:AZAHAR_UDS_BRIDGE = "45710"  before starting
each instance. With --b left out the relay only records what instance A sends.
"""
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from pokeldn.uds.bridge import Relay  # noqa: E402
from pokeldn.uds.decode import describe  # noqa: E402
from pokeldn.uds.bridge import capture_record  # noqa: E402


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--a", type=int, default=45710, help="instance A's AZAHAR_UDS_BRIDGE port (default 45710)")
    parser.add_argument("--b", type=int, default=45720, help="instance B's port (default 45720); 0 records A only")
    parser.add_argument("--out", default=None, help="JSON-lines capture (default captures/uds-<time>.jsonl)")
    parser.add_argument("--quiet-beacons", action="store_true", help="print a beacon only when it changes")
    args = parser.parse_args(argv)

    out = args.out or os.path.join("captures", time.strftime("uds-%Y%m%d-%H%M%S.jsonl"))
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    last_beacon: dict[str, str] = {}

    def show(side, packet):
        record = capture_record(side, packet)
        if args.quiet_beacons and record["type"] == "beacon":
            if last_beacon.get(side) == record["data"][16:]:      # skip the timestamp
                return
            last_beacon[side] = record["data"][16:]
        for line in describe(record):
            print(line, flush=True)

    with open(out, "a", encoding="utf-8") as capture:
        relay = Relay(args.a, args.b or None, capture, show)
        print(f"relay: A sends to 127.0.0.1:{args.a + 1}" +
              (f", B sends to 127.0.0.1:{args.b + 1}" if args.b else ", recording A only") +
              f"; capture {out}. Ctrl+C stops.", flush=True)
        try:
            relay.run()
        except KeyboardInterrupt:
            pass
        finally:
            relay.close()
            print(f"relay: {relay.counts['a']} packets from A, {relay.counts['b']} from B, "
                  f"{relay.counts['bad']} unreadable", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
