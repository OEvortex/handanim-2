"""Demo showing TTS integration in scene.add() and scene.group() - no separate add_audio needed."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from handanim.animations import FadeInAnimation, SketchAnimation
from handanim.core import FillStyle, Scene, StrokeStyle
from handanim.primitives import Rectangle, Text
from handanim.stylings.color import BLACK, BLUE, ORANGE, PASTEL_BLUE, WHITE

try:
    import edge_tts
except ImportError:
    print("Install edge-tts first: uv add --dev edge-tts")
    sys.exit(1)


def build_scene() -> Scene:
    scene = Scene(width=1280, height=720, fps=24, background_color=WHITE)
    scene.set_viewport_to_identity()

    title = Text(
        text="TTS in add() Demo",
        position=(640, 200),
        font_size=54,
        stroke_style=StrokeStyle(color=BLUE, width=2.4),
    )
    subtitle = Text(
        text="No separate add_audio() - just use add() with TTS!",
        position=(640, 280),
        font_size=28,
        stroke_style=StrokeStyle(color=BLACK, width=1.6),
    )
    panel = Rectangle(
        top_left=(200, 350),
        width=880,
        height=200,
        stroke_style=StrokeStyle(color=ORANGE, width=2.4),
        fill_style=FillStyle(color=PASTEL_BLUE, opacity=0.16, hachure_gap=18),
    )
    bullet1 = Text(
        text="1. Audio auto-advances timeline",
        position=(640, 400),
        font_size=32,
        stroke_style=StrokeStyle(color=BLACK, width=2.0),
    )
    bullet2 = Text(
        text="2. Group multiple scenes with one audio",
        position=(640, 450),
        font_size=32,
        stroke_style=StrokeStyle(color=BLACK, width=2.0),
    )
    bullet3 = Text(
        text="3. No overlapping audio issues",
        position=(640, 500),
        font_size=32,
        stroke_style=StrokeStyle(color=BLACK, width=2.0),
    )

    # Single animation with TTS - auto-waits for audio to finish
    scene.add(
        event=SketchAnimation(start_time=0.0, duration=1.0),
        drawable=title,
        tts_provider=edge_tts,
        speech="This demo shows TTS integrated directly into add().",
        voice="en-US-JennyNeural",
        rate="+8%",
    )

    # Another animation - timeline auto-advanced after previous audio
    scene.add(
        event=FadeInAnimation(start_time=scene.timeline_cursor, duration=0.7),
        drawable=subtitle,
        tts_provider=edge_tts,
        speech="No separate audio function needed. Timeline auto-advances.",
        voice="en-US-JennyNeural",
        rate="+8%",
    )

    # Group multiple animations with single audio
    with scene.group(
        tts_provider=edge_tts,
        speech="You can group multiple animations together with one audio track. All animations in this group share the same voiceover.",
        voice="en-US-JennyNeural",
        rate="+8%",
    ):
        scene.add(SketchAnimation(start_time=0.0, duration=1.2), drawable=panel)
        scene.add(SketchAnimation(start_time=0.3, duration=0.8), drawable=bullet1)
        scene.add(SketchAnimation(start_time=0.6, duration=0.8), drawable=bullet2)
        scene.add(SketchAnimation(start_time=0.9, duration=0.8), drawable=bullet3)

    return scene


def main() -> None:
    output_dir = ROOT / "examples" / "output"
    output_path = output_dir / "tts_in_add_demo.mp4"
    output_dir.mkdir(parents=True, exist_ok=True)

    sys.stdout.write("Building scene with TTS in add() and group()...\n")
    scene = build_scene()
    sys.stdout.write(f"Rendering to {output_path}...\n")
    scene.render(str(output_path))
    sys.stdout.write(f"Done: {output_path}\n")


if __name__ == "__main__":
    main()
