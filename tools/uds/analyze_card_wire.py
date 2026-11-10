#!/usr/bin/env python3
"""Compare a real distributor fragment fixture to its original full Wonder Card.

Usage: python tools/uds/analyze_card_wire.py tests/fixtures/krookodile_665.json card.wc7full
No radio connection or distributor required. Not a broadcast utility.
"""
import argparse
import json
from pathlib import Path
from pokeldn.uds.uds_gift_analysis import load_fixture, compare_to_full_card


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('fixture', type=Path)
    p.add_argument('full_card', type=Path)
    args = p.parse_args()
    report = compare_to_full_card(load_fixture(args.fixture), args.full_card.read_bytes())
    print(json.dumps(report, indent=2))
    if not report['fully_decoded']:
        print('NOTE: only a partially decoded stream; not suitable for broadcasting.')


if __name__ == '__main__':
    main()
