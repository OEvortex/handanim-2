import math
import os

from handanim.animations import FadeInAnimation, ReplacementTransformAnimation, TransformAnimation
from handanim.core import DrawableGroup, FillStyle, Scene, SketchStyle, StrokeStyle
from handanim.primitives import Circle, Math, Square, Text
from handanim.stylings.color import BLACK, BLUE, PASTEL_BLUE, PASTEL_ORANGE, WHITE


def build_scene() -> Scene:
    scene = Scene(width=1920, height=1080, fps=24, background_color=WHITE)
    stroke = StrokeStyle(color=BLACK, width=2.6)
    sketch = SketchStyle(roughness=1.0, bowing=1.0, disable_font_mixture=True)

    title = Text(
        text="Morph Animation Demo",
        position=(910, 95),
        font_size=80,
        stroke_style=StrokeStyle(color=BLUE, width=2.5),
        sketch_style=sketch,
    )

    circle = Circle(
        center=(430, 540),
        radius=130,
        stroke_style=stroke,
        sketch_style=sketch,
        fill_style=FillStyle(color=PASTEL_BLUE, opacity=0.35, hachure_gap=10),
    )
    square = Square(
        top_left=(300, 410),
        side_length=260,
        stroke_style=stroke,
        sketch_style=sketch,
        fill_style=FillStyle(color=PASTEL_ORANGE, opacity=0.35, hachure_gap=10),
    )

    formula_start = Math(
        tex_expression=r"$a^2 + b^2 = c^2$",
        position=(930, 500),
        font_size=115,
        stroke_style=stroke,
        sketch_style=sketch,
    )
    formula_end = Math(
        tex_expression=r"$c = \sqrt{a^2 + b^2}$",
        position=(930, 500),
        font_size=115,
        stroke_style=stroke,
        sketch_style=sketch,
    )
    group_start = DrawableGroup(
        elements=[
            Math(tex_expression=r"$x$", position=(1030, 800), font_size=100, stroke_style=stroke),
            Math(tex_expression=r"$y$", position=(1350, 800), font_size=100, stroke_style=stroke),
        ]
    )
    group_end = DrawableGroup(
        elements=[
            Square(top_left=(980, 735), side_length=120, stroke_style=stroke, sketch_style=sketch),
            Circle(center=(1410, 800), radius=68, stroke_style=stroke, sketch_style=sketch),
            Math(tex_expression=r"$x+y$", position=(1188, 800), font_size=92, stroke_style=stroke),
        ]
    )

    scene.add(FadeInAnimation(start_time=0, duration=0.5), drawable=title)
    scene.add(FadeInAnimation(start_time=0.2, duration=0.4), drawable=circle)
    scene.add(
        TransformAnimation(
            target_drawable=square,
            start_time=0.7,
            duration=2.2,
            path_arc=math.pi / 4,
        ),
        drawable=circle,
    )

    scene.add(FadeInAnimation(start_time=3.1, duration=0.5), drawable=formula_start)
    scene.add(
        ReplacementTransformAnimation(
            target_drawable=formula_end,
            start_time=3.7,
            duration=2.4,
            path_arc=-math.pi / 8,
        ),
        drawable=formula_start,
    )
    scene.add(FadeInAnimation(start_time=4.7, duration=0.3), drawable=group_start)
    scene.add(
        ReplacementTransformAnimation(
            target_drawable=group_end,
            start_time=5.0,
            duration=1.8,
            path_arc=math.pi / 10,
        ),
        drawable=group_start,
    )
    return scene


def main() -> None:
    output_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "output")
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "morph_demo.mp4")
    print(f"Rendering morph demo to {output_path}...")
    build_scene().render(output_path, max_length=7.4)


if __name__ == "__main__":
    main()

