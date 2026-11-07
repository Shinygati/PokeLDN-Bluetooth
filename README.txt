PokeLDN Gift Sender — source UI replacement

Includes TWO files only, with exactly their target folder structure.
Copy folder examples into your PokeLDN-Bluetooth checkout, merging folders; or run install_to_repo.py (backs up originals).

Implemented:
- PokéLDN Gift Sender header, connected status, white DS Phat art
- All NINE game choices inline; tap row to select, no separate game popup
- All seven language options (horizontal swipe strip, auto-scroll to selection)
- Wonder Card dropdown reads embedded title, fallback catalog title
- Right-side chevron only (native spinner background removed)
- LED legend, start/stop, scan/connect and import retained
- Dark purple style; light mode style; native ripple and scale click feedback
- Two-column UI on >=600dp layouts; stacked cards on narrow phones

DO NOT touch Gen5.java or Gen4.java: existing protocol preserved.
The firmware LED changes still require flashing separate ESP32 firmware.

IMPORTANT: This is SOURCE only, not an APK. Must rebuild successfully.
Build from PowerShell in REPOSITORY root; the android build.py sets Chaquopy Python automatically:
  $env:GRADLE = "C:\Gradle\gradle-8.14.5\bin\gradle.bat"
  .\.venv\Scripts\python.exe examples\android\build.py --release
Only copy the APK after the console prints BUILD SUCCESSFUL.

This update was not hardware-tested and is not guaranteed pixel-perfect at every screen size.
