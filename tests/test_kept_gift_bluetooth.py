from pokeldn.ldn import esp32_wlan


class _Radio:
    def __init__(self):
        self.started = 0

    def start_beacon(self):
        self.started += 1


def test_a_gift_kept_over_bluetooth_starts_at_once(monkeypatch):
    """A board on the phone's Bluetooth stays powered after the app lets go, so the stored Mystery Gift
    starts there and then; over a USB cable the board starts it itself after its next power-up."""
    for spec, bluetooth in (("esp32:android://ble", True), ("esp32:ble", True), ("esp32:ble:POKELDN-RADIO", True),
                            ("esp32:socket://127.0.0.1:47811", True), ("esp32:android://board", False),
                            ("esp32:/dev/ttyACM0", False), ("esp32:COM5", False), ("", False)):
        monkeypatch.setenv("POKELDN_RADIO", spec)
        radio = _Radio()
        assert esp32_wlan.over_bluetooth() is bluetooth, spec
        assert esp32_wlan.keep_running(radio) is bluetooth, spec
        assert radio.started == int(bluetooth), spec
