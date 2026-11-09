#!/usr/bin/env python3
"""Send a Gen 6/7 local Mystery Gift from the ESP32 alone, by replaying a recorded distributor.

1. Record the distributor once (run_distributor.ps1 -Record), which writes captures\\*.jsonl.
2. Turn the recording into a gift pack (a small JSON file you can keep and reuse):
       python tools/uds/gift_replay.py pack captures/distributor-....jsonl --name "Krookodile (US)" --out gifts/krookodile.json
3. With azahar_uds CLOSED (it must not hold the board's port), send it:
       python tools/uds/gift_replay.py send gifts/krookodile.json --port COM8
   then on the 3DS: Mystery Gift -> Receive Gift -> Get via Local Wireless. Ctrl+C stops.

The board needs VC-Adapter's esp32-uds-bridge firmware (the one azahar_uds uses). The beacons are
sent exactly as recorded: the same host MAC, channel and order, each held as long as the
distributor held it.
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from pokeldn.uds.gift_pack import GiftPack, from_capture  # noqa: E402


def cmd_pack(args) -> int:
    with open(args.capture, encoding="utf-8") as f:
        records = [json.loads(line) for line in f if line.strip()]
    pack = from_capture(records, name=args.name or os.path.splitext(os.path.basename(args.capture))[0])
    out = args.out or os.path.splitext(args.capture)[0] + ".gift.json"
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    pack.save(out)
    print(f"{out}: {len(pack.beacons)} beacons, {pack.dwell_ms} ms each, channel {pack.channel}, "
          f"host {':'.join(f'{b:02x}' for b in pack.host_mac)}, comm id {pack.wlan_comm_id:#010x}")
    return 0


def cmd_send(args) -> int:
    from pokeldn.uds.esp32_bridge import Bridge
    pack = GiftPack.load(args.pack)
    dwell = (args.dwell_ms or pack.dwell_ms) / 1000
    bridge = Bridge(args.port)
    bridge.open()
    result = bridge.start(pack.channel, pack.host_mac)
    if result != 0:
        print(f"START failed: esp_err {result:#x}")
        return 1
    print(f"Sending {pack.name or args.pack} on channel {pack.channel}: {len(pack.beacons)} beacons, "
          f"{int(dwell * 1000)} ms each. On the 3DS: Mystery Gift -> Receive Gift -> Get via Local Wireless. "
          "Ctrl+C stops.", flush=True)
    cycles = 0
    try:
        while True:
            for index in range(len(pack.beacons)):
                result = bridge.set_beacon(pack.mpdu(index))
                if result != 0:
                    print(f"SET_BEACON failed: esp_err {result:#x}")
                    return 1
                end = time.monotonic() + dwell
                while time.monotonic() < end:
                    bridge.read_frames()             # keep the board's log and stats drained
                    time.sleep(0.01)
            cycles += 1
            if cycles % 20 == 0:
                print(f"  {cycles} cycles sent", flush=True)
    except KeyboardInterrupt:
        pass
    finally:
        try:
            bridge.stop()
        except Exception:
            pass
        bridge.close()
        print("Stopped.")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("pack", help="make a gift pack from a bridge_relay.py recording")
    p.add_argument("capture")
    p.add_argument("--name", help="a label for the pack")
    p.add_argument("--out", help="output .json (default: next to the capture)")
    p.set_defaults(func=cmd_pack)
    s = sub.add_parser("send", help="replay a gift pack from an esp32-uds-bridge board")
    s.add_argument("pack")
    s.add_argument("--port", required=True, help="the board's serial port, e.g. COM8")
    s.add_argument("--dwell-ms", type=int, help="override how long each beacon is held")
    s.set_defaults(func=cmd_send)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
