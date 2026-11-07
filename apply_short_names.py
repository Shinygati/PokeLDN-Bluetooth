"""Display Wonder Card names without a redundant 'Mystery Gift:' prefix."""
import argparse
from pathlib import Path
import shutil

OLD = '    private void addCard(Card c){shownCards.add(c);cardAdapter.add(c.name);}'
NEW = '''    private static String wonderCardDisplayName(String name){
        // Keep original names and card bytes unchanged; only trim the UI label.
        return name.replaceFirst("(?i)^\\\\s*mystery\\\\s+gift\\\\s*[:：]\\\\s*", "");
    }
    private void addCard(Card c){shownCards.add(c);cardAdapter.add(wonderCardDisplayName(c.name));}'''

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('repo',type=Path,help='Path to PokeLDN-Bluetooth checkout')
    args=parser.parse_args()
    target=args.repo.resolve()/'examples/android/src/java/org/pokeldn/usbprobe/NdsWondercardActivity.java'
    if not target.is_file():parser.error('Cannot find '+str(target))
    data=target.read_text(encoding='utf-8')
    if 'wonderCardDisplayName(' in data:
        print('Already applied — no changes needed.')
        return
    if data.count(OLD)!=1:parser.error('Unexpected sender source. Expected addCard implementation not found.')
    backup=target.with_name(target.name+'.before-short-card-names.bak')
    if not backup.exists():shutil.copy2(target,backup)
    target.write_text(data.replace(OLD,NEW,1),encoding='utf-8')
    print('Updated:',target)
    print('Only display labels change. Original Wonder Card data remains untouched.')
    print('Backup:',backup)

if __name__=='__main__':main()
