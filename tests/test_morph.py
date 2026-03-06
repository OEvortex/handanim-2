import numpy as np
import pytest

from handanim.animations import FadeInAnimation, ReplacementTransformAnimation, TransformAnimation
from handanim.core import Drawable, DrawableGroup
from handanim.core.draw_ops import Ops, OpsSet, OpsType
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


def _path_centers(opsset: OpsSet) -> list[tuple[float, float]]:
    paths: list[list[tuple[float, float]]] = []
    current_path: list[tuple[float, float]] = []
    for op in opsset.opsset:
        if op.type == OpsType.MOVE_TO:
            if current_path:
                paths.append(current_path)
            current_path = [op.data[0]]
        elif op.type == OpsType.LINE_TO:
            current_path.append(op.data[0])
        elif op.type == OpsType.CLOSE_PATH and current_path:
            paths.append(current_path)
            current_path = []
    if current_path:
        paths.append(current_path)

    centers = []
    for path in paths:
        xs = [point[0] for point in path]
        ys = [point[1] for point in path]
        centers.append((sum(xs) / len(xs), sum(ys) / len(ys)))
    return centers


class PairDots(Drawable):
    def __init__(self, centers: list[tuple[float, float]], *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.centers = centers

    def draw(self) -> OpsSet:
        opsset = OpsSet(initial_set=[])
        opsset.add(Ops(OpsType.SET_PEN, {"color": self.stroke_style.color, "width": 1.5}))
        for center in self.centers:
            opsset.add(Ops(OpsType.DOT, {"center": center, "radius": 14}))
        return opsset


def test_transform_animation_matches_source_and_target_endpoints() -> None:
    style = StrokeStyle()
    sketch = _deterministic_sketch_style()
    source = Circle(center=(120, 120), radius=50, stroke_style=style, sketch_style=sketch)
    target = Square(top_left=(300, 70), side_length=100, stroke_style=style, sketch_style=sketch)

    animation = TransformAnimation(target_drawable=target, start_time=0.0, duration=1.0)
    animation.bind_target_opsset(target.draw())

    source_bbox = source.draw().get_bbox()
    target_bbox = target.draw().get_bbox()
    start_bbox = animation.apply(source.draw(), 0.0).get_bbox()
    end_bbox = animation.apply(source.draw(), 1.0).get_bbox()

    assert start_bbox == pytest.approx(source_bbox)
    assert end_bbox == pytest.approx(target_bbox)


def test_transform_animation_path_arc_curves_the_motion() -> None:
    style = StrokeStyle()
    sketch = _deterministic_sketch_style()
    source = Line(start=(0, 0), end=(20, 0), stroke_style=style, sketch_style=sketch)
    target = Line(start=(80, 0), end=(100, 0), stroke_style=style, sketch_style=sketch)

    animation = TransformAnimation(
        target_drawable=target,
        start_time=0.0,
        duration=1.0,
        path_arc=np.pi / 2,
    )
    animation.bind_target_opsset(target.draw())

    mid_ops = animation.apply(source.draw(), 0.5)
    _min_x, min_y, _max_x, max_y = mid_ops.get_bbox()

    assert min(min_y, max_y) < -1.0 or max(min_y, max_y) > 1.0


def test_replacement_transform_switches_scene_visibility_to_target() -> None:
    scene = Scene(fps=4)
    style = StrokeStyle()
    sketch = _deterministic_sketch_style()
    source = Circle(center=(120, 120), radius=40, stroke_style=style, sketch_style=sketch)
    target = Square(top_left=(260, 80), side_length=80, stroke_style=style, sketch_style=sketch)

    scene.add(FadeInAnimation(start_time=0.0, duration=0.0), source)
    scene.add(
        ReplacementTransformAnimation(target_drawable=target, start_time=0.0, duration=1.0),
        source,
    )

    assert source.id in scene.get_active_objects(0.5)
    assert target.id not in scene.get_active_objects(0.5)
    assert source.id not in scene.get_active_objects(1.0)
    assert target.id in scene.get_active_objects(1.0)

    timeline = scene.create_event_timeline(max_length=1.0)
    assert timeline[-1].get_bbox() == pytest.approx(target.draw().get_bbox(), abs=1.0)


def test_transform_animation_smart_matching_avoids_crossing_subpaths() -> None:
    style = StrokeStyle()
    source = PairDots(centers=[(100, 100), (300, 100)], stroke_style=style)
    target = PairDots(centers=[(300, 100), (100, 100)], stroke_style=style)

    animation = TransformAnimation(target_drawable=target, start_time=0.0, duration=1.0)
    animation.bind_target_opsset(target.draw())

    mid_ops = animation.apply(source.draw(), 0.5)
    centers = sorted(_path_centers(mid_ops))

    assert centers[0][0] == pytest.approx(100, abs=12)
    assert centers[1][0] == pytest.approx(300, abs=12)


def test_group_transform_matches_elements_by_geometry_when_target_order_is_reversed() -> None:
    scene = Scene(fps=4)
    style = StrokeStyle()
    sketch = _deterministic_sketch_style()
    source_left = Circle(center=(120, 120), radius=30, stroke_style=style, sketch_style=sketch)
    source_right = Circle(center=(340, 120), radius=30, stroke_style=style, sketch_style=sketch)
    target_left = Square(top_left=(80, 80), side_length=80, stroke_style=style, sketch_style=sketch)
    target_right = Square(top_left=(300, 80), side_length=80, stroke_style=style, sketch_style=sketch)

    source_group = DrawableGroup(elements=[source_left, source_right])
    target_group = DrawableGroup(elements=[target_right, target_left])

    scene.add(FadeInAnimation(start_time=0.0, duration=0.0), source_group)
    scene.add(TransformAnimation(target_drawable=target_group, start_time=0.0, duration=1.0), source_group)

    morph_events = {
        drawable_id: event
        for event, drawable_id in scene.events
        if getattr(event, "target_drawable", None) is not None
    }

    assert morph_events[source_left.id].target_drawable.id == target_left.id
    assert morph_events[source_right.id].target_drawable.id == target_right.id


def test_group_replacement_transform_can_introduce_extra_target_elements() -> None:
    scene = Scene(fps=4)
    style = StrokeStyle()
    sketch = _deterministic_sketch_style()
    source = DrawableGroup(
        elements=[Circle(center=(120, 120), radius=30, stroke_style=style, sketch_style=sketch)]
    )
    target_a = Square(top_left=(240, 80), side_length=80, stroke_style=style, sketch_style=sketch)
    target_b = Square(top_left=(360, 80), side_length=80, stroke_style=style, sketch_style=sketch)
    target = DrawableGroup(elements=[target_a, target_b])

    scene.add(FadeInAnimation(start_time=0.0, duration=0.0), source)
    scene.add(
        ReplacementTransformAnimation(target_drawable=target, start_time=0.0, duration=1.0),
        source,
    )

    active_end = scene.get_active_objects(1.0)
    assert target_a.id in active_end
    assert target_b.id in active_end
    assert source.elements[0].id not in active_end

    final_frame = scene.create_event_timeline(max_length=1.0)[-1]
    assert final_frame.get_bbox() == pytest.approx(target.draw().get_bbox(), abs=2.0)