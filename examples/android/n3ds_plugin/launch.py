"""Generate card beacons directly from a WC6/WC7; no gift-JSON import."""
import argparse
from pokeldn.uds.card_selection import GAMES, GAME_FAMILIES, LANGUAGES


def build_parser():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--game-family',choices=GAME_FAMILIES,default='xy')
    p.add_argument('--game',choices=GAMES,default=None)
    p.add_argument('--import-card',default='')
    p.add_argument('--distributor-code',default='')
    for game in (*GAMES, *GAME_FAMILIES):
        p.add_argument('--language-'+game,choices=LANGUAGES,default='ENG')
        for lang in LANGUAGES:
            p.add_argument('--card-'+game+'-'+lang.lower(),default='')
    return p


def main(argv=None):
    args=build_parser().parse_args(argv)
    game=args.game or args.game_family
    lang=getattr(args,'language_'+game)
    card=args.import_card or getattr(args,'card_'+game+'_'+lang.lower())
    if not card:
        print('Choose a bundled Wonder Card or import a WC6/WC7 file in Options.')
        return 1
    from pokeldn.uds.card_sender import prepare
    from pokeldn.uds.board3ds import send_pack, BoardError
    try:
        print('Preparing selected Wonder Card...')
        pack=prepare(card,game,lang,args.distributor_code)
        length=send_pack(pack,log=print)
    except (OSError,ValueError,BoardError) as error:
        print(str(error))
        return 1
    print(f'Broadcast started: {pack.name} ({length} bytes stored on board).')
    print('On the 3DS: Mystery Gift, Receive Gift, Get via Local Wireless.')
    return 0


if __name__=='__main__':
    raise SystemExit(main())
