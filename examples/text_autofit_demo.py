import os

from handanim.animations import FadeInAnimation, SketchAnimation
from handanim.core import Scene, StrokeStyle
from handanim.primitives import Rectangle, Text
from handanim.stylings.color import BLACK, BLUE, GREEN, ORANGE, WHITE


def main() -> None:
    scene = Scene(width=1280, height=720, fps=24, background_color=BLACK)

    title = Text(
        text="Text Autofit + Alignment",
        position=(640, 85),
        font_size=54,
        stroke_style=StrokeStyle(color=BLUE, width=2.5),
    )

    boxes = [
        ((70, 180, 320, 180), "left", GREEN),
        ((480, 180, 320, 180), "center", WHITE),
        ((890, 180, 320, 180), "right", ORANGE),
    ]
    text_value = "Multiline text\nfits the box\nand stays aligned"

    scene.add(FadeInAnimation(start_time=0, duration=0.5), drawable=title)
    for index, (box_rect, align, color) in enumerate(boxes):
        rect = Rectangle(
            top_left=(box_rect[0], box_rect[1]),
            width=box_rect[2],
            height=box_rect[3],
            stroke_style=StrokeStyle(color=color, width=2),
        )
        layout_text = Text(
            text=text_value,
            position=(0, 0),
            font_size=64,
            rect_box=box_rect,
            rect_padding=16,
            align=align,
            line_spacing=1.2,
            stroke_style=StrokeStyle(color=color, width=1.8),
        )

        start_time = 0.6 + index * 1.2
        scene.add(SketchAnimation(start_time=start_time, duration=0.8), drawable=rect)
        scene.add(SketchAnimation(start_time=start_time + 0.3, duration=1.6), drawable=layout_text)

    output_path = os.path.join("examples", "output", "text_autofit_demo.mp4")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    print(f"Rendering example to {output_path}...")
    scene.render(output_path, max_length=6)


if __name__ == "__main__":
    main()

