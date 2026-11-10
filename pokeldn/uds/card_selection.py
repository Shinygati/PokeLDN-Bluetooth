"""Shared game/language filters for bundled and imported WC6/WC7 cards."""
import json
import re
from pathlib import Path, PurePosixPath

DATA = Path(__file__).parents[1] / 'data/gift3ds'
GAMES = {'x': (6,1,'X'), 'y': (6,2,'Y'), 'or': (6,4,'Omega Ruby'), 'as': (6,8,'Alpha Sapphire'),
         's': (7,1,'Sun'), 'm': (7,2,'Moon'), 'us': (7,4,'Ultra Sun'), 'um': (7,8,'Ultra Moon')}
GAME_FAMILIES = {'xy':(6,3,'X / Y'), 'oras':(6,12,'Omega Ruby / Alpha Sapphire'),
                 'sm':(7,3,'Sun / Moon'), 'usum':(7,12,'Ultra Sun / Ultra Moon')}
LANGUAGES = {'JPN':(1,'Japanese'),'ENG':(2,'English'),'FRE':(3,'French'),'ITA':(4,'Italian'),
             'GER':(5,'German'),'SPA':(7,'Spanish'),'KOR':(8,'Korean'),'CHS':(9,'Simplified Chinese'),'CHT':(10,'Traditional Chinese')}
TOKENS = {'X':1,'Y':2,'XY':3,'OR':4,'AS':8,'ORAS':12,'XYORAS':15,
          'S':1,'M':2,'SM':3,'US':4,'UM':8,'USUM':12,'SMUSUM':15,'SUS':5,'MUM':10}


def mask(card):
    if card['games']:
        generation = card['generation']
        return sum(bit for gen,bit,name in GAMES.values() if gen == generation and name in card['games'])
    m = re.match(r'^\S+\s+([A-Z]+)\s*-', PurePosixPath(card['path'].replace('\\','/')).name)
    return TOKENS.get(m[1],0) if m else 0


def matching_cards(game, language):
    generation, bit, _ = selection(game)
    cards = json.loads((DATA/'library-index.json').read_text(encoding='utf-8'))
    return [c for c in cards if c['generation']==generation and c['language']==language and mask(c)&bit]


def selection(game):
    return GAME_FAMILIES[game] if game in GAME_FAMILIES else GAMES[game]


def bundled_value(card):
    """Persist a platform-independent library identifier, never a build-machine path."""
    return 'bundled:' + card['path'].replace('\\','/')


def resolve_card(value):
    value = str(value)
    normalized = value.replace('\\','/')
    if normalized.startswith('bundled:'):
        relative = normalized[len('bundled:'):]
    elif '/wondercards/' in normalized:
        # Accept card choices saved by the previous APK, including Windows separators.
        relative = normalized.split('/wondercards/',1)[1]
    else:
        return Path(value)
    path = PurePosixPath(relative)
    if path.is_absolute() or '..' in path.parts or not path.parts or ':' in relative:
        raise ValueError('Invalid bundled Wonder Card identifier')
    return DATA/'wondercards'/Path(*path.parts)
