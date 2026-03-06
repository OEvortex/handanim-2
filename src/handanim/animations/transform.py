from __future__ import annotations

import math
from typing import Callable

import numpy as np

from handanim.core.animation import AnimationEvent, AnimationEventType
from handanim.core.draw_ops import Ops, OpsSet, OpsType
from handanim.core.drawable import Drawable, FrozenDrawable

from .fade import FadeInAnimation, FadeOutAnimation
from .morph import ReplacementTransformAnimation, TransformAnimation


def _opsset_to_frozen_drawable(source_drawable: Drawable, opsset: OpsSet) -> FrozenDrawable:
    return FrozenDrawable(
        opsset,
        stroke_style=source_drawable.stroke_style,
        sketch_style=source_drawable.sketch_style,
        fill_style=source_drawable.fill_style,
        glow_dot_hint=source_drawable.glow_dot_hint,
    )


def _set_opsset_opacity(opsset: OpsSet, opacity: float) -> OpsSet:
    updated_ops = []
    for op in opsset.opsset:
        if op.type == OpsType.SET_PEN and isinstance(op.data, dict):
            data = dict(op.data)
            data["opacity"] = opacity
            updated_ops.append(Ops(op.type, data, op.partial, op.meta))
        elif op.type in {OpsType.IMAGE, OpsType.VIDEO} and isinstance(op.data, dict):
            data = dict(op.data)
            data["opacity"] = opacity * float(op.data.get("opacity", 1.0))
            updated_ops.append(Ops(op.type, data, op.partial, op.meta))
        else:
            updated_ops.append(op)
    return OpsSet(initial_set=updated_ops)


def _resolve_animation_endpoint(animation: AnimationEvent, drawable: Drawable, scene) -> OpsSet:
    working_ops = scene.snapshot_drawable_at_time(drawable, animation.start_time).draw()
    resolve_target_drawable = getattr(animation, "resolve_target_drawable", None)
    if callable(resolve_target_drawable) and getattr(animation, "target_drawable", None) is None:
        animation.target_drawable = resolve_target_drawable(drawable=drawable, scene=scene)
    bind_target_opsset = getattr(animation, "bind_target_opsset", None)
    target_drawable = getattr(animation, "target_drawable", None)
    if callable(bind_target_opsset) and target_drawable is not None:
        bind_target_opsset(target_drawable.draw())
    return animation.apply(working_ops, 1.0)


def _make_matrix_point_function(matrix) -> Callable[[tuple[float, float]], tuple[float, float]]:
    array = np.asarray(matrix, dtype=float)
    if array.shape == (2, 2):
        return lambda point: tuple((array @ np.asarray(point, dtype=float)).tolist())
    if array.shape == (2, 3):
        return lambda point: tuple((array @ np.asarray([point[0], point[1], 1.0], dtype=float)).tolist())
    if array.shape == (3, 3):
        def _projective(point: tuple[float, float]) -> tuple[float, float]:
            result = array @ np.asarray([point[0], point[1], 1.0], dtype=float)
            divisor = result[2] if abs(result[2]) > 1e-9 else 1.0
            return float(result[0] / divisor), float(result[1] / divisor)

        return _projective
    msg = "ApplyMatrix expects a 2x2, 2x3, or 3x3 matrix"
    raise ValueError(msg)


class Transform(TransformAnimation):
    pass


class ReplacementTransform(ReplacementTransformAnimation):
    pass


class ClockwiseTransform(Transform):
    def __init__(self, target_drawable=None, *args, **kwargs) -> None:
        kwargs.setdefault("path_arc", -math.pi)
        super().__init__(target_drawable=target_drawable, *args, **kwargs)


class CounterclockwiseTransform(Transform):
    def __init__(self, target_drawable=None, *args, **kwargs) -> None:
        kwargs.setdefault("path_arc", math.pi)
        super().__init__(target_drawable=target_drawable, *args, **kwargs)


class FadeTransform(ReplacementTransform):
    def __init__(self, target_drawable=None, *args, **kwargs) -> None:
        kwargs.setdefault("matching_strategy", "smart")
        super().__init__(target_drawable=target_drawable, *args, **kwargs)


class FadeTransformPieces(FadeTransform):
    pass


class _LazyTargetTransform(Transform):
    def __init__(self, source_drawable: Drawable | None = None, *args, **kwargs) -> None:
        self.source_drawable = source_drawable
        super().__init__(target_drawable=None, *args, **kwargs)

    def _snapshot_source(self, drawable: Drawable, scene) -> FrozenDrawable:
        return scene.snapshot_drawable_at_time(drawable, self.start_time)


class ApplyFunction(_LazyTargetTransform):
    def __init__(self, function, source_drawable: Drawable | None = None, *args, **kwargs) -> None:
        self.function = function
        super().__init__(source_drawable=source_drawable, *args, **kwargs)

    def resolve_target_drawable(self, drawable: Drawable, scene):
        source_snapshot = self._snapshot_source(drawable, scene)
        result = self.function(source_snapshot)
        if isinstance(result, Drawable):
            return result
        if isinstance(result, OpsSet):
            return _opsset_to_frozen_drawable(drawable, result)
        msg = "ApplyFunction must return a Drawable or OpsSet"
        raise TypeError(msg)


class ApplyMethod(ApplyFunction):
    def __init__(
        self,
        method,
        *method_args,
        start_time: float = 0.0,
        duration: float = 0.0,
        easing_fun=None,
        data: dict | None = None,
        path_arc: float = 0.0,
        sample_points_per_curve: int = 16,
        min_path_points: int = 8,
        matching_strategy: str = "smart",
    ) -> None:
        self.method = method
        self.method_args = method_args
        self.method_name = getattr(method, "__name__", None)
        source_drawable = getattr(method, "__self__", None)
        super().__init__(
            function=self._apply_method_to_snapshot,
            source_drawable=source_drawable if isinstance(source_drawable, Drawable) else None,
            start_time=start_time,
            duration=duration,
            easing_fun=easing_fun,
            data=data,
            path_arc=path_arc,
            sample_points_per_curve=sample_points_per_curve,
            min_path_points=min_path_points,
            matching_strategy=matching_strategy,
        )

    def _apply_method_to_snapshot(self, snapshot_drawable: Drawable):
        if self.method_name is not None and hasattr(snapshot_drawable, self.method_name):
            result = getattr(snapshot_drawable, self.method_name)(*self.method_args)
        else:
            result = self.method(snapshot_drawable, *self.method_args)
        return snapshot_drawable if result is None else result


class ApplyPointwiseFunction(_LazyTargetTransform):
    def __init__(self, function, source_drawable: Drawable | None = None, *args, **kwargs) -> None:
        self.function = function
        super().__init__(source_drawable=source_drawable, *args, **kwargs)

    def resolve_target_drawable(self, drawable: Drawable, scene):
        source_snapshot = self._snapshot_source(drawable, scene)
        target_ops = source_snapshot.draw().clone()
        target_ops.transform_points(self.function)
        return _opsset_to_frozen_drawable(drawable, target_ops)


class ApplyComplexFunction(ApplyPointwiseFunction):
    def __init__(self, function, source_drawable: Drawable | None = None, *args, **kwargs) -> None:
        def _complex_to_point(point: tuple[float, float]) -> tuple[float, float]:
            complex_result = function(complex(point[0], point[1]))
            return float(np.real(complex_result)), float(np.imag(complex_result))

        super().__init__(_complex_to_point, source_drawable=source_drawable, *args, **kwargs)


class ApplyMatrix(ApplyPointwiseFunction):
    def __init__(self, matrix, source_drawable: Drawable | None = None, *args, **kwargs) -> None:
        super().__init__(_make_matrix_point_function(matrix), source_drawable=source_drawable, *args, **kwargs)


class ApplyPointwiseFunctionToCenter(_LazyTargetTransform):
    def __init__(self, function, source_drawable: Drawable | None = None, *args, **kwargs) -> None:
        self.function = function
        super().__init__(source_drawable=source_drawable, *args, **kwargs)

    def resolve_target_drawable(self, drawable: Drawable, scene):
        source_snapshot = self._snapshot_source(drawable, scene)
        center_x, center_y = source_snapshot.draw().get_center_of_gravity()
        new_center_x, new_center_y = self.function((center_x, center_y))
        return source_snapshot.translate(new_center_x - center_x, new_center_y - center_y)


class MoveToTarget(_LazyTargetTransform):
    def resolve_target_drawable(self, drawable: Drawable, scene):
        target = getattr(drawable, "target", None)
        if target is None:
            msg = "MoveToTarget requires drawable.generate_target() to be called first"
            raise ValueError(msg)
        return target


class Restore(_LazyTargetTransform):
    def resolve_target_drawable(self, drawable: Drawable, scene):
        saved_state = drawable.get_saved_state()
        if saved_state is None:
            msg = "Restore requires drawable.save_state() to be called first"
            raise ValueError(msg)
        return saved_state


class ScaleInPlace(_LazyTargetTransform):
    def __init__(self, scale_factor: float, scale_factor_y: float | None = None, *args, **kwargs) -> None:
        self.scale_factor = scale_factor
        self.scale_factor_y = scale_factor_y
        super().__init__(*args, **kwargs)

    def resolve_target_drawable(self, drawable: Drawable, scene):
        return self._snapshot_source(drawable, scene).scale(self.scale_factor, self.scale_factor_y)


class ShrinkToCenter(_LazyTargetTransform):
    def resolve_target_drawable(self, drawable: Drawable, scene):
        source_snapshot = self._snapshot_source(drawable, scene)
        target_ops = source_snapshot.draw().clone()
        center = target_ops.get_center_of_gravity()
        target_ops.transform_points(lambda _point: center)
        target_ops = _set_opsset_opacity(target_ops, 0.0)
        return _opsset_to_frozen_drawable(drawable, target_ops)


class FadeToColor(AnimationEvent):
    def __init__(self, color, start_time: float = 0.0, duration: float = 0.0, easing_fun=None, data=None) -> None:
        super().__init__(AnimationEventType.MUTATION, start_time, duration, easing_fun, data)
        self.color = tuple(color)

    def apply(self, opsset: OpsSet, progress: float):
        if self.easing_fun is not None:
            progress = float(self.easing_fun(progress))
        current_ops = []
        for op in opsset.opsset:
            if op.type == OpsType.SET_PEN and isinstance(op.data, dict):
                old_color = op.data.get("color", self.color)
                source = np.asarray(old_color, dtype=float)
                target = np.asarray(self.color, dtype=float)
                blended = tuple(((1 - progress) * source + progress * target).tolist())
                data = dict(op.data)
                data["color"] = blended
                current_ops.append(Ops(op.type, data, op.partial, op.meta))
            else:
                current_ops.append(op)
        return OpsSet(initial_set=current_ops)


class TransformFromCopy(AnimationEvent):
    def __init__(
        self,
        source_drawable: Drawable,
        target_drawable: Drawable,
        start_time: float = 0.0,
        duration: float = 0.0,
        easing_fun=None,
        data=None,
        path_arc: float = 0.0,
        matching_strategy: str = "smart",
    ) -> None:
        super().__init__(AnimationEventType.MUTATION, start_time, duration, easing_fun, data)
        self.source_drawable = source_drawable
        self.target_drawable = target_drawable
        self.path_arc = path_arc
        self.matching_strategy = matching_strategy

    def expand_for_scene(self, scene, drawable: Drawable):
        source_snapshot = scene.snapshot_drawable_at_time(self.source_drawable, self.start_time)
        source_copy = source_snapshot.copy(new_id=True)
        return [
            (FadeInAnimation(start_time=self.start_time, duration=0.0), source_copy),
            (
                ReplacementTransform(
                    target_drawable=self.target_drawable,
                    start_time=self.start_time,
                    duration=self.duration,
                    easing_fun=self.easing_fun,
                    data=dict(self.data),
                    path_arc=self.path_arc,
                    matching_strategy=self.matching_strategy,
                ),
                source_copy,
            ),
        ]


class CyclicReplace(AnimationEvent):
    def __init__(self, *drawables: Drawable, start_time: float = 0.0, duration: float = 0.0, easing_fun=None, data=None, path_arc: float = math.pi / 2) -> None:
        super().__init__(AnimationEventType.MUTATION, start_time, duration, easing_fun, data)
        self.drawables = list(drawables)
        self.path_arc = path_arc
        self.source_drawable = self.drawables[0] if self.drawables else None

    def expand_for_scene(self, scene, drawable: Drawable):
        if len(self.drawables) < 2:
            msg = "CyclicReplace requires at least two drawables"
            raise ValueError(msg)
        expanded = []
        snapshots = [scene.snapshot_drawable_at_time(source, self.start_time) for source in self.drawables]
        centers = [snapshot.draw().get_center_of_gravity() for snapshot in snapshots]
        for index, source in enumerate(self.drawables):
            next_center = centers[(index + 1) % len(centers)]
            source_snapshot = snapshots[index]
            source_center = centers[index]
            target_ops = source_snapshot.draw().clone()
            target_ops.translate(next_center[0] - source_center[0], next_center[1] - source_center[1])
            target_drawable = _opsset_to_frozen_drawable(source, target_ops)
            expanded.append(
                (
                    Transform(
                        target_drawable=target_drawable,
                        start_time=self.start_time,
                        duration=self.duration,
                        easing_fun=self.easing_fun,
                        data=dict(self.data),
                        path_arc=self.path_arc,
                    ),
                    source,
                )
            )
        return expanded


class Swap(CyclicReplace):
    pass


class TransformAnimations(AnimationEvent):
    def __init__(
        self,
        start_animation: AnimationEvent,
        end_animation: AnimationEvent,
        source_drawable: Drawable,
        target_drawable: Drawable | None = None,
        start_time: float = 0.0,
        duration: float = 0.0,
        easing_fun=None,
        data=None,
        path_arc: float = 0.0,
        matching_strategy: str = "smart",
    ) -> None:
        super().__init__(AnimationEventType.MUTATION, start_time, duration, easing_fun, data)
        self.start_animation = start_animation
        self.end_animation = end_animation
        self.source_drawable = source_drawable
        self.target_drawable = target_drawable or source_drawable
        self.path_arc = path_arc
        self.matching_strategy = matching_strategy

    def expand_for_scene(self, scene, drawable: Drawable):
        start_state = _opsset_to_frozen_drawable(
            self.source_drawable,
            _resolve_animation_endpoint(self.start_animation, self.source_drawable, scene),
        )
        end_state = _opsset_to_frozen_drawable(
            self.target_drawable,
            _resolve_animation_endpoint(self.end_animation, self.target_drawable, scene),
        )
        return [
            (FadeOutAnimation(start_time=self.start_time, duration=self.duration), self.source_drawable),
            (FadeInAnimation(start_time=self.start_time, duration=0.0), start_state),
            (
                ReplacementTransform(
                    target_drawable=end_state,
                    start_time=self.start_time,
                    duration=self.duration,
                    easing_fun=self.easing_fun,
                    data=dict(self.data),
                    path_arc=self.path_arc,
                    matching_strategy=self.matching_strategy,
                ),
                start_state,
            ),
        ]


__all__ = [
    "ApplyComplexFunction",
    "ApplyFunction",
    "ApplyMatrix",
    "ApplyMethod",
    "ApplyPointwiseFunction",
    "ApplyPointwiseFunctionToCenter",
    "ClockwiseTransform",
    "CounterclockwiseTransform",
    "CyclicReplace",
    "FadeToColor",
    "FadeTransform",
    "FadeTransformPieces",
    "MoveToTarget",
    "ReplacementTransform",
    "Restore",
    "ScaleInPlace",
    "ShrinkToCenter",
    "Swap",
    "Transform",
    "TransformAnimations",
    "TransformFromCopy",
]