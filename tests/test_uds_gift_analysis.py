"""Fragment fields verified from the supplied real-hardware capture."""
import importlib.util
from pathlib import Path
import sys

BASE = Path(__file__).resolve().parents[1]
path = BASE / "pokeldn" / "uds" / "uds_gift_analysis.py"
spec = importlib.util.spec_from_file_location('uds_gift_analysis', path)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def test_krookodile_fragments():
    frames = module.load_fixture(BASE / "tests" / "fixtures" / "krookodile_665.json")
    assert [f.index for f in frames] == [0, 1, 2]
    assert {f.card_id for f in frames} == {665}
    assert all(f.application_size == 200 for f in frames)


def test_bad_frame_rejected():
    try:
        module.parse_fragment(b"1234")
    except ValueError:
        pass
    else:
        assert False


def test_krookodile_compressed_fragment_stream_and_card_comparison():
    frames = module.load_fixture(BASE / 'tests' / 'fixtures' / 'krookodile_665.json')
    stream = module.packed_card_stream(frames)
    assert len(stream) == 346
    assert stream[:4] == bytes.fromhex('10100300')
    full_cards = list((BASE / 'pokeldn' / 'data' / 'gift3ds' / 'wondercards').rglob('*Krookodile (ENG).wc7full'))
    assert len(full_cards) == 1
    report = module.compare_to_full_card(frames, full_cards[0].read_bytes())
    assert report['card_id'] == 665
    assert report['decoded_prefix_length'] >= 0x208
    assert report['different_offsets'] == [0x202, 0x203]
    assert not report['fully_decoded']
    assert not report['complete_card_match']


def test_cycle_rejects_wrong_session_and_duplicate():
    frames = module.load_fixture(BASE / 'tests' / 'fixtures' / 'krookodile_665.json')
    import pytest
    with pytest.raises(ValueError, match='incomplete|duplicate'):
        module.validate_cycle([frames[0], frames[0], frames[2]])
    modified = bytearray(frames[1].packet)
    modified[5] ^= 1
    with pytest.raises(ValueError, match='session'):
        module.validate_cycle([frames[0], module.parse_fragment(bytes(modified)), frames[2]])
