import os

from handanim.animations import FadeInAnimation, SketchAnimation
from handanim.core import FillStyle, Scene, SketchStyle, StrokeStyle
from handanim.primitives import Table, Text
from handanim.stylings.color import BLACK, BLUE, PASTEL_BLUE, PASTEL_GREEN, WHITE


def build_scene() -> Scene:
    scene = Scene(width=1920, height=1080, fps=24, background_color=WHITE)
    stroke = StrokeStyle(color=BLACK, width=2.5)
    sketch = SketchStyle(roughness=1.0, bowing=1.0, disable_font_mixture=True)

    title = Text(
        text="Table Example",
        position=(890, 95),
        font_size=82,
        stroke_style=StrokeStyle(color=BLUE, width=2.4),
        sketch_style=sketch,
    )

    table = Table(
        data=[
            ["Method", "Input", "Core Step", "Output"],
            ["Rule-based", "Structured data", "Deterministic rules", "Exact decision"],
            ["LLM", "Prompt text", "Reason over context", "Flexible answer"],
            ["Hybrid", "Data + prompt", "Route then reason", "Reliable response"],
        ],
        top_left=(250, 220),
        col_widths=[260, 260, 320, 280],
        row_heights=[110, 120, 120, 120],
        font_size=30,
        cell_padding=14,
        header_rows=1,
        stroke_style=stroke,
        sketch_style=sketch,
        fill_style=FillStyle(color=PASTEL_GREEN, opacity=0.35, hachure_gap=10),
        header_fill_style=FillStyle(color=PASTEL_BLUE, opacity=0.45, hachure_gap=10),
    )

    scene.add(event=FadeInAnimation(start_time=0, duration=0.6), drawable=title)
    scene.add(event=SketchAnimation(start_time=0.5, duration=3.4), drawable=table)
    return scene


def main() -> None:
    output_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "output")
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "table_demo.mp4")
    print(f"Rendering table demo to {output_path}...")
    build_scene().render(output_path, max_length=5)


if __name__ == "__main__":
    main()