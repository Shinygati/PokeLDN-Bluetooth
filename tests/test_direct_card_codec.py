import hashlib
import json
from pathlib import Path
import pytest
from Crypto.PublicKey import RSA
from pokeldn.uds.card_codec import cmc_encode, cmc_decode, lz10_encode, lz10_decode, sign_payload, recover_payload
from pokeldn.uds.direct_gift import packet_crc

PUBLIC = bytes.fromhex('307c300d06092a864886f70d0101010500036b003068026100b756e1dcd8cece78e148107b1bac115fdb17de843453cab7d4e6df8dd21f5a3d17b4477a8a531d97d57eb558f0d58a4af5bfaddda4a0bc1dc22ff87576c7268b942819d4c83f78e1ee92d406662f4e68471e4de833e5126c32eb63a868345d1d0203010001')


def test_real_capture_recovery_and_outer_checksums():
    fixture = json.loads((Path(__file__).parent / 'fixtures/krookodile_665.json').read_text())
    frames = [bytes.fromhex(p) for p in fixture['payloads_hex']]
    assert all(packet_crc(p[2:]) == int.from_bytes(p[:2], 'little') for p in frames)
    joined = b''.join(p[24:184] for p in frames)
    size = int.from_bytes(joined[4:8], 'little')
    packed = recover_payload(joined[8:8+size+8], PUBLIC)
    full = lz10_decode(packed)
    assert len(full) == 784
    assert hashlib.sha256(full).hexdigest() == 'f956211268b8b5fb94bb454c06ce2f312022e8df284defff3ae7f95d9cfd473b'
    assert lz10_decode(lz10_encode(full)) == full
    damaged = bytearray(joined[8:8+size+8]); damaged[0] ^= 1
    with pytest.raises(ValueError):
        recover_payload(bytes(damaged), PUBLIC)


def test_new_signatures_and_cmc_roundtrip():
    key = RSA.generate(1024)
    public = key.public_key().export_key(format='DER')
    plain = bytes(range(256)) + bytes(88)
    signed = sign_payload(plain, key.export_key(format='DER'), public)
    assert len(signed) == len(plain) + 8
    assert recover_payload(signed, public) == plain
    data = bytes(range(96))
    assert cmc_decode(cmc_encode(data, bytes(16)), bytes(16)) == data


@pytest.mark.parametrize('bad', [b'', b'\x10\x10\x03\0', b'\x10\x03\0\0\x80\0\0'])
def test_malformed_lz10(bad):
    with pytest.raises(ValueError):
        lz10_decode(bad)
