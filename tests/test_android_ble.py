import json
import subprocess
import sys

# A fresh interpreter: install() rewrites serial and esp_pylib for the whole process.
SCRIPT = r'''
import json, sys, types
from pokeldn.ldn import esp32_sim

air = esp32_sim.Air()
board = esp32_sim.SimulatedBoard(air)


class Ble:
    """BleStream.java's interface over the simulated board's host stream."""

    def __init__(self):
        self.stream, self.closed, self.discards, self.bauds = board.host_stream(), False, 0, []

    def read(self, size):
        return self.stream.read(size)

    def available(self):
        return 0

    def write(self, data):
        self.stream.write(bytes(data))
        return len(data)

    def setBaud(self, baud):
        self.bauds.append(baud)

    def setLines(self, dtr, rts):
        raise AssertionError("a Bluetooth port has no DTR or RTS")

    def isClosed(self):
        return self.closed

    def discardInput(self):
        self.discards += 1

    def close(self):
        self.closed = True


ble = Ble()


class Bridge:
    usbState = staticmethod(lambda: "missing")
    bleState = staticmethod(lambda: "ready")
    bleName = staticmethod(lambda: "POKELDN-RADIO")
    bleAddress = staticmethod(lambda: "AA:BB:CC:DD:EE:FF")
    openBle = staticmethod(lambda: (ble.discardInput(), ble)[1])


sys.modules["java"] = types.SimpleNamespace(jclass=lambda name: Bridge)
from pokeldn.app import android
android.install()
from serial.tools import list_ports
from pokeldn.ldn import esp32

ports = [(p.device, p.vid, p.pid, p.serial_number) for p in list_ports.comports()]
radio = esp32.Radio.open_serial(android.BLE_PORT, fast_baud=None)
first = bytes(radio.info.sta_mac).hex()
radio.close()
still_up = not ble.closed
radio = esp32.Radio.open_serial(android.BLE_PORT)
second = bytes(radio.info.sta_mac).hex()
radio.close()
print(json.dumps({"ports": ports, "first": first, "second": second, "still_up": still_up,
                  "discards": ble.discards, "bauds": sorted(set(ble.bauds)),
                  "over_bluetooth": [android.over_bluetooth(android.BLE_PORT), android.over_bluetooth(android.PORT)]}))
'''


def _run() -> dict:
    run = subprocess.run([sys.executable, "-c", SCRIPT], capture_output=True, text=True, timeout=60)
    assert run.returncode == 0, run.stderr
    return json.loads(run.stdout.strip().splitlines()[-1])


def test_bluetooth_board_is_listed_and_answers_hello():
    """The Android app's Bluetooth board (BleStream.java) is a serial port the launchers open unchanged:
    listed as native USB, answering HELLO with no line rate switched, and left connected when a
    session closes it, so the next session reuses the connection with its old input dropped."""
    out = _run()
    assert out["ports"] == [["android://ble", 0x303A, 0x1001, "AA:BB:CC:DD:EE:FF"]]
    assert out["first"] == out["second"] and len(out["first"]) == 12
    assert out["still_up"]
    assert out["discards"] == 2
    # No line rate reaches the stream, and no BAUD is sent over Bluetooth (fast_baud 0).
    assert out["bauds"] == []
    assert out["over_bluetooth"] == [True, False]
