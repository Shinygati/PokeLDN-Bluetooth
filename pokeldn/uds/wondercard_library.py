"""Gen VI/VII local Wonder Card library: offline catalog and safe custom imports.

This module does NOT claim to generate Nintendo UDS distribution beacons. The
3DS radio still needs a verified card-fragment encoder before broadcast.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import hashlib
import json
import re

CARD_SIZE = 0x108
FULL_SIZE = 0x310
HEADER_SIZE = FULL_SIZE - CARD_SIZE
EXTS = {'.wc6': 6, '.wc6full': 6, '.wc7': 7, '.wc7full': 7}
LANGS = ('ENG', 'JPN', 'FRE', 'GER', 'ITA', 'SPA', 'KOR', 'CHS', 'CHT')

@dataclass(frozen=True)
class Entry:
    generation: int
    id: int
    title: str
    language: str
    path: str
    sha256: str
    size: int
    games: tuple[str, ...]


def inspect(data: bytes, filename: str, *, lang: str = 'UNK') -> Entry:
    ext = Path(filename).suffix.lower()
    if ext not in EXTS:
        raise ValueError('Unsupported format: use .wc6, .wc6full, .wc7 or .wc7full')
    if len(data) not in (CARD_SIZE, FULL_SIZE) or (len(data) == CARD_SIZE) != (not ext.endswith('full')):
        raise ValueError(f'Invalid {ext} length: {len(data)} bytes')
    payload = data[HEADER_SIZE:] if len(data) == FULL_SIZE else data
    cid = int.from_bytes(payload[:2], 'little')
    title = payload[2:0x4A].decode('utf-16-le', errors='replace').split('\0')[0].strip()
    if not title:
        raise ValueError('Wonder Card title is empty')
    generation = EXTS[ext]
    games = ()
    if len(data) == FULL_SIZE:
        mask = data[0] & 15
        names = ('X', 'Y', 'Omega Ruby', 'Alpha Sapphire') if generation == 6 else ('Sun', 'Moon', 'Ultra Sun', 'Ultra Moon')
        games = tuple(name for i, name in enumerate(names) if mask & (1 << i))
    return Entry(generation, cid, title, lang.upper(), filename, hashlib.sha256(data).hexdigest(), len(data), games)


def import_card(src: str | Path, root: str | Path) -> Entry:
    """Install a user-supplied card without replacing a bundled card or executing file content."""
    src = Path(src)
    data = src.read_bytes()
    info = inspect(data, src.name)
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    dest = root / f'{info.generation}-{info.id:04d}-{info.sha256[:16]}{src.suffix.lower()}'
    if not dest.exists():
        dest.write_bytes(data)
    return inspect(data, dest.name)


def catalog(root: str | Path) -> list[dict]:
    entries = []
    root = Path(root)
    for p in sorted(root.rglob('*')):
        if p.is_file() and p.suffix.lower() in EXTS:
            try:
                lang = next((part.upper() for part in p.parts if part.upper() in LANGS), 'UNK')
                e = inspect(p.read_bytes(), p.relative_to(root).as_posix(), lang=lang)
                entries.append(e.__dict__)
            except (ValueError, OSError):
                pass
    return entries


def save_manifest(root: str | Path) -> Path:
    root = Path(root)
    dest = root / 'wondercard-manifest.json'
    dest.write_text(json.dumps({'format': 'pokeldn-wondercards', 'version': 1, 'cards': catalog(root)}, ensure_ascii=False, indent=2), encoding='utf-8')
    return dest
