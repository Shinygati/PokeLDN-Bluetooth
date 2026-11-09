"""The Nintendo 3DS Mystery Gift screen: the bundled Gen 7 Wonder Cards (pokeldn/data/gift3ds),
grouped Sun/Moon and Ultra Sun/Ultra Moon, and the gift packs the user has recorded from a Local
Distributor. A card with a matching pack sends to the board; the rest show how to record one.

A card cannot be sent straight from its .wc7full: the distributor encrypts part of each beacon, so a
card is recorded once into a gift pack and then replayed (docs/3ds_local_distributor.md)."""
import os
import shutil
import threading

import flet as ft

from gui import theme as t
from gui.views.widgets import PixelActivity
from pokeldn.app.i18n import t as tr
from pokeldn.app.paths import ROOT
from pokeldn.uds import board3ds
from pokeldn.uds.catalog3ds import GROUP_LABELS, GROUP_SM, GROUP_USUM, Catalog, load_packs

PACKS_DIR = os.path.join(ROOT, "gifts")


class Gift3DSView:
    def __init__(self, app):
        self.app = app
        self.catalog = Catalog.load()
        self.packs = load_packs(PACKS_DIR)
        self.group = GROUP_SM
        self.language = "ENG" if any(c.language_code == "ENG" for c in self.catalog.cards) else None
        self.query = ""
        self.status = t.text("", 12, t.MUTED)
        self.list = ft.Column(spacing=8, scroll=ft.ScrollMode.AUTO, expand=True)
        self.column = ft.Column(spacing=t.GAP, expand=True)
        self.control = self.column
        self._render()

    # Build

    def _header(self) -> ft.Control:
        langs = [("", tr('gift3ds.all_languages', 'All languages'))] + [
            (code, name) for code, name in self.catalog.languages()]
        language = t.dropdown([(c, n) for c, n in langs], self.language or "", self._set_language) \
            if hasattr(t, "dropdown") else None
        search = t.field(hint=tr('gift3ds.search_cards', 'Search by name or number'),
                         on_change=self._set_query)
        actions = [t.secondary_button(tr('gift3ds.how_to_record', 'How to record a card'),
                                      lambda e: self.app.navigate("docs", doc="3ds_local_distributor.md"),
                                      "book-open"),
                   t.button(tr('gift3ds.import_pack', 'Import pack'), self._import, "plus")]
        top = ft.Row([t.text(tr('gift3ds.nintendo_3ds', 'Nintendo 3DS'), 22, weight=ft.FontWeight.W_600,
                             expand=True), *actions], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
        controls = [top, t.text(tr('gift3ds.intro', 'Mystery Gift over local wireless. Pick a card '
                    'you have recorded into a gift pack and send it to the board; the board then '
                    'offers it to any 3DS.'), 13, t.MUTED), search]
        if language is not None:
            controls.append(language)
        return ft.Column(controls, spacing=10)

    def _tabs(self) -> ft.Control:
        counts = {g: len(self.catalog.group(g, language_code=self.language or None)) for g in
                  (GROUP_SM, GROUP_USUM)}
        return t.segmented([(GROUP_SM, f"{GROUP_LABELS[GROUP_SM]} · {counts[GROUP_SM]}", "gamepad"),
                            (GROUP_USUM, f"{GROUP_LABELS[GROUP_USUM]} · {counts[GROUP_USUM]}", "gamepad")],
                           self.group, self._set_group, wrap=True)

    def _render(self) -> None:
        self.column.controls = [self._header(), self._tabs(), self.status, self.list]
        self._fill()
        if self.column.page:
            self.column.update()

    def _fill(self) -> None:
        cards = self.catalog.group(self.group, language_code=self.language or None, query=self.query)
        if not cards:
            self.list.controls = [t.text(tr('gift3ds.no_cards', 'No cards match.'), 13, t.MUTED)]
        else:
            self.list.controls = [self._card_row(card) for card in cards]
        if self.list.page:
            self.list.update()

    def _card_row(self, card) -> ft.Control:
        have = self.packs.get(card.id)
        games = ", ".join(card.games)
        subtitle = f"#{card.id:04d} · {games} · {card.language}"
        left = ft.Column([t.text(card.title, 14, weight=ft.FontWeight.W_600),
                          t.text(subtitle, 12, t.MUTED)], spacing=2, expand=True)
        if have:
            action = t.button(tr('gift3ds.send_to_board', 'Send to board'),
                              lambda e, c=card: self._send(c), "upload")
        else:
            action = t.secondary_button(tr('gift3ds.record_to_send', 'Record to send'),
                                        lambda e: self.app.navigate("docs", doc="3ds_local_distributor.md"),
                                        "disc")
        return t.card_box(ft.Row([left, action], alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                 vertical_alignment=ft.CrossAxisAlignment.CENTER))

    # Events

    def _set_group(self, group) -> None:
        self.group = group
        self._fill()

    def _set_language(self, code) -> None:
        self.language = code or None
        self._render()

    def _set_query(self, event) -> None:
        self.query = event.control.value or ""
        self._fill()

    def _send(self, card) -> None:
        entry = self.packs.get(card.id)
        if not entry:
            return
        path, pack = entry[0]
        self.status.value = tr('gift3ds.sending', 'Sending {value0} to the board...', value0=card.title)
        self.status.color = t.MUTED
        if self.status.page:
            self.status.update()

        def work():
            try:
                length = board3ds.send_pack(pack, radio=self._radio(), log=None)
                message = tr('gift3ds.sent', 'Stored {value0} bytes. The board is offering the gift; '
                             'on the 3DS: Mystery Gift, Receive Gift, Get via Local Wireless.',
                             value0=length)
                colour = t.GREEN if hasattr(t, "GREEN") else t.TEXT
            except board3ds.BoardError as error:
                message, colour = str(error), t.RED if hasattr(t, "RED") else t.TEXT
            self.status.value = message
            self.status.color = colour
            if self.status.page:
                self.status.update()

        threading.Thread(target=work, daemon=True).start()

    def _radio(self):
        """The board the app already owns, when it exposes one; otherwise board3ds opens it."""
        getter = getattr(self.app, "radio", None)
        return getter() if callable(getter) else None

    def _import(self, event) -> None:
        def picked(result: ft.FilePickerResultEvent):
            if not result.files:
                return
            os.makedirs(PACKS_DIR, exist_ok=True)
            for file in result.files:
                if file.path and file.path.endswith(".json"):
                    shutil.copy2(file.path, os.path.join(PACKS_DIR, os.path.basename(file.path)))
            self.packs = load_packs(PACKS_DIR)
            self._fill()

        picker = ft.FilePicker(on_result=picked)
        self.app.page.overlay.append(picker)
        self.app.page.update()
        picker.pick_files(dialog_title=tr('gift3ds.choose_pack', 'Choose a gift pack (.gift.json)'),
                          allowed_extensions=["json"])
