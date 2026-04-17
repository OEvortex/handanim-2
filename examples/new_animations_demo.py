import os

from handanim.animations import (
    BounceInAnimation,
    BounceOutAnimation,
    FlashAnimation,
    GrowFromCenterAnimation,
    JitterAnimation,
    PulseAnimation,
    RotateAnimation,
    ScaleFromPointAnimation,
    ShrinkToPointAnimation,
    SlideAnimation,
    SlideInAnimation,
    SlideOutAnimation,
    SpinAnimation,
    WiggleAnimation,
)
from handanim.core import DrawableGroup, Scene, SketchStyle, StrokeStyle
from handanim.primitives import Circle, Square, Text
from handanim.stylings.color import BLACK, BLUE, GREEN, ORANGE, PASTEL_BLUE, PASTEL_GREEN, PASTEL_ORANGE, WHITE


def build_scene() -> Scene:
    scene = Scene(width=1920, height=1080, fps=24, background_color=WHITE)
    stroke = StrokeStyle(color=BLACK, width=2.6)
    sketch = SketchStyle(roughness=1.0, bowing=1.0, disable_font_mixture=True)

    # Title
    title = Text(
        text="New Animations Demo",
        position=(760, 90),
        font_size=80,
        stroke_style=StrokeStyle(color=BLUE, width=2.5),
        sketch_style=sketch,
    )

    # Row 1: Rotate and Scale animations
    rotate_circle = Circle(center=(320, 360), radius=70, stroke_style=stroke, sketch_style=sketch)
    spin_square = Square(top_left=(570, 290), side_length=140, stroke_style=stroke, sketch_style=sketch)
    grow_circle = Circle(center=(960, 360), radius=70, stroke_style=stroke, sketch_style=sketch)
    shrink_square = Square(top_left=(1210, 290), side_length=140, stroke_style=stroke, sketch_style=sketch)

    # Row 2: Bounce and Effects animations
    bounce_circle = Circle(center=(320, 720), radius=70, stroke_style=stroke, sketch_style=sketch)
    pulse_square = Square(top_left=(570, 650), side_length=140, stroke_style=stroke, sketch_style=sketch)
    wiggle_circle = Circle(center=(960, 720), radius=70, stroke_style=stroke, sketch_style=sketch)
    flash_square = Square(top_left=(1210, 650), side_length=140, stroke_style=stroke, sketch_style=sketch)

    # Row 3: Slide and Jitter animations
    slide_in_circle = Circle(center=(320, 900), radius=70, stroke_style=stroke, sketch_style=sketch)
    slide_out_square = Square(top_left=(570, 830), side_length=140, stroke_style=stroke, sketch_style=sketch)
    jitter_circle = Circle(center=(960, 900), radius=70, stroke_style=stroke, sketch_style=sketch)
    scale_from_point = Circle(center=(1210, 900), radius=70, stroke_style=stroke, sketch_style=sketch)

    # Labels
    labels = DrawableGroup(
        elements=[
            Text(text="RotateAnimation", position=(320, 200), font_size=32, stroke_style=stroke, sketch_style=sketch),
            Text(text="SpinAnimation", position=(640, 200), font_size=32, stroke_style=stroke, sketch_style=sketch),
            Text(text="GrowFromCenter", position=(960, 200), font_size=32, stroke_style=stroke, sketch_style=sketch),
            Text(text="ShrinkToPoint", position=(1280, 200), font_size=32, stroke_style=stroke, sketch_style=sketch),
            Text(text="BounceInAnimation", position=(320, 560), font_size=32, stroke_style=stroke, sketch_style=sketch),
            Text(text="PulseAnimation", position=(640, 560), font_size=32, stroke_style=stroke, sketch_style=sketch),
            Text(text="WiggleAnimation", position=(960, 560), font_size=32, stroke_style=stroke, sketch_style=sketch),
            Text(text="FlashAnimation", position=(1280, 560), font_size=32, stroke_style=stroke, sketch_style=sketch),
            Text(text="SlideInAnimation", position=(320, 740), font_size=32, stroke_style=stroke, sketch_style=sketch),
            Text(text="SlideOutAnimation", position=(640, 740), font_size=32, stroke_style=stroke, sketch_style=sketch),
            Text(text="JitterAnimation", position=(960, 740), font_size=32, stroke_style=stroke, sketch_style=sketch),
            Text(text="ScaleFromPoint", position=(1280, 740), font_size=32, stroke_style=stroke, sketch_style=sketch),
        ]
    )

    # Add title and labels
    scene.add(GrowFromCenterAnimation(start_time=0.0, duration=0.5), title)
    scene.add(GrowFromCenterAnimation(start_time=0.2, duration=0.3), labels)

    # Row 1: Rotate and Scale
    scene.add(GrowFromCenterAnimation(start_time=0.5, duration=0.4), rotate_circle)
    scene.add(RotateAnimation(angle=3.14159, center=(320, 360), start_time=1.0, duration=1.5), rotate_circle)

    scene.add(GrowFromCenterAnimation(start_time=0.6, duration=0.4), spin_square)
    scene.add(SpinAnimation(rotations=1.5, start_time=1.1, duration=1.5), spin_square)

    scene.add(GrowFromCenterAnimation(start_time=0.7, duration=0.4), grow_circle)
    scene.add(GrowFromCenterAnimation(scale_factor=1.5, start_time=1.2, duration=1.0), grow_circle)

    scene.add(GrowFromCenterAnimation(start_time=0.8, duration=0.4), shrink_square)
    scene.add(ShrinkToPointAnimation(point=(1280, 360), start_time=1.3, duration=1.0), shrink_square)

    # Row 2: Bounce and Effects
    scene.add(BounceInAnimation(scale_factor=1.0, bounce_type="bounce", start_time=2.5, duration=0.8), bounce_circle)
    scene.add(BounceOutAnimation(bounce_type="bounce", start_time=3.5, duration=0.8), bounce_circle)

    scene.add(GrowFromCenterAnimation(start_time=2.6, duration=0.4), pulse_square)
    scene.add(PulseAnimation(scale_min=0.8, scale_max=1.3, cycles=2.0, start_time=3.2, duration=1.5), pulse_square)

    scene.add(GrowFromCenterAnimation(start_time=2.7, duration=0.4), wiggle_circle)
    scene.add(WiggleAnimation(angle=0.2, cycles=3.0, start_time=3.3, duration=1.5), wiggle_circle)

    scene.add(GrowFromCenterAnimation(start_time=2.8, duration=0.4), flash_square)
    scene.add(FlashAnimation(flash_color=PASTEL_ORANGE, start_time=3.4, duration=0.8), flash_square)

    # Row 3: Slide and Jitter
    scene.add(SlideInAnimation(direction="left", distance=500, start_time=4.8, duration=0.8), slide_in_circle)
    scene.add(SlideOutAnimation(direction="right", distance=500, start_time=5.8, duration=0.8), slide_in_circle)

    scene.add(GrowFromCenterAnimation(start_time=4.9, duration=0.4), slide_out_square)
    scene.add(SlideOutAnimation(direction="up", distance=300, start_time=5.4, duration=0.8), slide_out_square)

    scene.add(GrowFromCenterAnimation(start_time=5.0, duration=0.4), jitter_circle)
    scene.add(JitterAnimation(magnitude=10.0, seed=42, start_time=5.6, duration=1.0), jitter_circle)

    scene.add(ScaleFromPointAnimation(point=(1210, 900), scale_factor=1.2, start_time=5.1, duration=0.8), scale_from_point)

    return scene


def main() -> None:
    output_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "output")
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "new_animations_demo.mp4")
    print(f"Rendering new animations demo to {output_path}...")
    build_scene().render(output_path, max_length=7.0)


if __name__ == "__main__":
    main()
