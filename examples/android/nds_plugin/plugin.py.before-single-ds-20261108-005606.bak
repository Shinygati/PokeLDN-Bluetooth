"""One Nintendo DS entry in PokeLDN; select the game inside the native sender."""
from pokeldn.plugins import Game, Tool


def register(api):
    sender = Tool(
        "nds-wondercard",
        "Wonder Card Sender",
        "launch.py",
        "Open the Nintendo DS Wonder Card Sender and choose your game there.",
        (
            "Open the Session tab and select Start to launch the Wonder Card Sender.",
            "Choose Diamond, Pearl, Platinum, HeartGold, SoulSilver, Black, White, Black 2, or White 2 inside the sender.",
            "Choose a language and Wonder Card, or import a compatible card.",
            "Connect the ESP32-S3 and start Wonder Card distribution.",
        ),
        fixed=("--game-index", "0"),  # Default to Diamond; sender has its own game selector.
        radio=False,
        joins=False,
    )
    api.add_game(
        Game("nintendo-ds", "Nintendo DS", "NDS", "", (sender,)),
        icon="nds-console.png",
    )
