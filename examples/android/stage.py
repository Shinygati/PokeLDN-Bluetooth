from pathlib import Path
import os
import sys
import shutil
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
DEST = HERE / 'staged'
if DEST.exists():
    assert DEST.resolve().parent == HERE.resolve() and DEST.name == 'staged'
    shutil.rmtree(DEST)
DEST.mkdir()
packages = ('pokeldn', 'bin', 'config', 'gui', 'docs', 'vendor/LDN/ldn')
filenames = []
for package in packages:
    for candidate in (ROOT / package).rglob('*'):
        if candidate.is_file() and '__pycache__' not in candidate.parts and candidate.suffix not in ('.pyc', '.code', '.jks', '.keystore', '.keys') and 'prepared' not in candidate.parts:
            filenames.append(candidate.relative_to(ROOT).as_posix())
for filename in filenames:
    if not filename:
        continue
    relative = Path(filename)
    if relative.name == 'prod.keys' or relative.suffix in ('.keys', '.pk3', '.ek3', '.sav', '.gba'):
        raise ValueError('Private input cannot be staged: ' + filename)
    target = DEST / (Path('ldn') / relative.relative_to('vendor/LDN/ldn')
                     if relative.is_relative_to('vendor/LDN/ldn') else relative)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / relative, target)
# Chaquopy extracts packages to real files and runpy runs only real files: the launchers become one.
(DEST / 'bin' / '__init__.py').write_text('')
# The firmware images the release build writes (gui/board.py); absent from a fresh checkout.
for image in (ROOT / 'gui' / 'firmware').glob('*.bin'):
    (DEST / 'gui' / 'firmware').mkdir(parents=True, exist_ok=True)
    shutil.copy2(image, DEST / 'gui' / 'firmware' / image.name)
# Unicorn's Python binding; its library is built for Android by build_native.py.
import unicorn
binding = Path(unicorn.__file__).parent
shutil.copytree(binding, DEST / 'unicorn', ignore=shutil.ignore_patterns('lib', 'include', '__pycache__'))
for filename in ('test_esp32.py', 'test_host_end_to_end.py'):
    shutil.copy2(ROOT / 'tests' / filename, DEST / ('android_' + filename))
# The Nintendo DS and Nintendo 3DS Games categories are packaged with the APK, no user plugins folder.
shutil.copytree(HERE / 'nds_plugin', DEST / 'pokeldn' / 'nds_plugin', dirs_exist_ok=True)
shutil.copytree(HERE / 'n3ds_plugin', DEST / 'pokeldn' / 'n3ds_plugin', dirs_exist_ok=True)
print('Staged tracked repository code and package data:', DEST)
prepared = os.environ.get('POKELDN_3DS_PREPARED')
if prepared:
    source = Path(prepared)
    target = DEST / 'pokeldn/data/gift3ds/prepared'
    target.mkdir(parents=True, exist_ok=True)
    for pack in source.glob('*.gift.json'):
        from pokeldn.uds.gift_pack import GiftPack
        GiftPack.load(pack)  # Only validated beacon packs are staged, never key files.
        shutil.copy2(pack, target / pack.name)
