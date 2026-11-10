"""Offline tests: no hardware or Bluetooth required."""
import importlib.util
from pathlib import Path

MODULE = Path(__file__).resolve().parents[1] / "pokeldn" / "uds" / "wondercard_library.py"
spec = importlib.util.spec_from_file_location("wondercard_library", MODULE)
import sys
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


def card_bytes(full=False):
    bare = bytearray(0x108)
    bare[0:2] = (665).to_bytes(2, "little")
    bare[2:2+len("Krookodile".encode("utf-16le"))] = "Krookodile".encode("utf-16le")
    if full:
        header = bytearray(0x208)
        header[0] = 0xF
        return bytes(header + bare)
    return bytes(bare)


def test_parse_bare_wc7():
    entry = mod.inspect(card_bytes(), "Krookodile.wc7", lang="ENG")
    assert entry.id == 665 and entry.generation == 7
    assert entry.title == "Krookodile" and entry.games == ()


def test_parse_full_wc7():
    entry = mod.inspect(card_bytes(True), "Krookodile.wc7full", lang="ENG")
    assert len(entry.games) == 4


def test_reject_wrong_length():
    try:
        mod.inspect(b"oops", "bad.wc6")
    except ValueError:
        pass
    else:
        raise AssertionError("Invalid card accepted")


def test_safe_import(tmp_path):
    original = tmp_path / "Krookodile.wc7"
    original.write_bytes(card_bytes())
    one = mod.import_card(original, tmp_path / "custom")
    two = mod.import_card(original, tmp_path / "custom")
    assert one.sha256 == two.sha256
    assert len(list((tmp_path / "custom").glob("*.wc7"))) == 1
