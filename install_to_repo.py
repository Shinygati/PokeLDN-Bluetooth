from pathlib import Path
import shutil,sys,datetime
if len(sys.argv)!=2:
    print(r'Usage: py -3.13 install_to_repo.py "C:\Users\scar_\Documents\GitHub\PokeLDN-Bluetooth"')
    sys.exit(2)
root=Path(sys.argv[1]).expanduser().resolve()
base=Path(__file__).resolve().parent
items=[
 'examples/android/src/java/org/pokeldn/usbprobe/NdsWondercardActivity.java',
 'examples/android/nds-assets/nds-phat.png',
]
if not (root/'examples/android/build.py').is_file():
    sys.exit('ERROR: Not a PokeLDN repository (examples/android/build.py missing).')
for rel in items:
    src=base/rel;dst=root/rel
    if not src.is_file():sys.exit(f'Missing from package: {src}')
    dst.parent.mkdir(parents=True,exist_ok=True)
    if dst.exists():
        backup=dst.with_name(dst.name+'.backup-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S'))
        shutil.copy2(dst,backup)
        print('Backup:',backup)
    shutil.copy2(src,dst)
    print('Updated:',dst)
print(r'Done. Rebuild: .\.venv\Scripts\python.exe examples\android\build.py --release')
