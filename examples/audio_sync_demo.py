# ruff: noqa: E402
"""Generate narration with edge-tts and render a synced audio demo."""

from __future__ import annotations

import argparse
import asyncio
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

from handanim.animations import FadeInAnimation, SketchAnimation
from handanim.core import FillStyle, Scene, StrokeStyle
from handanim.primitives import Rectangle, Text
from handanim.stylings.color import BLACK, BLUE, ORANGE, PASTEL_BLUE, WHITE

BOOKMARK_RE = re.compile(r"<bookmark\s+(?:mark|name)\s*=\s*['\"][^'\"]+['\"]\s*/>")
VOICE = "en-US-JennyNeural"
VOICEOVER_VOLUME = 1.6
SCRIPTS = {
    "intro": "<bookmark mark='title'/> Built in audio sync for handanim. "
    "<bookmark mark='panel'/> The lesson panel appears as the narration continues.",
    "beats": "<bookmark mark='one'/> Audio lives on the scene. "
    "<bookmark mark='two'/> Bookmarks trigger the visuals. "
    "<bookmark mark='three'/> Rendering exports one synced video.",
}


def strip_bookmarks(text: str) -> str:
    return BOOKMARK_RE.sub("", text)


async def synthesize_voiceovers(
    audio_dir: Path, *, regenerate: bool, voice: str
) -> dict[str, Path]:
    audio_dir.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}
    for name, script in SCRIPTS.items():
        path = audio_dir / f"audio_sync_demo_{name}.mp3"
        paths[name] = path
        if path.exists() and not regenerate:
            continue
        communicate = edge_tts.Communicate(strip_bookmarks(script), voice, rate="+8%")
        await communicate.save(str(path))
    return paths


def build_scene(audio_paths: dict[str, Path], *, voiceover_volume: float) -> Scene:
    scene = Scene(width=1280, height=720, fps=24, background_color=WHITE)
    scene.set_viewport_to_identity()

    title = Text(
        text="Built-in Audio Sync",
        position=(640, 92),
        font_size=54,
        stroke_style=StrokeStyle(color=BLUE, width=2.4),
    )
    subtitle = Text(
        text="handanim voiceover + bookmarks + final muxed audio",
        position=(640, 145),
        font_size=24,
        stroke_style=StrokeStyle(color=BLACK, width=1.6),
    )
    panel = Rectangle(
        top_left=(120, 190),
        width=1040,
        height=360,
        stroke_style=StrokeStyle(color=ORANGE, width=2.4),
        fill_style=FillStyle(color=PASTEL_BLUE, opacity=0.16, hachure_gap=18),
    )
    bullets = [
        Text(
            "1. Audio is part of the scene timeline.",
            (640, 290),
            34,
            stroke_style=StrokeStyle(color=BLACK, width=2.0),
        ),
        Text(
            "2. Bookmarks choose when visuals begin.",
            (640, 380),
            34,
            stroke_style=StrokeStyle(color=BLACK, width=2.0),
        ),
        Text(
            "3. Rendering outputs one synced MP4.",
            (640, 470),
            34,
            stroke_style=StrokeStyle(color=BLACK, width=2.0),
        ),
    ]
    footer = Text(
        text="Generated with edge-tts and rendered by handanim.",
        position=(640, 640),
        font_size=24,
        stroke_style=StrokeStyle(color=BLUE, width=1.6),
    )

    with scene.voiceover(
        str(audio_paths["intro"]), text=SCRIPTS["intro"], volume=voiceover_volume
    ) as tracker:
        title_start = tracker.bookmark_time("title")
        panel_start = tracker.bookmark_time("panel")
        scene.add(SketchAnimation(start_time=title_start, duration=0.95), drawable=title)
        scene.add(FadeInAnimation(start_time=title_start + 0.35, duration=0.55), drawable=subtitle)
        scene.add(
            SketchAnimation(
                start_time=panel_start,
                duration=max(tracker.get_remaining_duration(from_time=panel_start), 0.8),
            ),
            drawable=panel,
        )

    with scene.voiceover(
        str(audio_paths["beats"]), text=SCRIPTS["beats"], volume=voiceover_volume
    ) as tracker:
        first = tracker.bookmark_time("one")
        second = tracker.bookmark_time("two")
        third = tracker.bookmark_time("three")
        scene.add(SketchAnimation(start_time=first, duration=0.9), drawable=bullets[0])
        scene.add(SketchAnimation(start_time=second, duration=0.9), drawable=bullets[1])
        scene.add(SketchAnimation(start_time=third, duration=0.9), drawable=bullets[2])
        scene.add(FadeInAnimation(start_time=third + 0.25, duration=0.7), drawable=footer)

    return scene


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--regenerate-audio", action="store_true")
    parser.add_argument("--voice", default=VOICE)
    parser.add_argument("--volume", type=float, default=VOICEOVER_VOLUME)
    args = parser.parse_args()

    output_dir = ROOT / "examples" / "output"
    audio_dir = output_dir / "audio_sync_demo_audio"
    output_path = output_dir / "audio_sync_demo.mp4"
    voice = args.voice
    volume = args.volume

    sys.stdout.write(f"Generating narration with {voice}...\n")
    audio_paths = asyncio.run(
        synthesize_voiceovers(audio_dir, regenerate=args.regenerate_audio, voice=voice)
    )
    sys.stdout.write(f"Rendering synced demo to {output_path}...\n")
    build_scene(audio_paths, voiceover_volume=volume).render(str(output_path))
    sys.stdout.write(f"Done: {output_path}\n")


if __name__ == "__main__":
    main()
