from pathlib import Path

import numpy as np
import pytest

from handanim.stylings import fonts
from handanim.core.styles import SketchStyle, StrokeStyle
from handanim.primitives import Text
import handanim.primitives.text as text_module


def _styles() -> tuple[StrokeStyle, SketchStyle]:
    return StrokeStyle(), SketchStyle(roughness=0, disable_font_mixture=True)


def _bbox_size(bbox: tuple[float, float, float, float]) -> tuple[float, float]:
    min_x, min_y, max_x, max_y = bbox
    return max_x - min_x, max_y - min_y


def test_text_autofit_stays_inside_rect_box() -> None:
    rect_box = (100.0, 200.0, 160.0, 48.0)
    padding = 4.0
    stroke_style, sketch_style = _styles()

    text = Text(
        text="Autofit content",
        position=(0, 0),
        font_size=96,
        rect_box=rect_box,
        rect_padding=padding,
        stroke_style=stroke_style,
        sketch_style=sketch_style,
    )
    opsset = text.draw()

    min_x, min_y, max_x, max_y = opsset.get_bbox()
    box_x, box_y, box_width, box_height = rect_box
    tol = 1e-6

    assert min_x >= box_x + padding - tol
    assert max_x <= box_x + box_width - padding + tol
    assert min_y >= box_y + padding - tol
    assert max_y <= box_y + box_height - padding + tol

    center_x, center_y = opsset.get_center_of_gravity()
    assert np.isclose(center_x, box_x + box_width / 2, atol=tol)
    assert np.isclose(center_y, box_y + box_height / 2, atol=tol)


def test_text_autofit_reduces_oversized_text_bbox() -> None:
    rect_box = (40.0, 60.0, 120.0, 36.0)
    padding = 2.0
    stroke_style, sketch_style = _styles()

    baseline = Text(
        text="Very long text",
        position=(rect_box[0] + rect_box[2] / 2, rect_box[1] + rect_box[3] / 2),
        font_size=96,
        stroke_style=stroke_style,
        sketch_style=sketch_style,
    ).draw()
    fitted = Text(
        text="Very long text",
        position=(0, 0),
        font_size=96,
        rect_box=rect_box,
        rect_padding=padding,
        stroke_style=stroke_style,
        sketch_style=sketch_style,
    ).draw()

    baseline_width, baseline_height = _bbox_size(baseline.get_bbox())
    fitted_width, fitted_height = _bbox_size(fitted.get_bbox())

    assert fitted_width <= baseline_width
    assert fitted_height <= baseline_height
    assert fitted_width <= rect_box[2] - 2 * padding + 1e-6
    assert fitted_height <= rect_box[3] - 2 * padding + 1e-6


def test_multiline_text_autofit_stays_inside_rect_box() -> None:
    rect_box = (100.0, 150.0, 220.0, 120.0)
    padding = 8.0
    stroke_style, sketch_style = _styles()

    opsset = Text(
        text="Line one\nLine two",
        position=(0, 0),
        font_size=72,
        rect_box=rect_box,
        rect_padding=padding,
        stroke_style=stroke_style,
        sketch_style=sketch_style,
    ).draw()

    min_x, min_y, max_x, max_y = opsset.get_bbox()
    box_x, box_y, box_width, box_height = rect_box

    assert min_x >= box_x + padding - 1e-6
    assert max_x <= box_x + box_width - padding + 1e-6
    assert min_y >= box_y + padding - 1e-6
    assert max_y <= box_y + box_height - padding + 1e-6


def test_text_alignment_respects_rect_box_anchor() -> None:
    rect_box = (50.0, 75.0, 320.0, 100.0)
    padding = 10.0
    stroke_style, sketch_style = _styles()

    left_ops = Text(
        text="Aligned",
        position=(0, 0),
        font_size=64,
        rect_box=rect_box,
        rect_padding=padding,
        align="left",
        stroke_style=stroke_style,
        sketch_style=sketch_style,
    ).draw()
    center_ops = Text(
        text="Aligned",
        position=(0, 0),
        font_size=64,
        rect_box=rect_box,
        rect_padding=padding,
        align="center",
        stroke_style=stroke_style,
        sketch_style=sketch_style,
    ).draw()
    right_ops = Text(
        text="Aligned",
        position=(0, 0),
        font_size=64,
        rect_box=rect_box,
        rect_padding=padding,
        align="right",
        stroke_style=stroke_style,
        sketch_style=sketch_style,
    ).draw()

    left_min_x, _, _left_max_x, _ = left_ops.get_bbox()
    center_x, _ = center_ops.get_center_of_gravity()
    _right_min_x, _, right_max_x, _ = right_ops.get_bbox()

    assert left_min_x == pytest.approx(rect_box[0] + padding, abs=2.0)
    assert center_x == pytest.approx(rect_box[0] + rect_box[2] / 2, abs=2.0)
    assert right_max_x == pytest.approx(rect_box[0] + rect_box[2] - padding, abs=2.0)
    assert left_min_x < center_x < right_max_x


def test_text_glyph_construction_is_cached_per_font_and_character() -> None:
    text_module._cached_glyph_ops.cache_clear()
    stroke_style, sketch_style = _styles()

    text = Text(
        text="aa",
        position=(0, 0),
        font_size=48,
        stroke_style=stroke_style,
        sketch_style=sketch_style,
    )

    first_ops, first_width = text.get_glyph_strokes("a")
    second_ops, second_width = text.get_glyph_strokes("a")

    cache_info = text_module._cached_glyph_ops.cache_info()
    assert cache_info.misses == 1
    assert cache_info.hits == 1
    assert first_ops is not second_ops
    assert first_width == pytest.approx(second_width)
    assert first_ops.get_bbox() == pytest.approx(second_ops.get_bbox())


@pytest.mark.parametrize(
    ("rect_box", "rect_padding", "align", "line_spacing"),
    [
        ((0.0, 0.0, -1.0, 10.0), 0.0, "center", 1.25),
        ((0.0, 0.0, 10.0, 0.0), 0.0, "center", 1.25),
        ((0.0, 0.0, 10.0, 10.0), -1.0, "center", 1.25),
        ((0.0, 0.0, 10.0, 10.0), 0.0, "justify", 1.25),
        ((0.0, 0.0, 10.0, 10.0), 0.0, "center", 0.0),
    ],
)
def test_text_invalid_rect_box_inputs_raise_value_error(
    rect_box: tuple[float, float, float, float],
    rect_padding: float,
    align: str,
    line_spacing: float,
) -> None:
    with pytest.raises(ValueError):
        Text(
            text="x",
            position=(0, 0),
            rect_box=rect_box,
            rect_padding=rect_padding,
            align=align,
            line_spacing=line_spacing,
        )


def test_bundled_fonts_resolve_inside_package() -> None:
    package_font_root = Path(fonts.__file__).resolve().parents[1] / "fonts"

    assert package_font_root.is_dir()

    for font_name in fonts.list_fonts():
        font_path = Path(fonts.get_font_path(font_name)).resolve()

        assert font_path.is_relative_to(package_font_root)
        assert font_path.is_file()