from pathlib import Path

FONT_PATHS = {
    # Original fonts
    "feasibly": "FeasiblySingleLine-z8D90.ttf",
    "headstay": "HeadstayRegular.ttf",
    "backstay": "BackstaySingleLine-rgOw8.ttf",
    "caveat": "Caveat-VariableFont_wght.ttf",
    "permanent_marker": "PermanentMarker-Regular.ttf",
    "notosans_math": "NotoSansMath-Regular.ttf",
    "handanimtype1": str(Path("custom") / "handanimtype1.json"),
    "cabin_sketch": "CabinSketch-Regular.ttf",
    # Hand-drawn / Sketch
    "patrick_hand": "PatrickHand-Regular.ttf",
    "architects_daughter": "ArchitectsDaughter-Regular.ttf",
    "ArchitectsDaughter-Regular": "ArchitectsDaughter-Regular.ttf",  # Alias for compatibility
    "handlee": "Handlee-Regular.ttf",
    "short_stack": "ShortStack-Regular.ttf",
    "marck_script": "MarckScript-Regular.ttf",
    # Marker / Chalk
    "balsamiq_sans": "BalsamiqSans-Regular.ttf",
    "fredericka_the_great": "FrederickatheGreat-Regular.ttf",
    "cabin_sketch": "CabinSketch-Regular.ttf",
    "amatic_sc": "AmaticSC-Regular.ttf",
    # Math / Technical
    "space_mono": "SpaceMono-Regular.ttf",
    # Script / Calligraphy
    "pacifico": "Pacifico-Regular.ttf",
    "great_vibes": "GreatVibes-Regular.ttf",
    "sacramento": "Sacramento-Regular.ttf",
}

PACKAGE_FONT_ROOT = Path(__file__).resolve().parents[1] / "fonts"
LEGACY_FONT_ROOT = Path(__file__).resolve().parents[3] / "fonts"


def list_fonts():
    """
    List all available fonts
    """
    return list(FONT_PATHS.keys())



def get_font_path(font_name):
    """
    Get the path to a font
    """
    font_relative_path = Path(FONT_PATHS[font_name])
    for font_root_path in (PACKAGE_FONT_ROOT, LEGACY_FONT_ROOT):
        font_path = font_root_path / font_relative_path
        if font_path.is_file():
            return str(font_path)

    msg = f"Bundled font '{font_name}' was not found in '{PACKAGE_FONT_ROOT}' or '{LEGACY_FONT_ROOT}'."
    raise FileNotFoundError(msg)
