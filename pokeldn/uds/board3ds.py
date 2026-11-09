"""Store a 3DS gift pack on the PokeLDN board and start it, for the app and the CLI.

Both go through the board the way every other PokeLDN tool does
(pokeldn.ldn.esp32_wlan.use_from_environment): POKELDN_RADIO selects it. The GUI, which owns the one
board a session allows, can pass an already-open radio instead.
"""

from __future__ import annotations

from .gift_pack import GiftPack
from .portable3ds import build_image


class BoardError(RuntimeError):
    pass


def send_pack(pack: GiftPack, *, radio=None, interval_ms: int = 102, log=None) -> int:
    """Build ``pack``'s image, store it on the board and start it. Returns the stored byte length.

    With no ``radio`` the board is taken from the environment and closed again. Raises BoardError
    when there is no board, its firmware is too old, or the transfer fails.
    """
    from pokeldn.ldn import esp32, esp32_wlan

    image = build_image(pack, interval_ms=interval_ms)
    owned = radio is None
    if owned:
        radio = esp32_wlan.use_from_environment(log=log)
        if radio is None:
            raise BoardError("no board: set POKELDN_RADIO=esp32:auto, or open the board in the app")
    try:
        if esp32.firmware_version(radio.hello()) < esp32.BEACON_3DS_FIRMWARE:
            need = ".".join(map(str, esp32.BEACON_3DS_FIRMWARE))
            raise BoardError(f"the board's firmware sends no 3DS gift; install radio firmware {need} "
                             "or later from the Board page")
        state = radio.store_beacon(image)
        esp32_wlan.keep_running(radio)
        return state.length
    except (OSError, esp32.RadioError) as error:
        raise BoardError(str(error)) from error
    finally:
        if owned:
            try:
                radio.close()
            except Exception:
                pass
