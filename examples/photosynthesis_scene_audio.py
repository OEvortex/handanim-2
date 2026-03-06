# ruff: noqa: E402, PLR0915
"""Port of the Manim PhotosynthesisScene into handanim with built-in audio sync."""

from __future__ import annotations

import argparse
import asyncio
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

try:
    import edge_tts
except ImportError as exc:
    msg = "Install edge-tts first: uv add --dev edge-tts --frozen --python 3.14"
    raise SystemExit(msg) from exc

from handanim.animations import (
    FadeInAnimation,
    FadeOutAnimation,
    ScaleInPlace,
    SketchAnimation,
    TransformAnimation,
    TranslateFromAnimation,
)
from handanim.core import DrawableGroup, FillStyle, Scene, SketchStyle, StrokeStyle
from handanim.primitives import Arrow, Circle, Ellipse, Line, Math, Rectangle, Text

BACKGROUND = (0.09, 0.10, 0.12)
PRIMARY_TEXT = (0.83, 0.83, 0.83)
ACCENT_BLUE = (0.29, 0.62, 1.00)
ACCENT_GREEN = (0.42, 0.65, 0.43)
ACCENT_ORANGE = (0.91, 0.58, 0.37)
EMPHASIS = (0.93, 0.90, 0.89)
SUN_YELLOW = (0.98, 0.84, 0.11)

BOOKMARK_RE = re.compile(r"<bookmark\s+(?:mark|name)\s*=\s*['\"][^'\"]+['\"]\s*/>")
VOICE = "en-US-JennyNeural"
VOICEOVER_VOLUME = 1.35
SKETCH = SketchStyle(roughness=1.6, bowing=1.0)

SCRIPTS = {
    "intro": "<bookmark mark='title'/> Photosynthesis. <bookmark mark='subtitle'/> "
    "It is the process plants use to convert light into stored energy.",
    "leaf": "<bookmark mark='fade_intro'/> The action happens inside a plant leaf. "
    "<bookmark mark='leaf'/> Its structure helps capture light and move materials.",
    "sunlight": "<bookmark mark='sun'/> Sunlight provides the energy. "
    "<bookmark mark='rays'/> Bright rays strike the leaf and drive the reactions.",
    "inputs": "<bookmark mark='co2'/> Carbon dioxide enters from the air. "
    "<bookmark mark='absorb'/> Those molecules move into the leaf. "
    "<bookmark mark='water'/> Water rises from the roots into the same process.",
    "outputs": "<bookmark mark='fade_labels'/> With light, water, and carbon dioxide available, "
    "the leaf can make sugar. <bookmark mark='oxygen'/> Oxygen is released. "
    "<bookmark mark='glucose'/> Glucose stores the captured energy.",
    "equation": "<bookmark mark='cleanup'/> The whole idea can be summarized with one equation. "
    "<bookmark mark='equation'/> Six carbon dioxide plus six water, with light, "
    "produce glucose and six oxygen. <bookmark mark='box'/> "
    "<bookmark mark='note'/> The energy ends up stored in chemical bonds.",
}


def strip_bookmarks(text: str) -> str:
    return BOOKMARK_RE.sub("", text)


async def synthesize_voiceovers(
    audio_dir: Path, *, regenerate: bool, voice: str
) -> dict[str, Path]:
    audio_dir.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}
    for name, script in SCRIPTS.items():
        path = audio_dir / f"photosynthesis_scene_{name}.mp3"
        paths[name] = path
        if path.exists() and not regenerate:
            continue
        communicate = edge_tts.Communicate(strip_bookmarks(script), voice, rate="+6%")
        await communicate.save(str(path))
    return paths


def make_text(
    text: str,
    position: tuple[float, float],
    font_size: int,
    color: tuple[float, float, float],
    *,
    align: str = "center",
) -> Text:
    return Text(
        text=text,
        position=position,
        font_size=font_size,
        align=align,
        stroke_style=StrokeStyle(color=color, width=max(font_size / 26, 1.4)),
        sketch_style=SKETCH,
    )


def molecule(
    label: str,
    center: tuple[float, float],
    radius: float,
    color: tuple[float, float, float],
) -> DrawableGroup:
    ring = Circle(
        center=center,
        radius=radius,
        stroke_style=StrokeStyle(color=color, width=2.3),
        fill_style=FillStyle(color=color, opacity=0.28, hachure_gap=10),
        sketch_style=SKETCH,
    )
    text = make_text(label, center, int(radius * 1.8), EMPHASIS)
    return DrawableGroup([ring, text])


def build_scene(audio_paths: dict[str, Path], *, voiceover_volume: float) -> Scene:
    scene = Scene(width=1280, height=720, fps=24, background_color=BACKGROUND)
    scene.set_viewport_to_identity()

    title = make_text("Photosynthesis", (640, 72), 54, EMPHASIS)
    intro_text = make_text(
        "The process of converting light into energy.",
        (640, 145),
        30,
        PRIMARY_TEXT,
    )

    leaf_center = (640, 360)
    leaf_shape = Ellipse(
        center=leaf_center,
        width=420,
        height=210,
        stroke_style=StrokeStyle(color=ACCENT_GREEN, width=2.8),
        fill_style=FillStyle(color=ACCENT_GREEN, opacity=0.20, hachure_gap=16),
        sketch_style=SKETCH,
    )
    leaf_main_vein = Line(
        start=(455, 360),
        end=(825, 360),
        stroke_style=StrokeStyle(color=ACCENT_GREEN, width=2.2),
        sketch_style=SKETCH,
    )
    leaf_side_veins = DrawableGroup(
        [
            Line(
                (520, 360),
                (585, 295),
                stroke_style=StrokeStyle(color=ACCENT_GREEN, width=1.7),
                sketch_style=SKETCH,
            ),
            Line(
                (585, 360),
                (640, 300),
                stroke_style=StrokeStyle(color=ACCENT_GREEN, width=1.7),
                sketch_style=SKETCH,
            ),
            Line(
                (695, 360),
                (760, 300),
                stroke_style=StrokeStyle(color=ACCENT_GREEN, width=1.7),
                sketch_style=SKETCH,
            ),
            Line(
                (520, 360),
                (585, 425),
                stroke_style=StrokeStyle(color=ACCENT_GREEN, width=1.7),
                sketch_style=SKETCH,
            ),
            Line(
                (585, 360),
                (640, 420),
                stroke_style=StrokeStyle(color=ACCENT_GREEN, width=1.7),
                sketch_style=SKETCH,
            ),
            Line(
                (695, 360),
                (760, 420),
                stroke_style=StrokeStyle(color=ACCENT_GREEN, width=1.7),
                sketch_style=SKETCH,
            ),
        ]
    )
    leaf_group = DrawableGroup([leaf_shape, leaf_main_vein, leaf_side_veins])
    leaf_label = make_text("Plant Leaf", (640, 212), 28, ACCENT_GREEN)

    sun_center = (145, 125)
    sun_core = Circle(
        center=sun_center,
        radius=36,
        stroke_style=StrokeStyle(color=SUN_YELLOW, width=2.4),
        fill_style=FillStyle(color=SUN_YELLOW, opacity=0.45, hachure_gap=10),
        sketch_style=SKETCH,
    )
    sun_rays = DrawableGroup(
        [
            Line(
                start=sun_center,
                end=(sun_center[0] + math.cos(angle) * 70, sun_center[1] + math.sin(angle) * 70),
                stroke_style=StrokeStyle(color=SUN_YELLOW, width=1.8),
                sketch_style=SKETCH,
            )
            for angle in [index * math.pi / 4 for index in range(8)]
        ]
    )
    sun_group = DrawableGroup([sun_core, sun_rays])
    sun_label = make_text("Sunlight (Energy)", (175, 205), 24, SUN_YELLOW)
    ray1 = Arrow(
        start_point=(190, 160),
        end_point=(470, 290),
        arrow_head_size=18,
        stroke_style=StrokeStyle(color=SUN_YELLOW, width=2.3),
        sketch_style=SKETCH,
    )
    ray2 = Arrow(
        start_point=(195, 170),
        end_point=(570, 320),
        arrow_head_size=18,
        stroke_style=StrokeStyle(color=SUN_YELLOW, width=2.3),
        sketch_style=SKETCH,
    )
    ray_group = DrawableGroup([ray1, ray2])

    co2_group = DrawableGroup(
        [
            molecule("CO2", (900, 235), 28, ACCENT_ORANGE),
            molecule("CO2", (1000, 285), 28, ACCENT_ORANGE),
            molecule("CO2", (1090, 345), 28, ACCENT_ORANGE),
        ]
    )
    co2_absorbed_group = DrawableGroup(
        [
            molecule("CO2", (610, 335), 17, ACCENT_ORANGE),
            molecule("CO2", (655, 355), 17, ACCENT_ORANGE),
            molecule("CO2", (700, 378), 17, ACCENT_ORANGE),
        ]
    )
    co2_label = make_text("Carbon Dioxide", (1000, 172), 24, ACCENT_ORANGE)

    water_arrow = Arrow(
        start_point=(640, 675),
        end_point=(640, 470),
        arrow_head_size=20,
        stroke_style=StrokeStyle(color=ACCENT_BLUE, width=7.0),
        sketch_style=SKETCH,
    )
    water_label = make_text("Water (H2O)", (500, 605), 24, ACCENT_BLUE)
    water_group = DrawableGroup([water_arrow, water_label])

    o2_group = DrawableGroup(
        [
            molecule("O2", (1030, 285), 26, EMPHASIS),
            molecule("O2", (1110, 350), 26, EMPHASIS),
            molecule("O2", (1030, 415), 26, EMPHASIS),
        ]
    )
    o2_label = make_text("Oxygen Released", (1075, 220), 24, EMPHASIS)
    glucose_text = make_text("Glucose (Sugar)", (650, 438), 32, ACCENT_GREEN)

    equation = Math(
        tex_expression=r"$6CO_2 + 6H_2O + \mathrm{Light} \rightarrow C_6H_{12}O_6 + 6O_2$",
        position=(640, 355),
        font_size=42,
        stroke_style=StrokeStyle(color=PRIMARY_TEXT, width=2.2),
        sketch_style=SKETCH,
    )
    equation_box = Rectangle(
        top_left=(170, 270),
        width=940,
        height=170,
        stroke_style=StrokeStyle(color=ACCENT_GREEN, width=2.6),
        sketch_style=SKETCH,
    )
    final_note = make_text("Energy stored in chemical bonds.", (640, 540), 28, ACCENT_GREEN)

    with scene.voiceover(
        str(audio_paths["intro"]), text=SCRIPTS["intro"], volume=voiceover_volume
    ) as tracker:
        title_time = tracker.bookmark_time("title")
        subtitle_time = tracker.bookmark_time("subtitle")
        scene.add(SketchAnimation(start_time=title_time, duration=1.3), title)
        scene.add(FadeInAnimation(start_time=subtitle_time, duration=1.0), intro_text)
    scene.advance_timeline(0.4)

    with scene.voiceover(
        str(audio_paths["leaf"]), text=SCRIPTS["leaf"], volume=voiceover_volume
    ) as tracker:
        scene.add(
            FadeOutAnimation(start_time=tracker.bookmark_time("fade_intro"), duration=0.8),
            intro_text,
        )
        leaf_time = tracker.bookmark_time("leaf")
        scene.add(SketchAnimation(start_time=leaf_time, duration=1.8), leaf_group)
        scene.add(FadeInAnimation(start_time=leaf_time + 0.2, duration=0.8), leaf_label)
    scene.advance_timeline(0.4)

    with scene.voiceover(
        str(audio_paths["sunlight"]), text=SCRIPTS["sunlight"], volume=voiceover_volume
    ) as tracker:
        sun_time = tracker.bookmark_time("sun")
        rays_time = tracker.bookmark_time("rays")
        scene.add(FadeInAnimation(start_time=sun_time, duration=0.9), sun_group)
        scene.add(FadeInAnimation(start_time=sun_time + 0.15, duration=0.8), sun_label)
        scene.add(SketchAnimation(start_time=rays_time, duration=1.2), ray_group)
    scene.advance_timeline(0.4)

    with scene.voiceover(
        str(audio_paths["inputs"]), text=SCRIPTS["inputs"], volume=voiceover_volume
    ) as tracker:
        co2_time = tracker.bookmark_time("co2")
        absorb_time = tracker.bookmark_time("absorb")
        water_time = tracker.bookmark_time("water")
        scene.add(FadeInAnimation(start_time=co2_time, duration=1.0), co2_group)
        scene.add(FadeInAnimation(start_time=co2_time + 0.2, duration=0.8), co2_label)
        scene.add(
            TransformAnimation(
                target_drawable=co2_absorbed_group,
                start_time=absorb_time,
                duration=2.2,
            ),
            co2_group,
        )
        scene.add(FadeOutAnimation(start_time=absorb_time + 1.5, duration=0.7), co2_group)
        scene.add(SketchAnimation(start_time=water_time, duration=1.2), water_arrow)
        scene.add(FadeInAnimation(start_time=water_time + 0.15, duration=0.8), water_label)
    scene.advance_timeline(0.4)

    with scene.voiceover(
        str(audio_paths["outputs"]), text=SCRIPTS["outputs"], volume=voiceover_volume
    ) as tracker:
        fade_labels_time = tracker.bookmark_time("fade_labels")
        oxygen_time = tracker.bookmark_time("oxygen")
        glucose_time = tracker.bookmark_time("glucose")
        scene.add(FadeOutAnimation(start_time=fade_labels_time, duration=0.8), co2_label)
        scene.add(FadeOutAnimation(start_time=fade_labels_time, duration=0.8), water_label)
        scene.add(FadeOutAnimation(start_time=fade_labels_time, duration=0.8), sun_label)
        scene.add(
            TranslateFromAnimation(
                start_time=oxygen_time,
                duration=2.4,
                data={"point": leaf_center},
            ),
            o2_group,
        )
        scene.add(FadeInAnimation(start_time=oxygen_time, duration=0.8), o2_group)
        scene.add(FadeInAnimation(start_time=oxygen_time + 1.2, duration=0.8), o2_label)
        scene.add(FadeInAnimation(start_time=glucose_time, duration=0.7), glucose_text)
        scene.add(ScaleInPlace(1.15, start_time=glucose_time, duration=1.4), glucose_text)
    scene.advance_timeline(0.5)

    with scene.voiceover(
        str(audio_paths["equation"]), text=SCRIPTS["equation"], volume=voiceover_volume
    ) as tracker:
        cleanup_time = tracker.bookmark_time("cleanup")
        equation_time = tracker.bookmark_time("equation")
        box_time = tracker.bookmark_time("box")
        note_time = tracker.bookmark_time("note")
        cleanup_drawables = [
            leaf_group,
            leaf_label,
            sun_group,
            ray_group,
            water_group,
            o2_group,
            o2_label,
            glucose_text,
        ]
        for drawable in cleanup_drawables:
            scene.add(FadeOutAnimation(start_time=cleanup_time, duration=1.0), drawable)
        scene.add(SketchAnimation(start_time=equation_time, duration=2.0), equation)
        scene.add(SketchAnimation(start_time=box_time, duration=0.9), equation_box)
        scene.add(FadeInAnimation(start_time=note_time, duration=0.9), final_note)

    return scene


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--regenerate-audio", action="store_true")
    parser.add_argument("--voice", default=VOICE)
    parser.add_argument("--volume", type=float, default=VOICEOVER_VOLUME)
    args = parser.parse_args()

    output_dir = ROOT / "examples" / "output"
    audio_dir = output_dir / "photosynthesis_scene_audio"
    output_path = output_dir / "photosynthesis_scene_audio.mp4"

    sys.stdout.write(f"Generating narration with {args.voice}...\n")
    audio_paths = asyncio.run(
        synthesize_voiceovers(audio_dir, regenerate=args.regenerate_audio, voice=args.voice)
    )
    sys.stdout.write(f"Rendering synced demo to {output_path}...\n")
    build_scene(audio_paths, voiceover_volume=args.volume).render(str(output_path))
    sys.stdout.write(f"Done: {output_path}\n")


if __name__ == "__main__":
    main()
