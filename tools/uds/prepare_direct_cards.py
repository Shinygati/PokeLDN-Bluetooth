"""Prepare Gen 7 cards using the user's decrypted distributor executable; export no keys."""
import argparse
import hashlib
from pathlib import Path
from pokeldn.uds.card_codec import recover_payload, lz10_decode
from pokeldn.uds.direct_gift import build_pack
from pokeldn.uds.frames import Beacon
from pokeldn.uds.gift_pack import GiftPack
from pokeldn.uds.prepared_cards import pack_path, PACKS


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--code', type=Path, required=True)
    parser.add_argument('--template', type=Path, required=True)
    parser.add_argument('--cards', type=Path, required=True)
    parser.add_argument('--out', type=Path, default=PACKS)
    args = parser.parse_args()
    code = args.code.read_bytes()
    if hashlib.sha256(code).hexdigest() != '307029836ed2533275af52236c09fc354ae695fac429d18fe50396f6bf901103':
        parser.error('This extractor supports only the verified Gen 7 distributor executable')
    public, private = code[0x56b279:0x56b279+126], code[0x56b2f7:0x56b2f7+461]
    template = GiftPack.load(args.template)
    apps = sorted((Beacon.parse(b).network_info.application_data for b in template.beacons), key=lambda a:a[23])
    joined = b''.join(a[24:184] for a in apps)
    size = int.from_bytes(joined[4:8], 'little')
    header = lz10_decode(recover_payload(joined[8:8+size+8], public))
    paths = sorted(args.cards.rglob('*.wc7*')) if args.cards.is_dir() else [args.cards]
    args.out.mkdir(parents=True, exist_ok=True)
    for index, path in enumerate(paths, 1):
        if path.suffix.lower() not in ('.wc7', '.wc7full'):
            continue
        card = path.read_bytes()
        build_pack(card, template, private, public, header).save(pack_path(card, args.out))
        if index % 100 == 0:
            print('Prepared', index, flush=True)
    print('Prepared broadcast data in', args.out)


if __name__ == '__main__':
    main()
