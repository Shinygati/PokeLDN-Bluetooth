from pathlib import Path
import hashlib
import pytest
from pokeldn.uds.gen6_gift import unpack_card, build_pack
from pokeldn.uds.gift_pack import GiftPack
from pokeldn.uds.card_selection import GAMES, matching_cards
from pokeldn.uds.card_sender import prepare
from pokeldn.uds.cards import HEADER_SIZE, is_full_card
from pokeldn.uds.card_selection import DATA, GAME_FAMILIES, LANGUAGES, bundled_value, resolve_card
from pokeldn.uds.portable3ds import build_image
import struct
import zlib


@pytest.mark.parametrize('name,digest',[
 ('mewtwo','54cd4be0636d1d9e6c2b3b956fc3b3403e826f215da54f5e25dfc5ca30697fef'),
 ('machamp','4d10d26f011608c3b1bac024bee88d7bab4a64e3bd42d495ac856ae9ab09fca8')])
def test_real_capture_and_new_generation(name,digest):
    original=GiftPack.load(Path(__file__).parent/f'fixtures/gen6-{name}.json')
    full=unpack_card(original)
    assert hashlib.sha256(full).hexdigest()==digest
    generated=build_pack(full)
    assert unpack_card(generated)==full


def test_bad_checksum_rejected():
    pack=GiftPack.load(Path(__file__).parent/'fixtures/gen6-mewtwo.json')
    body=bytearray(pack.beacons[0]);offset=body.index(bytes.fromhex('001f3215'))+52+40;body[offset]^=1;pack.beacons[0]=bytes(body)
    with pytest.raises(ValueError):unpack_card(pack)


def test_game_language_filters():
    for game,(generation,_,name) in GAMES.items():
        for card in matching_cards(game,'ENG'):
            assert card['generation']==generation and card['language']=='ENG'
            if card['games']:assert name in card['games']


@pytest.mark.parametrize('game,version',[('x',1),('y',2),('or',4),('as',8)])
def test_imported_wc6_to_firmware_image_without_distributor_setup(tmp_path, monkeypatch, game, version):
    from pokeldn.app import paths
    monkeypatch.setattr(paths, 'DATA', tmp_path/'private')
    captured = GiftPack.load(Path(__file__).parent/'fixtures/gen6-machamp.json')
    full = unpack_card(captured)
    imported = tmp_path/'machamp.wc6'
    imported.write_bytes(full[HEADER_SIZE:])
    pack = prepare(imported, game, 'ENG')
    decoded = unpack_card(pack)
    assert decoded[HEADER_SIZE:] == full[HEADER_SIZE:]
    assert decoded[0] == version and decoded[0x1ff] == 2 and is_full_card(decoded)
    image = build_image(pack)
    assert image[:6] == b'PKSA\x01\x03'
    assert image[124] == len(pack.beacons)
    assert struct.unpack_from('<I', image, len(image)-4)[0] == zlib.crc32(image[:-4])
    assert not (tmp_path/'private/distributor/gen7.code').exists()


def test_gen6_rejects_a_gen7_file(tmp_path):
    path = tmp_path/'wrong.wc7'
    path.write_bytes(bytes(264))
    with pytest.raises(ValueError, match='wc6'):
        prepare(path, 'x', 'ENG')


def test_android_bundled_path_from_previous_apk():
    card = next(c for c in matching_cards('xy','ENG') if 'Garchomp' in c['title'])
    value = bundled_value(card)
    assert '\\' not in value and not value.startswith(str(DATA))
    old = '/data/data/org.pokeldn.usbprobe/files/chaquopy/AssetFinder/app/pokeldn/data/gift3ds/wondercards/' + card['path'].replace('/','\\')
    assert resolve_card(old) == resolve_card(value)
    pack = prepare(old, 'xy', 'ENG')
    assert unpack_card(pack)[HEADER_SIZE:] == resolve_card(value).read_bytes()[HEADER_SIZE:]


@pytest.mark.parametrize('family,left,right',[('xy','x','y'),('oras','or','as'),('sm','s','m'),('usum','us','um')])
def test_pair_lists_are_union_of_both_games(family,left,right):
    for language in LANGUAGES:
        paths = lambda game: {c['path'] for c in matching_cards(game,language)}
        assert paths(family) == paths(left) | paths(right)


def test_group_does_not_widen_exclusive_card_compatibility(tmp_path):
    from pokeldn.uds.cards import fix_crc
    full = bytearray(unpack_card(GiftPack.load(Path(__file__).parent/'fixtures/gen6-machamp.json')))
    full[0] = 1
    path = tmp_path/'exclusive.wc6full'
    path.write_bytes(fix_crc(full))
    assert unpack_card(prepare(path,'xy','ENG'))[0] == 1
    with pytest.raises(ValueError, match='does not support'):
        prepare(path,'oras','ENG')


def test_group_fields_only_show_selected_pair():
    from examples.android.n3ds_plugin import plugin
    from pokeldn.app.command import applies
    class API:
        def add_game(self,game,icon=''): self.game=game
    api=API();plugin.register(api);tool=api.game.tools[0]
    assert dict(tool.fields[0].choices).keys() == GAME_FAMILIES.keys()
    for family,(generation,_,_) in GAME_FAMILIES.items():
        values={'--game-family':family,'--language-'+family:'ENG'}
        active=[f for f in tool.fields if applies(f,tool,values)]
        assert len([f for f in active if f.key.startswith('--card-')])==1
        assert len([f for f in active if f.key=='--distributor-code'])==(generation==7)
