#!/usr/bin/env python3
"""Extract .wc6/.wc6full/.wc7/.wc7full from EventsGallery ZIP into PokeLDN.
Usage: python tools/uds/build_wondercard_library.py EventsGallery.zip
"""
from pathlib import Path
import argparse
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from pokeldn.uds.wondercard_library import inspect, save_manifest  # noqa: E402


def build(archive: Path, out: Path) -> tuple[int, int]:
    total = bad = 0
    with zipfile.ZipFile(archive) as z:
        for item in z.infolist():
            if item.is_dir() or Path(item.filename).suffix.lower() not in ('.wc6', '.wc6full', '.wc7', '.wc7full'):
                continue
            # Limit size BEFORE reading or expanding potentially untrusted ZIP entries.
            if item.file_size not in (0x108, 0x310):
                bad += 1
                continue
            rel_parts = Path(item.filename.replace('\\', '/')).parts
            language = next((p.upper() for p in rel_parts if p.upper() in ('ENG','JPN','FRE','GER','ITA','SPA','KOR','CHS','CHT')), 'UNK')
            data = z.read(item)
            try:
                card = inspect(data, item.filename, lang=language)
            except ValueError:
                bad += 1
                continue
            target = out / f'gen{card.generation}' / language / f'{card.id:04d}_{card.sha256[:16]}{Path(item.filename).suffix.lower()}'
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists():
                target.write_bytes(data)
            total += 1
    save_manifest(out)
    return total, bad


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('archive', type=Path)
    p.add_argument('--out', type=Path, default=ROOT / 'pokeldn/data/gift3ds/wondercards')
    a = p.parse_args()
    print('Accepted / rejected:', *build(a.archive, a.out))
