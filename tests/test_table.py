import pytest

from handanim.core.styles import FillStyle, SketchStyle, StrokeStyle
from handanim.primitives import Table


def _deterministic_sketch_style() -> SketchStyle:
    return SketchStyle(
        roughness=0,
        bowing=0,
        max_random_offset=0,
        disable_multi_stroke=True,
        disable_font_mixture=True,
    )


def test_table_geometry_helpers() -> None:
    table = Table(
        data=[["A", "B"], ["1", "2"]],
        top_left=(100, 200),
        col_widths=[120, 160],
        row_heights=[50, 70],
        stroke_style=StrokeStyle(),
        sketch_style=_deterministic_sketch_style(),
    )

    assert table.width == 280
    assert table.height == 120
    assert table.center == (240, 260)
    assert table.cell_bbox(1, 1) == (220, 250, 160, 70)
    assert table.cell_center(0, 1) == (300, 225)


def test_table_draw_bbox_matches_total_bounds() -> None:
    table = Table(
        data=[["Header", "Value"], ["Alpha", "42"]],
        top_left=(50, 80),
        col_widths=140,
        row_heights=60,
        header_rows=1,
        stroke_style=StrokeStyle(),
        sketch_style=_deterministic_sketch_style(),
        fill_style=FillStyle(opacity=0.25),
        header_fill_style=FillStyle(opacity=0.4),
    )

    min_x, min_y, max_x, max_y = table.draw().get_bbox()

    assert min_x == pytest.approx(50.0, abs=1.0)
    assert min_y == pytest.approx(80.0, abs=1.0)
    assert max_x == pytest.approx(330.0, abs=1.0)
    assert max_y == pytest.approx(200.0, abs=1.0)


@pytest.mark.parametrize(
    ("data", "col_widths", "row_heights"),
    [
        ([], 100, 40),
        ([["A"], ["B", "C"]], 100, 40),
        ([["A"]], [0], 40),
        ([["A"]], 100, [-1]),
    ],
)
def test_table_invalid_inputs_raise_value_error(data, col_widths, row_heights) -> None:
    with pytest.raises(ValueError):
        Table(
            data=data,
            top_left=(0, 0),
            col_widths=col_widths,
            row_heights=row_heights,
            stroke_style=StrokeStyle(),
            sketch_style=_deterministic_sketch_style(),
        )