"""Launch the native Android BLE sender as a screen above PokeLDN's WebView."""
import argparse

def build_parser():
    parser = argparse.ArgumentParser(description="Open Nintendo DS Wonder Card Sender")
    parser.add_argument("--game-index", type=int, choices=range(9), required=True)
    return parser

def main(argv=None):
    args = build_parser().parse_args(argv)
    from pokeldn.app import android
    if not android.active():
        print("Nintendo DS wireless sending in this integration requires the Android APK.")
        return 1
    android.bridge().openNdsWondercards(args.game_index)
    print("Nintendo DS Wondercard Sender screen opened on Android.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
