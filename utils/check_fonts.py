import os
from fontTools.ttLib import TTFont, TTLibError

# Correct absolute path to the fonts directory
FONT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src', 'handanim', 'fonts'))

def is_font_corrupted(font_path):
    try:
        TTFont(font_path)
        return False
    except TTLibError:
        return True
    except Exception as e:
        print(f"Unexpected error for {font_path}: {e}")
        return True

def main():
    if not os.path.isdir(FONT_DIR):
        print(f"Font directory not found: {FONT_DIR}")
        return
    corrupted = []
    for fname in os.listdir(FONT_DIR):
        fpath = os.path.join(FONT_DIR, fname)
        if os.path.isfile(fpath) and fname.lower().endswith('.ttf'):
            if is_font_corrupted(fpath):
                corrupted.append(fname)
    if corrupted:
        print("Corrupted fonts found:")
        for f in corrupted:
            print(f" - {f}")
    else:
        print("No corrupted fonts detected.")

if __name__ == "__main__":
    main()
