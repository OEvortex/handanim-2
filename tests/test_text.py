from pathlib import Path

import numpy as np
import pytest

from handanim.stylings import fonts
from handanim.core.styles import SketchStyle, StrokeStyle
from handanim.primitives import Text


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


@pytest.mark.parametrize(
    ("rect_box", "rect_padding"),
    [
        ((0.0, 0.0, -1.0, 10.0), 0.0),
        ((0.0, 0.0, 10.0, 0.0), 0.0),
        ((0.0, 0.0, 10.0, 10.0), -1.0),
    ],
)
def test_text_invalid_rect_box_inputs_raise_value_error(
    rect_box: tuple[float, float, float, float], rect_padding: float
) -> None:
    with pytest.raises(ValueError):
        Text(
            text="x",
            position=(0, 0),
            rect_box=rect_box,
            rect_padding=rect_padding,
        )


def test_bundled_fonts_resolve_inside_package() -> None:
    package_font_root = Path(fonts.__file__).resolve().parents[1] / "fonts"

    assert package_font_root.is_dir()

    for font_name in fonts.list_fonts():
        font_path = Path(fonts.get_font_path(font_name)).resolve()

        assert font_path.is_relative_to(package_font_root)
        assert font_path.is_file()