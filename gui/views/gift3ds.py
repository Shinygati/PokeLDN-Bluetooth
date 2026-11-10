"""Nintendo 3DS card-library screen (Gen VI / VII).

This screen never implies that a selected WC6/WC7 is already a broadcastable
3DS distribution. The UDS fragment encoder is still under investigation.
It intentionally replaces the old recording / gift-pack workflow with a local
Wonder Card library and an Add Wonder Card file picker.
"""
from __future__ import annotations

import os
from pathlib import Path
import threading

import flet as ft

from gui import theme as t
from pokeldn.app.i18n import t as tr
from pokeldn.app.paths import ROOT
from pokeldn.uds.wondercard_library import catalog, import_card

LIBRARY = Path(__file__).resolve().parents[2] / "pokeldn" / "data" / "gift3ds" / "wondercards"
CUSTOM = Path(ROOT) / "wondercards" / "custom"

GROUPS = {
    "xy": (6, 0x3, "X / Y"),
    "oras": (6, 0xC, "Omega Ruby / Alpha Sapphire"),
    "sm": (7, 0x3, "Sun / Moon"),
    "usum": (7, 0xC, "Ultra Sun / Ultra Moon"),
}


class Gift3DSView:
    def __init__(self, app):
        self.app = app
        self.group = "sm"
        self.language = ""
        self.query = ""
        self.cards = []
        self.status = t.text("", 12, t.MUTED)
        self.list = ft.Column(spacing=8, scroll=ft.ScrollMode.AUTO, expand=True)
        self.column = ft.Column(spacing=t.GAP, expand=True)
        self.control = self.column
        self._refresh()

    def _refresh(self):
        self.cards = catalog(LIBRARY) + catalog(CUSTOM)
        self._render()

    def _header(self):
        search = t.field(hint="Search Wonder Cards by title or ID", on_change=self._search)
        actions = [t.button("Add Wonder Card", self._import, "plus")]
        head = ft.Row([t.text("Nintendo 3DS", 22, weight=ft.FontWeight.W_600, expand=True), *actions],
                      alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
        return ft.Column([
            head,
            t.text("Bundled Gen 6 and Gen 7 Wonder Cards. Direct wireless distribution "
                   "requires the verified UDS encoder; importing a card does not "
                   "make it broadcastable yet.", 13, t.MUTED),
            search,
        ], spacing=10)

    def _render(self):
        self.column.controls = [self._header(),
            t.segmented([(key, group[2], "gamepad") for key, group in GROUPS.items()],
                        self.group, self._choose_group, wrap=True),
            self.status, self.list]
        self._fill()
        if self.column.page:
            self.column.update()

    def _fill(self):
        generation, mask, _ = GROUPS[self.group]
        matches = []
        for c in self.cards:
            if c["generation"] != generation:
                continue
            # A bare WC file has no distribution game mask; leave it visible
            # in either generation group until the user selects a target game.
            games = c.get("games") or ()
            if games:
                names = ("X", "Y", "Omega Ruby", "Alpha Sapphire") if generation == 6 else (
                    "Sun", "Moon", "Ultra Sun", "Ultra Moon")
                if not any(name in games for name in [names[i] for i in range(4) if mask & (1 << i)]):
                    continue
            if self.language and c.get("language") != self.language:
                continue
            query = self.query.lower().strip()
            if query and query not in c["title"].lower() and query not in str(c["id"]):
                continue
            matches.append(c)
        matches.sort(key=lambda c: (c["id"], c.get("language", ""), c["title"]))
        if matches:
            self.list.controls = [self._card_row(c) for c in matches]
        else:
            self.list.controls = [t.text("No Wonder Cards match this selection.", 13, t.MUTED)]
        if self.list.page:
            self.list.update()

    def _card_row(self, card):
        name = card["title"]
        details = f'#{card["id"]:04d} · {card.get("language", "UNK")} · {Path(card["path"]).suffix}'
        if card.get("games"):
            details += " · " + ", ".join(card["games"])
        left = ft.Column([t.text(name, 14, weight=ft.FontWeight.W_600),
                          t.text(details, 12, t.MUTED)], spacing=2, expand=True)
        btn = t.secondary_button("Distribution unavailable", lambda e: self._unsupported(), "info")
        return t.card_box(ft.Row([left, btn], alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                 vertical_alignment=ft.CrossAxisAlignment.CENTER))

    def _unsupported(self):
        self.status.value = ("A direct WC6/WC7-to-UDS beacon encoder has not yet passed "
                             "hardware validation. This source update does not transmit a card.")
        if self.status.page:
            self.status.update()

    def _choose_group(self, group):
        self.group = group
        self._fill()

    def _search(self, event):
        self.query = event.control.value or ""
        self._fill()

    def _import(self, event):
        def picked(result: ft.FilePickerResultEvent):
            if not result.files:
                return
            count = 0
            failures = []
            for file in result.files:
                try:
                    if not file.path:
                        raise ValueError("No local path available")
                    import_card(file.path, CUSTOM)
                    count += 1
                except (OSError, ValueError) as exc:
                    failures.append(f"{file.name}: {exc}")
            self.status.value = f"Added {count} Wonder Card(s)." + (" Errors: " + "; ".join(failures[:3]) if failures else "")
            self._refresh()

        picker = ft.FilePicker(on_result=picked)
        self.app.page.overlay.append(picker)
        self.app.page.update()
        picker.pick_files(dialog_title="Add a WC6 / WC7 Wonder Card", allow_multiple=True,
                          allowed_extensions=["wc6", "wc6full", "wc7", "wc7full"])
