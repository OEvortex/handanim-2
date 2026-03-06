import math
import os

from handanim.animations import (
    ApplyMethod,
    CyclicReplace,
    FadeInAnimation,
    FadeToColor,
    MoveToTarget,
    ReplacementTransform,
    Restore,
    ScaleInPlace,
    TransformFromCopy,
)
from handanim.core import DrawableGroup, Scene, SketchStyle, StrokeStyle
from handanim.primitives import Circle, Square, Text
from handanim.stylings.color import BLACK, BLUE, PASTEL_BLUE, PASTEL_GREEN, PASTEL_ORANGE, WHITE


def build_scene() -> Scene:
    scene = Scene(width=1920, height=1080, fps=24, background_color=WHITE)
    stroke = StrokeStyle(color=BLACK, width=2.6)
    sketch = SketchStyle(roughness=1.0, bowing=1.0, disable_font_mixture=True)

    title = Text(
        text="Transform Gallery",
        position=(860, 90),
        font_size=80,
        stroke_style=StrokeStyle(color=BLUE, width=2.5),
        sketch_style=sketch,
    )
    circle = Circle(center=(260, 360), radius=90, stroke_style=stroke, sketch_style=sketch)
    square = Square(top_left=(630, 270), side_length=180, stroke_style=stroke, sketch_style=sketch)
    source = Circle(center=(1090, 350), radius=70, stroke_style=stroke, sketch_style=sketch)
    target = Square(top_left=(1340, 280), side_length=140, stroke_style=stroke, sketch_style=sketch)
    top = Circle(center=(510, 760), radius=70, stroke_style=stroke, sketch_style=sketch)
    bottom = Circle(center=(790, 760), radius=70, stroke_style=stroke, sketch_style=sketch)
    labels = DrawableGroup(
        elements=[
            Text(text="MoveToTarget", position=(260, 200), font_size=42, stroke_style=stroke, sketch_style=sketch),
            Text(text="ReplacementTransform", position=(720, 200), font_size=42, stroke_style=stroke, sketch_style=sketch),
            Text(text="TransformFromCopy", position=(1250, 200), font_size=42, stroke_style=stroke, sketch_style=sketch),
            Text(text="CyclicReplace + ApplyMethod", position=(620, 620), font_size=42, stroke_style=stroke, sketch_style=sketch),
        ]
    )

    circle.save_state()
    circle.generate_target()
    circle.target = circle.target.translate(180, 0).scale(1.2, 1.2)

    scene.add(FadeInAnimation(start_time=0.0, duration=0.4), title)
    scene.add(FadeInAnimation(start_time=0.2, duration=0.3), labels)
    scene.add(FadeInAnimation(start_time=0.2, duration=0.3), circle)
    scene.add(FadeInAnimation(start_time=0.6, duration=0.3), square)
    scene.add(FadeInAnimation(start_time=1.0, duration=0.3), source)
    scene.add(FadeInAnimation(start_time=1.2, duration=0.3), top)
    scene.add(FadeInAnimation(start_time=1.2, duration=0.3), bottom)

    scene.add(MoveToTarget(start_time=0.6, duration=1.2), circle)
    scene.add(FadeToColor(PASTEL_BLUE, start_time=1.8, duration=0.7), circle)
    scene.add(Restore(start_time=2.7, duration=0.9), circle)

    scene.add(
        ReplacementTransform(
            target_drawable=Square(
                top_left=(630, 270),
                side_length=180,
                stroke_style=StrokeStyle(color=PASTEL_ORANGE, width=2.6),
                sketch_style=sketch,
            ).rotate(45),
            start_time=1.0,
            duration=1.6,
            path_arc=math.pi / 4,
        ),
        square,
    )

    scene.add(TransformFromCopy(source, target, start_time=1.5, duration=1.6))
    scene.add(FadeToColor(PASTEL_GREEN, start_time=3.2, duration=0.8), target)

    scene.add(CyclicReplace(top, bottom, start_time=2.1, duration=1.2, path_arc=math.pi / 2))
    scene.add(ApplyMethod(top.scale, 0.7, start_time=3.6, duration=0.8))
    scene.add(ApplyMethod(bottom.scale, 1.25, start_time=3.6, duration=0.8))

    return scene


def main() -> None:
    output_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "output")
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "transform_gallery.mp4")
    print(f"Rendering transform gallery to {output_path}...")
    build_scene().render(output_path, max_length=5.0)


if __name__ == "__main__":
    main()

