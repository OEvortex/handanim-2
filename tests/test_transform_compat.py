import math

import pytest

from handanim.animations import (
    ApplyComplexFunction,
    ApplyMatrix,
    ApplyMethod,
    ApplyPointwiseFunction,
    ClockwiseTransform,
    CounterclockwiseTransform,
    CyclicReplace,
    FadeInAnimation,
    FadeToColor,
    FadeTransform,
    FadeTransformPieces,
    MoveToTarget,
    Restore,
    ScaleInPlace,
    ShrinkToCenter,
    Swap,
    Transform,
    TransformAnimations,
    TransformFromCopy,
)
from handanim.core import DrawableGroup
from handanim.core.scene import Scene
from handanim.core.styles import SketchStyle, StrokeStyle
from handanim.primitives import Circle, Line, Square


def _deterministic_sketch_style() -> SketchStyle:
    return SketchStyle(
        roughness=0,
        bowing=0,
        max_random_offset=0,
        disable_multi_stroke=True,
        disable_font_mixture=True,
    )


def _bbox_center(bbox):
    min_x, min_y, max_x, max_y = bbox
    return ((min_x + max_x) / 2, (min_y + max_y) / 2)


def _first_pen_color(opsset):
    for op in opsset.opsset:
        if op.type.value == "set_pen":
            return op.data.get("color")
    raise AssertionError("No set_pen op found")


def test_transform_aliases_are_available_with_expected_defaults() -> None:
    style = StrokeStyle()
    sketch = _deterministic_sketch_style()
    target = Square(top_left=(60, 60), side_length=40, stroke_style=style, sketch_style=sketch)

    clockwise = ClockwiseTransform(target_drawable=target)
    counterclockwise = CounterclockwiseTransform(target_drawable=target)
    fade_transform = FadeTransform(target_drawable=target)
    fade_transform_pieces = FadeTransformPieces(target_drawable=DrawableGroup(elements=[target]))

    assert isinstance(clockwise, Transform)
    assert clockwise.path_arc < 0
    assert counterclockwise.path_arc > 0
    assert fade_transform.replace_mobject_with_target_in_scene is True
    assert fade_transform_pieces.replace_mobject_with_target_in_scene is True


def test_apply_method_uses_bound_drawable_without_explicit_scene_add_drawable() -> None:
    scene = Scene(fps=10)
    style = StrokeStyle()
    sketch = _deterministic_sketch_style()
    circle = Circle(center=(100, 100), radius=30, stroke_style=style, sketch_style=sketch)

    scene.add(FadeInAnimation(start_time=0.0, duration=0.0), circle)
    scene.add(ApplyMethod(circle.translate, 120, 40, start_time=0.0, duration=1.0))

    final_bbox = scene.get_drawable_opsset_at_scene_time(circle.id, 1.0).get_bbox()
    assert _bbox_center(final_bbox) == pytest.approx((220, 140), abs=2.0)


def test_apply_pointwise_function_matrix_and_complex_function_change_geometry() -> None:
    style = StrokeStyle()
    sketch = _deterministic_sketch_style()

    line_a = Line(start=(0, 0), end=(40, 0), stroke_style=style, sketch_style=sketch)
    scene_a = Scene(fps=10)
    scene_a.add(FadeInAnimation(start_time=0.0, duration=0.0), line_a)
    scene_a.add(
        ApplyPointwiseFunction(
            lambda point: (point[0], point[1] + point[0] / 2),
            start_time=0.0,
            duration=1.0,
        ),
        line_a,
    )
    assert scene_a.get_drawable_opsset_at_scene_time(line_a.id, 1.0).get_bbox()[3] > 15

    line_b = Line(start=(0, 0), end=(40, 0), stroke_style=style, sketch_style=sketch)
    scene_b = Scene(fps=10)
    scene_b.add(FadeInAnimation(start_time=0.0, duration=0.0), line_b)
    scene_b.add(ApplyMatrix([[1, 0, 50], [0, 1, 10]], start_time=0.0, duration=1.0), line_b)
    assert _bbox_center(scene_b.get_drawable_opsset_at_scene_time(line_b.id, 1.0).get_bbox()) == pytest.approx(
        (70, 10),
        abs=2.0,
    )

    line_c = Line(start=(10, 0), end=(30, 0), stroke_style=style, sketch_style=sketch)
    scene_c = Scene(fps=10)
    scene_c.add(FadeInAnimation(start_time=0.0, duration=0.0), line_c)
    scene_c.add(ApplyComplexFunction(lambda z: z * 1j, start_time=0.0, duration=1.0), line_c)
    final_bbox = scene_c.get_drawable_opsset_at_scene_time(line_c.id, 1.0).get_bbox()
    assert _bbox_center(final_bbox) == pytest.approx((0, 20), abs=2.0)


def test_move_to_target_restore_scale_shrink_and_fade_to_color_work_together() -> None:
    scene = Scene(fps=10)
    style = StrokeStyle(color=(0, 0, 0))
    sketch = _deterministic_sketch_style()
    square = Square(top_left=(100, 100), side_length=60, stroke_style=style, sketch_style=sketch)

    square.save_state()
    square.generate_target()
    square.target = square.target.translate(100, 20)

    scene.add(FadeInAnimation(start_time=0.0, duration=0.0), square)
    scene.add(MoveToTarget(start_time=0.0, duration=1.0), square)
    moved_center = _bbox_center(scene.get_drawable_opsset_at_scene_time(square.id, 1.0).get_bbox())
    assert moved_center == pytest.approx((230, 150), abs=2.0)

    scene.add(Restore(start_time=1.0, duration=1.0), square)
    restored_center = _bbox_center(scene.get_drawable_opsset_at_scene_time(square.id, 2.0).get_bbox())
    assert restored_center == pytest.approx((130, 130), abs=2.0)

    scene.add(ScaleInPlace(0.5, start_time=2.0, duration=1.0), square)
    scaled_bbox = scene.get_drawable_opsset_at_scene_time(square.id, 3.0).get_bbox()
    assert scaled_bbox[2] - scaled_bbox[0] < 40

    scene.add(FadeToColor((1, 0, 0), start_time=3.0, duration=1.0), square)
    final_color = _first_pen_color(scene.get_drawable_opsset_at_scene_time(square.id, 4.0))
    assert final_color == pytest.approx((1, 0, 0), abs=0.05)

    scene.add(ShrinkToCenter(start_time=4.0, duration=1.0), square)
    shrunk_bbox = scene.get_drawable_opsset_at_scene_time(square.id, 5.0).get_bbox()
    assert shrunk_bbox[2] - shrunk_bbox[0] < 2


def test_transform_from_copy_keeps_original_and_reveals_target() -> None:
    scene = Scene(fps=10)
    style = StrokeStyle()
    sketch = _deterministic_sketch_style()
    source = Circle(center=(100, 100), radius=30, stroke_style=style, sketch_style=sketch)
    target = Square(top_left=(220, 70), side_length=60, stroke_style=style, sketch_style=sketch)

    scene.add(FadeInAnimation(start_time=0.0, duration=0.0), source)
    scene.add(TransformFromCopy(source, target, start_time=0.0, duration=1.0))

    active_end = scene.get_active_objects(1.0)
    assert source.id in active_end
    assert target.id in active_end


def test_cyclic_replace_and_swap_move_objects_to_each_others_centers() -> None:
    style = StrokeStyle()
    sketch = _deterministic_sketch_style()

    left = Circle(center=(80, 100), radius=20, stroke_style=style, sketch_style=sketch)
    right = Circle(center=(220, 100), radius=20, stroke_style=style, sketch_style=sketch)
    cycle_scene = Scene(fps=10)
    cycle_scene.add(FadeInAnimation(start_time=0.0, duration=0.0), left)
    cycle_scene.add(FadeInAnimation(start_time=0.0, duration=0.0), right)
    cycle_scene.add(CyclicReplace(left, right, start_time=0.0, duration=1.0))

    assert _bbox_center(cycle_scene.get_drawable_opsset_at_scene_time(left.id, 1.0).get_bbox()) == pytest.approx(
        (220, 100),
        abs=2.0,
    )
    assert _bbox_center(cycle_scene.get_drawable_opsset_at_scene_time(right.id, 1.0).get_bbox()) == pytest.approx(
        (80, 100),
        abs=2.0,
    )

    top = Circle(center=(80, 60), radius=20, stroke_style=style, sketch_style=sketch)
    bottom = Circle(center=(80, 180), radius=20, stroke_style=style, sketch_style=sketch)
    swap_scene = Scene(fps=10)
    swap_scene.add(FadeInAnimation(start_time=0.0, duration=0.0), top)
    swap_scene.add(FadeInAnimation(start_time=0.0, duration=0.0), bottom)
    swap_scene.add(Swap(top, bottom, start_time=0.0, duration=1.0, path_arc=math.pi / 2))

    assert _bbox_center(swap_scene.get_drawable_opsset_at_scene_time(top.id, 1.0).get_bbox()) == pytest.approx(
        (80, 180),
        abs=2.0,
    )


def test_transform_animations_reaches_end_animation_state() -> None:
    scene = Scene(fps=10)
    style = StrokeStyle()
    sketch = _deterministic_sketch_style()
    line = Line(start=(0, 0), end=(40, 0), stroke_style=style, sketch_style=sketch)

    scene.add(
        TransformAnimations(
            start_animation=ScaleInPlace(0.5, source_drawable=line, start_time=0.0, duration=0.0),
            end_animation=ApplyMatrix([[0, -1], [1, 0]], source_drawable=line, start_time=0.0, duration=0.0),
            source_drawable=line,
            start_time=0.0,
            duration=1.0,
        )
    )

    final_frame = scene.create_event_timeline(max_length=1.0)[-1]
    assert _bbox_center(final_frame.get_bbox()) == pytest.approx((0, 20), abs=3.0)