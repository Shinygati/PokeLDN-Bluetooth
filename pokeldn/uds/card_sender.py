"""On-device card generation with distributor material supplied separately by the user."""
import hashlib
from pathlib import Path
from .card_codec import lz10_decode, recover_payload
from .cards import to_full
from .frames import Beacon
from .gift_pack import GiftPack
from .card_selection import DATA, LANGUAGES, selection, resolve_card


def prepare(card_path, game, language, code_path=''):
    from pokeldn.app.paths import DATA as PRIVATE_DATA
    generation, bit, _ = selection(game)
    path = resolve_card(card_path)
    if path.suffix.lower() not in (f'.wc{generation}',f'.wc{generation}full'):
        raise ValueError(f'Select a .wc{generation} or .wc{generation}full for this game')
    data = path.read_bytes()
    if len(data) not in (264,784):
        raise ValueError('Wonder Card must be 264 or 784 bytes')
    if len(data)==784 and data[0]&15 and not data[0]&bit:
        raise ValueError('This Wonder Card does not support the selected game')
    if len(data)==784 and data[0]&15:
        bit &= data[0]&15
    if generation == 6:
        from .gen6_gift import build_pack
        return build_pack(data, version=bit, language=LANGUAGES[language][0])
    saved = Path(PRIVATE_DATA)/'distributor/gen7.code'
    expected = '307029836ed2533275af52236c09fc354ae695fac429d18fe50396f6bf901103'
    if code_path:
        code = Path(code_path).read_bytes()
        if hashlib.sha256(code).hexdigest()!=expected:
            raise ValueError('Unsupported distributor .code. Import the verified decrypted Gen 7 distributor executable')
        saved.parent.mkdir(parents=True,exist_ok=True)
        saved.write_bytes(code)
    if not saved.is_file():
        raise ValueError('One-time setup required: select your decrypted Gen 7 distributor .code in Options, then Start')
    code = saved.read_bytes()
    if hashlib.sha256(code).hexdigest()!=expected:
        raise ValueError('Saved distributor material is invalid; import your .code again')
    public,private = code[0x56b279:0x56b279+126],code[0x56b2f7:0x56b2f7+461]
    template = GiftPack.load(DATA/'gen7-envelope.json')
    apps = sorted((Beacon.parse(b).network_info.application_data for b in template.beacons),key=lambda a:a[23])
    joined = b''.join(a[24:184] for a in apps)
    size = int.from_bytes(joined[4:8],'little')
    header = lz10_decode(recover_payload(joined[8:8+size+8], public))
    full = to_full(data,header,version=bit,language=LANGUAGES[language][0])
    from .direct_gift import build_pack
    return build_pack(full,template,private,public)
