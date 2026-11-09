"""One Nintendo 3DS entry in PokeLDN, beside Nintendo DS: send a Gen 6/7 local Mystery Gift the
board replays from a Wonder Card you recorded from a Local Distributor (docs/3ds_local_distributor.md)."""
from pokeldn.plugins import Field, Game, Tool

STEPS = (
    "Pick a gift (a Wonder Card you recorded into a gift pack in the gifts folder).",
    "Connect the ESP32-S3 on PokeLDN's Bluetooth firmware (1.10.0 or later).",
    "Open the Session tab and select Start: the board broadcasts the gift.",
    "On the 3DS: Mystery Gift, Receive Gift, Get via Local Wireless.",
)


def _pack_choices():
    """(value, label) for every recorded pack, labelled by card and game group."""
    try:
        from pokeldn.uds.catalog3ds import Catalog, load_packs, pack_card_id, packs_dir

        catalog = Catalog.load()
        titles = {c.id: c for c in catalog.cards}
        choices = []
        for cid, entries in sorted(load_packs(packs_dir()).items()):
            for path, pack in entries:
                card = titles.get(cid)
                group = ""
                if card:
                    tags = [g for g, bit in (("SM", 0x3), ("USUM", 0xC)) if card.mask & bit]
                    group = f" [{'/'.join(tags)}]" if tags else ""
                name = (card.title if card else pack.name) or path.stem
                choices.append((str(path), f"{name}{group}"))
        return tuple(choices)
    except Exception:
        return ()


def register(api):
    choices = _pack_choices()
    fields = ()
    if choices:
        fields = (Field("--pack", "Gift", "choice", default=choices[0][0], choices=choices,
                        help="A Wonder Card recorded from a Local Distributor. Import more on the "
                             "gifts folder; record new ones with the PC (see docs/3ds_local_distributor.md)."),)
    sender = Tool(
        "n3ds-gift",
        "Mystery Gift",
        "launch.py",
        "Broadcast a Gen 6/7 Wonder Card for a real 3DS to receive over local wireless.",
        STEPS,
        fields=fields,
        radio=True,       # it uses the board to broadcast
        joins=False,      # the 3DS only scans the beacon; it never joins
    )
    api.add_game(Game("nintendo-3ds", "Nintendo 3DS", "N3DS", "3ds_local_distributor.md", (sender,)),
                 icon="n3ds-console.png")
