import os

from handanim.animations import FadeInAnimation, SketchAnimation
from handanim.core import Scene, StrokeStyle
from handanim.primitives import MathTex, Rectangle, Text
from handanim.stylings.color import BLACK, BLUE, GREEN, ORANGE, WHITE


def build_scene() -> Scene:
    scene = Scene(width=1280, height=720, fps=24, background_color=WHITE)

    title = Text(
        text="MathTex / LaTeX-style Demo",
        position=(640, 70),
        font_size=52,
        stroke_style=StrokeStyle(color=BLUE, width=2.4),
    )
    subtitle = Text(
        text="No explicit dollar delimiters needed",
        position=(640, 120),
        font_size=28,
        stroke_style=StrokeStyle(color=BLACK, width=1.6),
    )

    formula_1 = MathTex(
        r"\frac{a}{b} + \sqrt{x} = y",
        position=(320, 255),
        font_size=72,
        stroke_style=StrokeStyle(color=GREEN, width=1.8),
    )
    formula_2 = MathTex(
        r"\sum_{i=1}^{n} i = \frac{n(n+1)}{2}",
        position=(320, 400),
        font_size=66,
        stroke_style=StrokeStyle(color=ORANGE, width=1.8),
    )
    formula_3 = MathTex(
        r"\int_0^{\pi} \sin(x)\,dx = 2",
        position=(320, 545),
        font_size=70,
        stroke_style=StrokeStyle(color=BLUE, width=1.8),
    )

    formula_box = Rectangle(
        top_left=(740, 220),
        width=430,
        height=250,
        stroke_style=StrokeStyle(color=BLACK, width=2.0),
    )
    fitted_formula = MathTex(
        r"\sum_{k=1}^{20} k^2 = \frac{20\cdot21\cdot41}{6}",
        position=(0, 0),
        rect_box=(740, 220, 430, 250),
        rect_padding=20,
        align="center",
        font_size=110,
        stroke_style=StrokeStyle(color=BLACK, width=1.8),
    )
    box_label = Text(
        text="Autofit inside a layout box",
        position=(955, 505),
        font_size=28,
        stroke_style=StrokeStyle(color=BLACK, width=1.5),
    )

    scene.add(FadeInAnimation(start_time=0.0, duration=0.5), drawable=title)
    scene.add(FadeInAnimation(start_time=0.2, duration=0.5), drawable=subtitle)
    scene.add(SketchAnimation(start_time=0.8, duration=1.1), drawable=formula_1)
    scene.add(SketchAnimation(start_time=1.8, duration=1.2), drawable=formula_2)
    scene.add(SketchAnimation(start_time=2.9, duration=1.2), drawable=formula_3)
    scene.add(SketchAnimation(start_time=4.1, duration=0.8), drawable=formula_box)
    scene.add(SketchAnimation(start_time=4.5, duration=1.8), drawable=fitted_formula)
    scene.add(FadeInAnimation(start_time=5.1, duration=0.5), drawable=box_label)
    return scene


def main() -> None:
    output_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "output")
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "latex_math_demo.mp4")
    print(f"Rendering LaTeX math demo to {output_path}...")
    build_scene().render(output_path, max_length=6.8)


if __name__ == "__main__":
    main()