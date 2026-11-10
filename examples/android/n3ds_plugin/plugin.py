"""Game then language then Wonder Card, with direct WC6/WC7 imports."""
from pathlib import Path
from pokeldn.plugins import Field, Game, Tool
from pokeldn.uds.card_selection import GAME_FAMILIES, LANGUAGES, matching_cards, bundled_value


def register(api):
    fields = [Field('--game-family','Game pair','choice',default='xy',choices=tuple((k,'Pokémon '+v[2]) for k,v in GAME_FAMILIES.items())),
              Field('--import-card','Import Wonder Card instead of choosing a bundled card','file',default='',
                    exts=('wc6','wc6full','wc7','wc7full'),help='Only Wonder Card files are accepted. Clear this field to use the bundled library.')]
    for game,(generation,_,_) in GAME_FAMILIES.items():
        langs = [(key,name) for key,(_,name) in LANGUAGES.items() if generation==7 or key not in ('CHS','CHT')]
        langflag = '--language-'+game
        fields.append(Field(langflag,'Language','choice',default='ENG',choices=tuple(langs),when=('--game-family',game)))
        for language,_ in langs:
            choices = [('', 'Select a Wonder Card')]
            choices.extend((bundled_value(c),f"#{c['id']:04d} {c['title']}") for c in matching_cards(game,language))
            fields.append(Field('--card-'+game+'-'+language.lower(),'Wonder Card','choice',default='',choices=tuple(choices),
                                when=(langflag,language),unless='--import-card',help='EventsGallery cards compatible with the chosen game and language.'))
        if generation==7:
            fields.append(Field('--distributor-code','One-time Gen 7 setup: your decrypted distributor .code','file',default='',
                                exts=('code',),when=('--game-family',game),remembered=False,
                                help='Required once for Gen 7 signing. Stored in app-private data, never bundled in the APK. Leave empty after setup.'))
    sender=Tool('n3ds-gift','Mystery Gift','launch.py',
                'Distribute Gen 6 or Gen 7 Wonder Cards over local wireless.',
                ('Choose a game and language, then a bundled Wonder Card or import a WC6/WC7 file.',
                 'For Gen 7, import your distributor .code once in Options.',
                 'Connect the Bluetooth board, then open Session and Start.',
                 'On the 3DS choose Mystery Gift, Receive Gift, Get via Local Wireless.'),
                fields=tuple(fields),radio=True,joins=False)
    api.add_game(Game('nintendo-3ds','Nintendo 3DS','N3DS','gen67_hardware_test.md',(sender,)),icon='n3ds-console.png')
