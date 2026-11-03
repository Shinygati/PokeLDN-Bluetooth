#!/usr/bin/env python3
"""Build chip-specific Bluetooth radio images with an activated ESP-IDF 6.1 environment."""
import argparse
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
TARGETS = {"esp32": "", "esp32s3": "s3", "esp32c2": "c2", "esp32c3": "c3",
           "esp32c5": "c5", "esp32c6": "c6", "esp32c61": "c61"}
PREVIEW = {"esp32s31": "s31"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--targets", nargs="+", choices=(*TARGETS, *PREVIEW), default=list(TARGETS))
    args = parser.parse_args()
    idf_path = os.environ.get("IDF_PATH")
    if not idf_path or not (Path(idf_path) / "tools/idf.py").is_file():
        parser.error("Activate ESP-IDF 6.1 first (export.sh or export.ps1).")
    project = ROOT / "firmware/esp32"
    output = ROOT / "gui/firmware"
    output.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "POKELDN_BLE": "1"}
    defaults = ";".join((project / name).as_posix() for name in
                        ("sdkconfig.defaults", "sdkconfig.defaults.ble"))
    for target in args.targets:
        build = project / "build" / ("ble-" + target)
        command = [sys.executable, str(Path(idf_path) / "tools/idf.py")]
        if target in PREVIEW:
            command.append("--preview")
        command += ["-B", str(build), "-DIDF_TARGET=" + target,
                    "-DSDKCONFIG=" + str(build / "sdkconfig"),
                    "-DSDKCONFIG_DEFAULTS=" + defaults]
        subprocess.run(command + ["build"], cwd=project, env=env, check=True)
        suffix = {**TARGETS, **PREVIEW}[target]
        filename = "pokeldn-radio-ble" + ("-" + suffix if suffix else "") + ".bin"
        merge = [sys.executable, str(Path(idf_path) / "tools/idf.py")]
        if target in PREVIEW:
            merge.append("--preview")
        subprocess.run(merge + ["-B", str(build), "merge-bin", "-o", str(output / filename)],
                       cwd=project, env=env, check=True)
        print("Built", output / filename, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
