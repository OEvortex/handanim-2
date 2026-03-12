import pytest

from handanim.core.styles import SketchStyle, StrokeStyle
from handanim.primitives import Math, MathTex


def _styles() -> tuple[StrokeStyle, SketchStyle]:
    return (
        StrokeStyle(),
        SketchStyle(roughness=0, bowing=0, max_random_offset=0, disable_multi_stroke=True),
    )


def test_mathtex_renders_latex_like_expression_without_explicit_dollar_delimiters() -> None:
    stroke_style, sketch_style = _styles()
    drawable = MathTex(
        r"\frac{a}{b}+\sqrt{x}",
        position=(240.0, 160.0),
        font_size=72,
        stroke_style=stroke_style,
        sketch_style=sketch_style,
    )

    opsset = drawable.draw()
    min_x, min_y, max_x, max_y = opsset.get_bbox()
    center_x, center_y = opsset.get_center_of_gravity()

    assert max_x > min_x
    assert max_y > min_y
    assert center_x == pytest.approx(240.0, abs=1.5)
    assert center_y == pytest.approx(160.0, abs=1.5)


def test_mathtex_supports_rect_box_alignment_and_autofit() -> None:
    stroke_style, sketch_style = _styles()
    rect_box = (50.0, 100.0, 180.0, 60.0)
    padding = 6.0
    drawable = MathTex(
        r"\sum_{i=1}^{n} i = \frac{n(n+1)}{2}",
        position=(0.0, 0.0),
        rect_box=rect_box,
        rect_padding=padding,
        align="right",
        font_size=96,
        stroke_style=stroke_style,
        sketch_style=sketch_style,
    )

    min_x, min_y, max_x, max_y = drawable.draw().get_bbox()
    box_x, box_y, box_width, box_height = rect_box

    assert min_x >= box_x + padding - 1e-6
    assert max_x <= box_x + box_width - padding + 1e-6
    assert min_y >= box_y + padding - 1e-6
    assert max_y <= box_y + box_height - padding + 1e-6
    assert max_x == pytest.approx(box_x + box_width - padding, abs=2.0)


def test_math_legacy_primitive_still_renders_basic_formula() -> None:
    stroke_style, sketch_style = _styles()
    drawable = Math(
        tex_expression=r"$a^2 + b^2 = c^2$",
        position=(100.0, 80.0),
        font_size=48,
        stroke_style=stroke_style,
        sketch_style=sketch_style,
    )

    min_x, min_y, max_x, max_y = drawable.draw().get_bbox()
    assert max_x > min_x
    assert max_y > min_y