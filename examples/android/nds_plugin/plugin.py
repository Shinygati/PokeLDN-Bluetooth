"""Native Wonder Card sender available under Nintendo DS in PokeLDN's Games page."""
from pokeldn.plugins import Game, Tool

NAMES = (
    "Diamond", "Pearl", "Platinum", "Heart Gold", "Soul Silver",
    "Black", "White", "Black 2", "White 2",
)

def register(api):
    tools = []
    for index, name in enumerate(NAMES):
        generation = "IV" if index < 5 else "V"
        tools.append(Tool(
            "nds-wondercard-" + name.lower().replace(" ", "-"),
            name,
            "launch.py",
            f"Open the Gen {generation} Wonder Card sender for {name}.",
            (
                "Connect the ESP32-S3 running Gen IV/V Wondercard Sender firmware.",
                "Press Start to open the Nintendo DS sender screen.",
                "Choose a language and a built-in card, or import a custom Wonder Card.",
                "Scan and select your ESP32-S3, then send the selected gift.",
            ),
            fixed=("--game-index", str(index)),
            radio=False,
            joins=False,
        ))
    api.add_game(Game("nintendo-ds", "Nintendo DS", "NDS", "", tuple(tools)), icon="nds-console.png")
