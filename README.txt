PokeLDN Nintendo DS Click Fix
=============================
This fixes the single Nintendo DS category entry so tapping it opens its Options pane on a phone, instead of only selecting the category.

Only gui/views/games.py is modified. Existing Wonder Card Sender, icon, game selector, BLE functionality, and plugin files are preserved.

Extract to Downloads, then PowerShell:
py -3.13 "$env:USERPROFILE\Downloads\PokeLDN-DS-Click-Fix\install_to_repo.py" "C:\Users\scar_\Documents\GitHub\PokeLDN-Bluetooth"

Build (same PowerShell window):
cd "C:\Users\scar_\Documents\GitHub\PokeLDN-Bluetooth"
$env:GRADLE = "C:\Gradle\gradle-8.14.5\bin\gradle.bat"
$env:POKELDN_ANDROID_BUILD_PYTHON = (Resolve-Path '.\.venv\Scripts\python.exe').Path
.\.venv\Scripts\python.exe examples\android\build.py --release

Only install the APK after BUILD SUCCESSFUL. The patch checks Python syntax and creates a backup.
