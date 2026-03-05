import numpy as np

from handanim.core.draw_ops import OpsType
from handanim.core.styles import SketchStyle, StrokeStyle
from handanim.primitives import Arrow, CurvedArrow


def _deterministic_sketch_style() -> SketchStyle:
    return SketchStyle(
        roughness=0,
        bowing=0,
        max_random_offset=0,
        disable_multi_stroke=True,
    )


def _collect_points(arrow_like) -> tuple[list[tuple[float, float]], list[tuple[float, float]]]:
    ops = arrow_like.draw().opsset
    move_to_points = [op.data[0] for op in ops if op.type is OpsType.MOVE_TO]
    curve_end_points = [op.data[-1] for op in ops if op.type is OpsType.CURVE_TO]
    return move_to_points, curve_end_points


def test_arrow_barbed_head_draws_bar_segment() -> None:
    arrow = Arrow(
        start_point=(0, 0),
        end_point=(20, 0),
        arrow_head_type="-|>",
        arrow_head_size=10,
        arrow_head_angle=45,
        stroke_style=StrokeStyle(),
        sketch_style=_deterministic_sketch_style(),
    )

    move_to_points, curve_end_points = _collect_points(arrow)
    bar_x = 20 - 10 / 2
    bar_half_height = np.sin(np.deg2rad(45)) * 10

    assert any(np.allclose(point, (bar_x, -bar_half_height)) for point in move_to_points)
    assert any(np.allclose(point, (bar_x, bar_half_height)) for point in curve_end_points)


def test_curved_arrow_barbed_head_draws_bar_segment() -> None:
    curved_arrow = CurvedArrow(
        points=[(0, 0), (10, 0), (20, 0)],
        arrow_head_type="-|>",
        arrow_head_size=10,
        arrow_head_angle=45,
        stroke_style=StrokeStyle(),
        sketch_style=_deterministic_sketch_style(),
    )

    move_to_points, curve_end_points = _collect_points(curved_arrow)
    bar_x = 20 - 10 / 2
    bar_half_height = np.sin(np.deg2rad(45)) * 10

    assert any(np.allclose(point, (bar_x, -bar_half_height)) for point in move_to_points)
    assert any(np.allclose(point, (bar_x, bar_half_height)) for point in curve_end_points)
