from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np

from handanim.core.animation import AnimationEvent, AnimationEventType
from handanim.core.draw_ops import Ops, OpsSet, OpsType


@dataclass
class _MorphStyle:
    mode: str = "stroke"
    color: tuple[float, float, float] | None = None
    opacity: float = 1.0
    width: float = 1.0


@dataclass
class _MorphPath:
    points: list[np.ndarray]
    style: _MorphStyle
    closed: bool = False


@dataclass
class _DrawableMatchEntry:
    drawable: object
    bbox: tuple[float, float, float, float]


def _clone_opsset(opsset: OpsSet) -> OpsSet:
    return OpsSet(initial_set=list(opsset.opsset), has_3d_ops=opsset.has_3d_ops())


def _style_from_pen_data(data: dict) -> _MorphStyle:
    return _MorphStyle(
        mode=str(data.get("mode", "stroke")),
        color=data.get("color"),
        opacity=float(data.get("opacity", 1.0)),
        width=float(data.get("width", 1.0)),
    )


def _eval_cubic_bezier(
    p0: np.ndarray, p1: np.ndarray, p2: np.ndarray, p3: np.ndarray, t: float
) -> np.ndarray:
    omt = 1 - t
    return (
        omt**3 * p0
        + 3 * omt**2 * t * p1
        + 3 * omt * t**2 * p2
        + t**3 * p3
    )


def _sample_curve_points(
    p0: np.ndarray, p1: np.ndarray, p2: np.ndarray, p3: np.ndarray, sample_count: int
) -> list[np.ndarray]:
    return [
        _eval_cubic_bezier(p0, p1, p2, p3, t)
        for t in np.linspace(0.0, 1.0, max(sample_count, 2))
    ]


def _rotate_90(vector: np.ndarray) -> np.ndarray:
    return np.array([-vector[1], vector[0]], dtype=float)


def _path_center(paths: list[_MorphPath]) -> np.ndarray:
    all_points = [point for path in paths for point in path.points]
    if not all_points:
        return np.zeros(2, dtype=float)
    return np.mean(np.vstack(all_points), axis=0)


def _bbox_center(bbox: tuple[float, float, float, float]) -> np.ndarray:
    min_x, min_y, max_x, max_y = bbox
    return np.array([(min_x + max_x) / 2, (min_y + max_y) / 2], dtype=float)


def _bbox_area(bbox: tuple[float, float, float, float]) -> float:
    min_x, min_y, max_x, max_y = bbox
    return max(max_x - min_x, 0.0) * max(max_y - min_y, 0.0)


def _path_bbox(path: _MorphPath) -> tuple[float, float, float, float]:
    if not path.points:
        return (0.0, 0.0, 0.0, 0.0)
    points = np.vstack(path.points)
    return (
        float(np.min(points[:, 0])),
        float(np.min(points[:, 1])),
        float(np.max(points[:, 0])),
        float(np.max(points[:, 1])),
    )


def _path_length(path: _MorphPath) -> float:
    if len(path.points) <= 1:
        return 0.0
    return float(
        sum(
            np.linalg.norm(path.points[index + 1] - path.points[index])
            for index in range(len(path.points) - 1)
        )
    )


def _polygon_area(points: list[np.ndarray]) -> float:
    if len(points) < 3:
        return 0.0
    point_array = np.vstack(points)
    x_values = point_array[:, 0]
    y_values = point_array[:, 1]
    return float(
        0.5 * abs(np.dot(x_values, np.roll(y_values, -1)) - np.dot(y_values, np.roll(x_values, -1)))
    )


def _pair_by_greedy_cost(cost_matrix: list[list[float]]) -> list[tuple[int, int]]:
    if not cost_matrix or not cost_matrix[0]:
        return []

    remaining_source = set(range(len(cost_matrix)))
    remaining_target = set(range(len(cost_matrix[0])))
    pairs: list[tuple[int, int]] = []
    while remaining_source and remaining_target:
        source_idx = target_idx = -1
        best_cost = float("inf")
        for current_source in remaining_source:
            for current_target in remaining_target:
                current_cost = cost_matrix[current_source][current_target]
                if current_cost < best_cost:
                    best_cost = current_cost
                    source_idx = current_source
                    target_idx = current_target
        pairs.append((source_idx, target_idx))
        remaining_source.remove(source_idx)
        remaining_target.remove(target_idx)
    return pairs


def _path_match_cost(source_path: _MorphPath, target_path: _MorphPath) -> float:
    source_bbox = _path_bbox(source_path)
    target_bbox = _path_bbox(target_path)
    source_center = _bbox_center(source_bbox)
    target_center = _bbox_center(target_bbox)
    center_distance = float(np.linalg.norm(source_center - target_center))
    area_delta = abs(_bbox_area(source_bbox) - _bbox_area(target_bbox))
    path_length_delta = abs(_path_length(source_path) - _path_length(target_path))
    polygon_area_delta = abs(_polygon_area(source_path.points) - _polygon_area(target_path.points))
    style_penalty = 0.0 if source_path.style.mode == target_path.style.mode else 500.0
    closed_penalty = 0.0 if source_path.closed == target_path.closed else 500.0
    return center_distance + 0.05 * area_delta + 0.1 * path_length_delta + 0.05 * polygon_area_delta + style_penalty + closed_penalty


def _drawable_match_cost(source_entry: _DrawableMatchEntry, target_entry: _DrawableMatchEntry) -> float:
    source_center = _bbox_center(source_entry.bbox)
    target_center = _bbox_center(target_entry.bbox)
    center_distance = float(np.linalg.norm(source_center - target_center))
    area_delta = abs(_bbox_area(source_entry.bbox) - _bbox_area(target_entry.bbox))
    source_name = getattr(source_entry.drawable, "__class__", type(source_entry.drawable)).__name__
    target_name = getattr(target_entry.drawable, "__class__", type(target_entry.drawable)).__name__
    type_penalty = 0.0 if source_name == target_name else 150.0
    return center_distance + 0.05 * area_delta + type_penalty


def _resample_polyline(points: list[np.ndarray], target_count: int, closed: bool) -> list[np.ndarray]:
    if not points:
        return [np.zeros(2, dtype=float) for _ in range(target_count)]
    if len(points) == 1:
        return [points[0].copy() for _ in range(target_count)]

    working_points = [point.copy() for point in points]
    if closed and not np.allclose(working_points[0], working_points[-1]):
        working_points.append(working_points[0].copy())

    segment_lengths = [
        float(np.linalg.norm(working_points[index + 1] - working_points[index]))
        for index in range(len(working_points) - 1)
    ]
    total_length = sum(segment_lengths)
    if total_length <= 1e-9:
        return [working_points[0].copy() for _ in range(target_count)]

    samples = np.linspace(0.0, total_length, target_count)
    resampled: list[np.ndarray] = []
    segment_index = 0
    distance_so_far = 0.0

    for sample in samples:
        while (
            segment_index < len(segment_lengths) - 1
            and distance_so_far + segment_lengths[segment_index] < sample
        ):
            distance_so_far += segment_lengths[segment_index]
            segment_index += 1

        segment_length = segment_lengths[segment_index]
        if segment_length <= 1e-9:
            resampled.append(working_points[segment_index].copy())
            continue

        local_t = (sample - distance_so_far) / segment_length
        start = working_points[segment_index]
        end = working_points[segment_index + 1]
        resampled.append((1 - local_t) * start + local_t * end)

    if closed and resampled:
        resampled[-1] = resampled[0].copy()
    return resampled


def _best_cyclic_shift(source_points: list[np.ndarray], target_points: list[np.ndarray]) -> list[np.ndarray]:
    if len(source_points) != len(target_points) or len(target_points) <= 2:
        return target_points

    best_shift = 0
    best_distance = float("inf")
    target_array = np.vstack(target_points)
    source_array = np.vstack(source_points)
    for shift in range(len(target_points) - 1):
        rolled = np.roll(target_array, shift=shift, axis=0)
        rolled[-1] = rolled[0]
        distance = float(np.sum((source_array - rolled) ** 2))
        if distance < best_distance:
            best_distance = distance
            best_shift = shift

    aligned = np.roll(target_array, shift=best_shift, axis=0)
    aligned[-1] = aligned[0]
    return [point.copy() for point in aligned]


def _interpolate_color(
    source_color: tuple[float, float, float] | None,
    target_color: tuple[float, float, float] | None,
    progress: float,
) -> tuple[float, float, float] | None:
    if source_color is None and target_color is None:
        return None
    source = np.array(source_color or target_color, dtype=float)
    target = np.array(target_color or source_color, dtype=float)
    return tuple(((1 - progress) * source + progress * target).tolist())


def _interpolate_point_along_arc(
    start: np.ndarray, end: np.ndarray, progress: float, path_arc: float
) -> np.ndarray:
    if abs(path_arc) < 1e-8:
        return (1 - progress) * start + progress * end

    chord = end - start
    chord_length = float(np.linalg.norm(chord))
    if chord_length <= 1e-9:
        return start.copy()

    tangent = math.tan(path_arc / 2)
    if abs(tangent) < 1e-8:
        return (1 - progress) * start + progress * end

    midpoint = (start + end) / 2
    normal = _rotate_90(chord / chord_length)
    center = midpoint + normal * (chord_length / (2 * tangent))
    relative_start = start - center

    rotation = progress * path_arc
    cos_theta = math.cos(rotation)
    sin_theta = math.sin(rotation)
    rotated = np.array(
        [
            cos_theta * relative_start[0] - sin_theta * relative_start[1],
            sin_theta * relative_start[0] + cos_theta * relative_start[1],
        ],
        dtype=float,
    )
    return center + rotated


class TransformAnimation(AnimationEvent):
    def __init__(
        self,
        target_drawable=None,
        start_time: float = 0.0,
        duration: float = 0.0,
        easing_fun=None,
        data: dict | None = None,
        path_arc: float = 0.0,
        sample_points_per_curve: int = 16,
        min_path_points: int = 8,
        matching_strategy: str = "smart",
        replace_mobject_with_target_in_scene: bool = False,
    ) -> None:
        merged_data = dict(data or {})
        merged_data["path_arc"] = path_arc
        merged_data["matching_strategy"] = matching_strategy
        super().__init__(AnimationEventType.MUTATION, start_time, duration, easing_fun, merged_data)
        self.target_drawable = target_drawable
        self.path_arc = float(path_arc)
        self.sample_points_per_curve = max(int(sample_points_per_curve), 4)
        self.min_path_points = max(int(min_path_points), 2)
        self.matching_strategy = matching_strategy
        self.replace_mobject_with_target_in_scene = replace_mobject_with_target_in_scene
        self._target_opsset: OpsSet | None = None
        self._aligned_cache_key: int | None = None
        self._aligned_source_paths: list[_MorphPath] | None = None
        self._aligned_target_paths: list[_MorphPath] | None = None

    def bind_target_opsset(self, target_opsset: OpsSet) -> None:
        self._target_opsset = _clone_opsset(target_opsset)
        self._aligned_cache_key = None

    def clone_for_target(self, target_drawable):
        event_cls = ReplacementTransformAnimation if self.replace_mobject_with_target_in_scene else TransformAnimation
        return event_cls(
            target_drawable=target_drawable,
            start_time=self.start_time,
            duration=self.duration,
            easing_fun=self.easing_fun,
            data=dict(self.data),
            path_arc=self.path_arc,
            sample_points_per_curve=self.sample_points_per_curve,
            min_path_points=self.min_path_points,
            matching_strategy=self.matching_strategy,
        )

    def pair_drawables(self, source_drawables: list, target_drawables: list, drawable_cache) -> list[tuple[object, object]]:
        source_entries = [
            _DrawableMatchEntry(drawable=drawable, bbox=drawable_cache.get_drawable_opsset(drawable.id).get_bbox())
            for drawable in source_drawables
        ]
        target_entries = [
            _DrawableMatchEntry(drawable=drawable, bbox=drawable_cache.get_drawable_opsset(drawable.id).get_bbox())
            for drawable in target_drawables
        ]
        if not source_entries and not target_entries:
            return []

        cost_matrix = [
            [_drawable_match_cost(source_entry, target_entry) for target_entry in target_entries]
            for source_entry in source_entries
        ]
        pairs: list[tuple[object, object]] = []
        matched_source_indices = set()
        matched_target_indices = set()
        for source_idx, target_idx in _pair_by_greedy_cost(cost_matrix):
            pairs.append((source_entries[source_idx].drawable, target_entries[target_idx].drawable))
            matched_source_indices.add(source_idx)
            matched_target_indices.add(target_idx)

        for source_idx, source_entry in enumerate(source_entries):
            if source_idx not in matched_source_indices:
                pairs.append((source_entry.drawable, None))
        for target_idx, target_entry in enumerate(target_entries):
            if target_idx not in matched_target_indices:
                pairs.append((None, target_entry.drawable))
        return pairs

    def _opsset_to_paths(self, opsset: OpsSet) -> list[_MorphPath]:
        paths: list[_MorphPath] = []
        current_style = _MorphStyle()
        current_points: list[np.ndarray] = []
        current_closed = False
        current_point: np.ndarray | None = None
        first_point: np.ndarray | None = None

        def flush_current_path() -> None:
            nonlocal current_points, current_closed, current_point, first_point
            if current_points:
                paths.append(
                    _MorphPath(
                        points=[point.copy() for point in current_points],
                        style=current_style,
                        closed=current_closed,
                    )
                )
            current_points = []
            current_closed = False
            current_point = None
            first_point = None

        for op in opsset.opsset:
            if op.type == OpsType.SET_PEN:
                flush_current_path()
                current_style = _style_from_pen_data(op.data)
            elif op.type == OpsType.MOVE_TO:
                flush_current_path()
                current_point = np.array(op.data[0], dtype=float)
                first_point = current_point.copy()
                current_points = [current_point.copy()]
            elif op.type == OpsType.LINE_TO and current_point is not None:
                end = np.array(op.data[0], dtype=float)
                current_points.append(end.copy())
                current_point = end
            elif op.type == OpsType.CURVE_TO and current_point is not None:
                p1 = np.array(op.data[0], dtype=float)
                p2 = np.array(op.data[1], dtype=float)
                p3 = np.array(op.data[2], dtype=float)
                current_points.extend(
                    _sample_curve_points(
                        current_point, p1, p2, p3, self.sample_points_per_curve
                    )[1:]
                )
                current_point = p3
            elif op.type == OpsType.QUAD_CURVE_TO and current_point is not None:
                q1 = np.array(op.data[0], dtype=float)
                q2 = np.array(op.data[1], dtype=float)
                p1 = current_point / 3 + 2 * q1 / 3
                p2 = q1 / 3 + 2 * q2 / 3
                p3 = q2
                current_points.extend(
                    _sample_curve_points(
                        current_point, p1, p2, p3, self.sample_points_per_curve
                    )[1:]
                )
                current_point = p3
            elif op.type == OpsType.CLOSE_PATH and first_point is not None:
                if current_point is None or not np.allclose(current_point, first_point):
                    current_points.append(first_point.copy())
                current_closed = True
            elif op.type == OpsType.DOT:
                flush_current_path()
                center = np.array(op.data.get("center", (0, 0)), dtype=float)
                radius = float(op.data.get("radius", 1.0))
                dot_points = [
                    center + radius * np.array([math.cos(angle), math.sin(angle)])
                    for angle in np.linspace(0.0, 2 * np.pi, 24, endpoint=False)
                ]
                dot_points.append(dot_points[0].copy())
                paths.append(_MorphPath(points=dot_points, style=current_style, closed=True))
            elif op.type in {OpsType.IMAGE, OpsType.VIDEO}:
                msg = "TransformAnimation does not support morphing Image or Video drawables"
                raise NotImplementedError(msg)

        flush_current_path()
        return paths

    def _degenerate_path(self, center: np.ndarray, template: _MorphPath | None = None) -> _MorphPath:
        point_count = self.min_path_points
        if template is not None:
            point_count = max(len(template.points), self.min_path_points)
        return _MorphPath(
            points=[center.copy() for _ in range(point_count)],
            style=template.style if template is not None else _MorphStyle(),
            closed=template.closed if template is not None else False,
        )

    def _align_paths(self, source_opsset: OpsSet) -> None:
        source_paths = self._opsset_to_paths(source_opsset)
        target_paths = self._opsset_to_paths(self._target_opsset or OpsSet(initial_set=[]))

        source_center = _path_center(source_paths)
        target_center = _path_center(target_paths)
        paired_source_paths: list[_MorphPath] = []
        paired_target_paths: list[_MorphPath] = []

        if self.matching_strategy == "smart" and source_paths and target_paths:
            cost_matrix = [
                [_path_match_cost(source_path, target_path) for target_path in target_paths]
                for source_path in source_paths
            ]
            matched_source_indices = set()
            matched_target_indices = set()
            for source_idx, target_idx in _pair_by_greedy_cost(cost_matrix):
                paired_source_paths.append(source_paths[source_idx])
                paired_target_paths.append(target_paths[target_idx])
                matched_source_indices.add(source_idx)
                matched_target_indices.add(target_idx)
            for source_idx, source_path in enumerate(source_paths):
                if source_idx not in matched_source_indices:
                    paired_source_paths.append(source_path)
                    paired_target_paths.append(self._degenerate_path(target_center, source_path))
            for target_idx, target_path in enumerate(target_paths):
                if target_idx not in matched_target_indices:
                    paired_source_paths.append(self._degenerate_path(source_center, target_path))
                    paired_target_paths.append(target_path)
        else:
            target_count = max(len(source_paths), len(target_paths), 1)
            while len(source_paths) < target_count:
                template = target_paths[len(source_paths)] if len(target_paths) > len(source_paths) else None
                source_paths.append(self._degenerate_path(source_center, template))
            while len(target_paths) < target_count:
                template = source_paths[len(target_paths)] if len(source_paths) > len(target_paths) else None
                target_paths.append(self._degenerate_path(target_center, template))
            paired_source_paths = source_paths
            paired_target_paths = target_paths

        aligned_source: list[_MorphPath] = []
        aligned_target: list[_MorphPath] = []
        for source_path, target_path in zip(paired_source_paths, paired_target_paths, strict=False):
            target_point_count = max(
                len(source_path.points), len(target_path.points), self.min_path_points
            )
            source_points = _resample_polyline(source_path.points, target_point_count, source_path.closed)
            target_points = _resample_polyline(target_path.points, target_point_count, target_path.closed)
            if source_path.closed and target_path.closed:
                target_points = _best_cyclic_shift(source_points, target_points)

            aligned_source.append(
                _MorphPath(points=source_points, style=source_path.style, closed=source_path.closed)
            )
            aligned_target.append(
                _MorphPath(points=target_points, style=target_path.style, closed=target_path.closed)
            )

        self._aligned_source_paths = aligned_source
        self._aligned_target_paths = aligned_target
        self._aligned_cache_key = id(source_opsset)

    def apply(self, opsset: OpsSet, progress: float) -> OpsSet:
        if self.easing_fun is not None:
            progress = float(self.easing_fun(progress))
        progress = float(np.clip(progress, 0.0, 1.0))
        if progress <= 0:
            return _clone_opsset(opsset)
        if self._target_opsset is None:
            msg = "TransformAnimation target opsset has not been bound by Scene.add()"
            raise ValueError(msg)
        if progress >= 1:
            return _clone_opsset(self._target_opsset)

        if self._aligned_cache_key != id(opsset):
            self._align_paths(opsset)

        interpolated_ops = OpsSet(initial_set=[])
        assert self._aligned_source_paths is not None
        assert self._aligned_target_paths is not None
        for source_path, target_path in zip(
            self._aligned_source_paths, self._aligned_target_paths, strict=False
        ):
            color = _interpolate_color(source_path.style.color, target_path.style.color, progress)
            width = (1 - progress) * source_path.style.width + progress * target_path.style.width
            opacity = (1 - progress) * source_path.style.opacity + progress * target_path.style.opacity
            mode = source_path.style.mode if progress < 0.5 else target_path.style.mode
            interpolated_ops.add(
                Ops(
                    OpsType.SET_PEN,
                    {"mode": mode, "color": color, "opacity": opacity, "width": width},
                )
            )

            interpolated_points = [
                _interpolate_point_along_arc(source_point, target_point, progress, self.path_arc)
                for source_point, target_point in zip(source_path.points, target_path.points, strict=False)
            ]
            if not interpolated_points:
                continue
            interpolated_ops.add(Ops(OpsType.MOVE_TO, [tuple(interpolated_points[0])]))
            for point in interpolated_points[1:]:
                interpolated_ops.add(Ops(OpsType.LINE_TO, [tuple(point)]))
            if source_path.closed or target_path.closed:
                interpolated_ops.add(Ops(OpsType.CLOSE_PATH, {}))

        return interpolated_ops


class ReplacementTransformAnimation(TransformAnimation):
    def __init__(self, target_drawable, *args, **kwargs) -> None:
        kwargs["replace_mobject_with_target_in_scene"] = True
        super().__init__(target_drawable, *args, **kwargs)


MorphAnimation = TransformAnimation
