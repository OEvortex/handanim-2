import math
import os

from handanim.animations import (
    ApplyComplexFunction,
    ApplyMatrix,
    ApplyMethod,
    ClockwiseTransform,
    CounterclockwiseTransform,
    FadeInAnimation,
    FadeToColor,
    FadeTransformPieces,
    MoveToTarget,
    Restore,
    ScaleInPlace,
    ShrinkToCenter,
    Swap,
    TransformAnimations,
    TransformFromCopy,
)
from handanim.core import DrawableGroup, Scene, SketchStyle, StrokeStyle
from handanim.primitives import Circle, Line, Square, Text
from handanim.stylings.color import BLACK, BLUE, PASTEL_BLUE, PASTEL_GREEN, PASTEL_ORANGE, WHITE


def label(text: str, position: tuple[float, float], sketch: SketchStyle) -> Text:
    return Text(
        text=text,
        position=position,
        font_size=34,
        stroke_style=StrokeStyle(color=BLUE, width=2.1),
        sketch_style=sketch,
    )


def build_scene() -> Scene:
    scene = Scene(width=1920, height=1080, fps=24, background_color=WHITE)
    stroke = StrokeStyle(color=BLACK, width=2.6)
    sketch = SketchStyle(roughness=1.0, bowing=1.0, disable_font_mixture=True)

    title = Text(
        text="New Transform Animation Showcase",
        position=(960, 80),
        font_size=72,
        stroke_style=StrokeStyle(color=BLUE, width=2.5),
        sketch_style=sketch,
    )

    cw_source = Circle(center=(220, 280), radius=68, stroke_style=stroke, sketch_style=sketch)
    cw_target = Square(top_left=(152, 212), side_length=136, stroke_style=stroke, sketch_style=sketch)
    ccw_source = Square(top_left=(602, 212), side_length=136, stroke_style=stroke, sketch_style=sketch)
    ccw_target = Circle(center=(670, 280), radius=68, stroke_style=stroke, sketch_style=sketch)
    pieces_source = DrawableGroup(
        elements=[
            Text(text="A", position=(1110, 280), font_size=90, stroke_style=stroke, sketch_style=sketch),
            Text(text="+", position=(1210, 280), font_size=90, stroke_style=stroke, sketch_style=sketch),
            Text(text="B", position=(1310, 280), font_size=90, stroke_style=stroke, sketch_style=sketch),
        ]
    )
    pieces_target = DrawableGroup(
        elements=[
            Text(text="x", position=(1110, 280), font_size=90, stroke_style=stroke, sketch_style=sketch),
            Text(text="•", position=(1210, 280), font_size=90, stroke_style=stroke, sketch_style=sketch),
            Text(text="y", position=(1310, 280), font_size=90, stroke_style=stroke, sketch_style=sketch),
        ]
    )

    mover = Circle(center=(220, 610), radius=54, stroke_style=stroke, sketch_style=sketch)
    mover.save_state()
    mover.generate_target()
    mover.target = mover.target.translate(130, -40).scale(1.25, 1.25)

    method_square = Square(top_left=(575, 545), side_length=110, stroke_style=stroke, sketch_style=sketch)
    copy_source = Circle(center=(1130, 610), radius=48, stroke_style=stroke, sketch_style=sketch)
    copy_target = Square(top_left=(1235, 560), side_length=96, stroke_style=stroke, sketch_style=sketch)

    matrix_line = Line(start=(150, 900), end=(360, 900), stroke_style=stroke, sketch_style=sketch)
    complex_line = Line(start=(560, 900), end=(760, 900), stroke_style=stroke, sketch_style=sketch)
    swap_left = Circle(center=(1100, 900), radius=42, stroke_style=stroke, sketch_style=sketch)
    swap_right = Circle(center=(1270, 900), radius=42, stroke_style=stroke, sketch_style=sketch)
    transform_line = Line(start=(1500, 900), end=(1680, 900), stroke_style=stroke, sketch_style=sketch)

    labels = DrawableGroup(
        elements=[
            label("ClockwiseTransform", (220, 170), sketch),
            label("CounterclockwiseTransform", (670, 170), sketch),
            label("FadeTransformPieces", (1210, 170), sketch),
            label("MoveToTarget + Restore", (260, 500), sketch),
            label("ApplyMethod + FadeToColor + ShrinkToCenter", (700, 500), sketch),
            label("TransformFromCopy", (1210, 500), sketch),
            label("ApplyMatrix", (255, 790), sketch),
            label("ApplyComplexFunction", (660, 790), sketch),
            label("Swap", (1185, 790), sketch),
            label("TransformAnimations", (1590, 790), sketch),
        ]
    )

    scene.add(FadeInAnimation(start_time=0.0, duration=0.4), title)
    scene.add(FadeInAnimation(start_time=0.15, duration=0.3), labels)

    scene.add(FadeInAnimation(start_time=0.3, duration=0.2), cw_source)
    scene.add(ClockwiseTransform(target_drawable=cw_target, start_time=0.55, duration=1.5), cw_source)
    scene.add(FadeInAnimation(start_time=0.45, duration=0.2), ccw_source)
    scene.add(CounterclockwiseTransform(target_drawable=ccw_target, start_time=0.7, duration=1.5), ccw_source)
    scene.add(FadeInAnimation(start_time=0.55, duration=0.2), pieces_source)
    scene.add(FadeTransformPieces(target_drawable=pieces_target, start_time=0.9, duration=1.5), pieces_source)

    scene.add(FadeInAnimation(start_time=2.4, duration=0.2), mover)
    scene.add(MoveToTarget(start_time=2.65, duration=1.1), mover)
    scene.add(Restore(start_time=3.9, duration=0.9), mover)

    scene.add(FadeInAnimation(start_time=2.45, duration=0.2), method_square)
    scene.add(ApplyMethod(method_square.rotate, math.pi / 4, start_time=2.8, duration=1.0), method_square)
    scene.add(FadeToColor(PASTEL_ORANGE, start_time=3.3, duration=0.8), method_square)
    scene.add(ShrinkToCenter(start_time=4.25, duration=0.7), method_square)

    scene.add(FadeInAnimation(start_time=2.55, duration=0.2), copy_source)
    scene.add(TransformFromCopy(copy_source, copy_target, start_time=2.95, duration=1.4))
    scene.add(FadeToColor(PASTEL_GREEN, start_time=4.2, duration=0.7), copy_target)

    scene.add(FadeInAnimation(start_time=5.0, duration=0.2), matrix_line)
    scene.add(ApplyMatrix([[1, 0, 20], [0.35, 1, -120]], start_time=5.25, duration=1.1), matrix_line)
    scene.add(FadeInAnimation(start_time=5.1, duration=0.2), complex_line)
    scene.add(
        ApplyComplexFunction(
            lambda z: (z - complex(660, 900)) * 1j + complex(660, 900),
            start_time=5.35,
            duration=1.1,
        ),
        complex_line,
    )

    scene.add(FadeInAnimation(start_time=5.15, duration=0.2), swap_left)
    scene.add(FadeInAnimation(start_time=5.15, duration=0.2), swap_right)
    scene.add(Swap(swap_left, swap_right, start_time=5.5, duration=1.2, path_arc=math.pi / 2))

    scene.add(FadeInAnimation(start_time=5.2, duration=0.2), transform_line)
    scene.add(
        TransformAnimations(
            start_animation=ScaleInPlace(0.55, source_drawable=transform_line, start_time=0.0, duration=0.0),
            end_animation=ApplyMatrix([[0, -1], [1, 0]], source_drawable=transform_line, start_time=0.0, duration=0.0),
            source_drawable=transform_line,
            start_time=5.7,
            duration=1.3,
        )
    )
    scene.add(FadeToColor(PASTEL_BLUE, start_time=7.0, duration=0.7), transform_line)
    return scene


def main() -> None:
    output_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "output")
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "transform_showcase.mp4")
    print(f"Rendering transform showcase to {output_path}...")
    build_scene().render(output_path, max_length=8.2)


if __name__ == "__main__":
    main()