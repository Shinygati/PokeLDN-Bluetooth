"""Gen 6/7 full Wonder Cards and the distributor card tool."""

import os
import sys

import pytest

from pokeldn.uds.cards import (CARD_SIZE, FULL_SIZE, HEADER_SIZE, card_id, crc16_ccitt, fix_crc, full_crc,
                               is_full_card, title, to_full)

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools", "uds"))
import distributor_card  # noqa: E402


def test_crc16_ccitt_false_check_value():
    # The catalogued check value of CRC-16/CCITT-FALSE. The same formula reproduced the stored CRC of
    # all 24 released .wc6full/.wc7full cards checked from Project Pokemon's EventsGallery.
    assert crc16_ccitt(b"123456789") == 0x29B1


def _card(cid=566, name="The Mythical Pokémon Genesect", versions=15):
    full = bytearray(FULL_SIZE)
    full[0] = versions
    full[HEADER_SIZE:HEADER_SIZE + 2] = cid.to_bytes(2, "little")
    full[HEADER_SIZE + 2:HEADER_SIZE + 2 + len(name) * 2] = name.encode("utf-16-le")
    return fix_crc(bytes(full))


def test_full_card_round_trip():
    full = _card()
    assert is_full_card(full) and card_id(full) == 566 and title(full) == "The Mythical Pokémon Genesect"
    assert int.from_bytes(full[0x202:0x204], "little") == full_crc(full)
    broken = bytearray(full)
    broken[0x300] ^= 1
    assert not is_full_card(bytes(broken))


def test_bare_card_takes_the_template_header():
    template = _card(1, "Old", versions=3)
    bare = _card(570, "Wow! It's Zapdos!")[HEADER_SIZE:]
    assert len(bare) == CARD_SIZE
    full = to_full(bare, template, language=2)
    assert is_full_card(full) and full[1:0x1FF] == template[1:0x1FF]
    assert full[0x1FF] == 2 and card_id(full) == 570 and full[0] == 3
    with pytest.raises(ValueError):
        to_full(b"\0" * 10, template)


def test_tool_swaps_the_distributor_card(tmp_path, capsys):
    user = tmp_path / "user"
    extdata = user / "sdmc" / "Nintendo 3DS" / ("0" * 32) / ("0" * 32) / "extdata" / "00000000" / "00000ec5" / "user" / "hashin"
    extdata.mkdir(parents=True)
    (extdata / "1").write_bytes(_card(11, "A Special Garchomp!", versions=3))
    (extdata / "other.bin").write_bytes(b"\0" * FULL_SIZE)            # right size, wrong CRC: ignored
    new = tmp_path / "zapdos.wc6full"
    new.write_bytes(_card(570, "Wow! It's Zapdos!"))

    assert distributor_card.main(["--dir", str(user), "--list"]) == 0
    assert "A Special Garchomp!" in capsys.readouterr().out
    assert distributor_card.main(["--dir", str(user), "--card", str(new)]) == 0
    installed = (extdata / "1").read_bytes()
    assert card_id(installed) == 570 and is_full_card(installed)
    backups = [p for p in os.listdir(extdata) if p.startswith("1.bak-")]
    assert len(backups) == 1 and card_id((extdata / backups[0]).read_bytes()) == 11
