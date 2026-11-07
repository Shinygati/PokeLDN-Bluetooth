#!/usr/bin/env python3
"""Only show Disconnect when the Nintendo DS BLE sender is connected."""
from pathlib import Path
from datetime import datetime
import sys

REL = Path('examples/android/src/java/org/pokeldn/usbprobe/NdsWondercardActivity.java')

def main():
    if len(sys.argv) != 2:
        raise SystemExit('Usage: py -3.13 install_to_repo.py "C:\\path\\to\\PokeLDN-Bluetooth"')
    target = Path(sys.argv[1]).expanduser().resolve() / REL
    if not target.is_file():
        raise SystemExit(f'ERROR: File not found: {target}')
    source = target.read_text(encoding='utf-8')
    if 'disconnectButton.setVisibility(connected ? View.VISIBLE : View.GONE);' in source:
        print('Already installed; no changes needed.')
        return
    old_field = 'private LinearLayout languageTabRow, gameRows, connectionTools;'
    old_button = 'button(tools,"Disconnect",()->disconnect());'
    old_visual = 'private void setStatusVisuals(String message){\n        boolean linked=connected&&ready;'
    for item in (old_field, old_button, old_visual):
        if source.count(item) != 1:
            raise SystemExit(f'ERROR: Expected source pattern was not found exactly once: {item!r}. File unchanged.')
    updated = source.replace(old_field, old_field + '\n    private Button disconnectButton;', 1)
    updated = updated.replace(old_button, 'disconnectButton=button(tools,"Disconnect",()->disconnect());\n        disconnectButton.setVisibility(View.GONE);', 1)
    updated = updated.replace(old_visual, old_visual + '\n        if(disconnectButton!=null)disconnectButton.setVisibility(connected ? View.VISIBLE : View.GONE);', 1)
    backup = target.with_name(target.name + '.backup-' + datetime.now().strftime('%Y%m%d-%H%M%S'))
    backup.write_text(source,encoding='utf-8')
    target.write_text(updated,encoding='utf-8')
    print('Backup:',backup)
    print('Updated:',target)
    print('Disconnect is hidden while disconnected and shown after an ESP32 BLE connection.')
    print('Rebuild the APK to apply the change.')

if __name__ == '__main__':
    main()
