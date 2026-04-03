import atexit
import json
import tempfile
import webbrowser
from collections import OrderedDict
from enum import Enum
from pathlib import Path
from typing import Any

import cairo
import imageio.v2 as imageio
import numpy as np

from .camera_3d import ThreeDCamera
from .utils import (
    get_bezier_extreme_points,
    get_bezier_points_from_quadcurve,
    slice_bezier,
)
from .viewport import Viewport


_IMAGE_SURFACE_CACHE: dict[str, tuple[cairo.ImageSurface, np.ndarray]] = {}
_VIDEO_READER_CACHE: dict[str, Any] = {}
_VIDEO_META_CACHE: dict[str, dict[str, float | int | None]] = {}
_VIDEO_FRAME_SURFACE_CACHE: OrderedDict[tuple[str, int], tuple[cairo.ImageSurface, np.ndarray]] = (
    OrderedDict()
)
_VIDEO_FRAME_CACHE_SIZE = 32


def _normalize_media_path(media_path: str) -> str:
    resolved_path = Path(media_path).expanduser().resolve()
    if not resolved_path.exists():
        msg = f"Media file does not exist: {media_path}"
        raise FileNotFoundError(msg)
    return str(resolved_path)


def _normalize_to_rgba(frame: np.ndarray) -> np.ndarray:
    data = np.asarray(frame)

    if np.issubdtype(data.dtype, np.floating):
        max_value = float(np.nanmax(data)) if data.size > 0 else 1.0
        if max_value <= 1.0:
            data = np.clip(data, 0.0, 1.0) * 255
        else:
            data = np.clip(data, 0.0, 255.0)
        data = data.astype(np.uint8)
    elif data.dtype != np.uint8:
        data = np.clip(data, 0, 255).astype(np.uint8)

    if data.ndim == 4:
        data = data[0]

    if data.ndim == 2:
        rgb = np.stack([data, data, data], axis=-1)
        alpha = np.full((*data.shape, 1), 255, dtype=np.uint8)
        return np.concatenate([rgb, alpha], axis=-1)

    if data.ndim != 3:
        msg = f"Unsupported media frame format with shape {data.shape}"
        raise ValueError(msg)

    channels = data.shape[2]
    if channels == 4:
        return data
    if channels == 3:
        alpha = np.full((data.shape[0], data.shape[1], 1), 255, dtype=np.uint8)
        return np.concatenate([data, alpha], axis=-1)
    if channels == 1:
        rgb = np.repeat(data, 3, axis=2)
        alpha = np.full((data.shape[0], data.shape[1], 1), 255, dtype=np.uint8)
        return np.concatenate([rgb, alpha], axis=-1)

    msg = f"Unsupported media frame channel count: {channels}"
    raise ValueError(msg)


def _rgba_to_cairo_surface(rgba_frame: np.ndarray) -> tuple[cairo.ImageSurface, np.ndarray]:
    if rgba_frame.ndim != 3 or rgba_frame.shape[2] != 4:
        msg = "Expected RGBA frame with shape (height, width, 4)"
        raise ValueError(msg)

    bgra = np.ascontiguousarray(rgba_frame[:, :, [2, 1, 0, 3]])
    alpha = bgra[:, :, 3:4].astype(np.uint16)
    bgra[:, :, :3] = ((bgra[:, :, :3].astype(np.uint16) * alpha) // 255).astype(np.uint8)
    surface = cairo.ImageSurface.create_for_data(
        bgra,
        cairo.FORMAT_ARGB32,
        int(bgra.shape[1]),
        int(bgra.shape[0]),
        int(bgra.strides[0]),
    )
    return surface, bgra


def _get_image_surface(media_path: str) -> cairo.ImageSurface:
    normalized_path = _normalize_media_path(media_path)
    if normalized_path not in _IMAGE_SURFACE_CACHE:
        image_array = imageio.imread(normalized_path)
        rgba = _normalize_to_rgba(np.asarray(image_array))
        surface, buffer = _rgba_to_cairo_surface(rgba)
        _IMAGE_SURFACE_CACHE[normalized_path] = (surface, buffer)
    return _IMAGE_SURFACE_CACHE[normalized_path][0]


def _get_video_reader(media_path: str):
    normalized_path = _normalize_media_path(media_path)
    if normalized_path not in _VIDEO_READER_CACHE:
        _VIDEO_READER_CACHE[normalized_path] = imageio.get_reader(normalized_path)
    return _VIDEO_READER_CACHE[normalized_path]


def _get_video_meta(media_path: str) -> dict[str, float | int | None]:
    normalized_path = _normalize_media_path(media_path)
    if normalized_path in _VIDEO_META_CACHE:
        return _VIDEO_META_CACHE[normalized_path]

    reader = _get_video_reader(normalized_path)
    raw_meta = reader.get_meta_data() or {}

    fps = raw_meta.get("fps")
    try:
        fps = float(fps) if fps is not None else 24.0
    except (TypeError, ValueError):
        fps = 24.0

    nframes = raw_meta.get("nframes")
    if isinstance(nframes, float) and np.isinf(nframes):
        nframes = None
    if nframes is not None:
        try:
            nframes = int(nframes)
        except (TypeError, ValueError):
            nframes = None
    if nframes is None or nframes <= 0:
        try:
            nframes = int(reader.count_frames())
        except Exception:
            nframes = None

    _VIDEO_META_CACHE[normalized_path] = {
        "fps": fps,
        "nframes": nframes,
    }
    return _VIDEO_META_CACHE[normalized_path]


def _resolve_video_frame_index(
    video_data: dict[str, Any],
    render_context: dict[str, Any] | None,
    video_meta: dict[str, float | int | None],
) -> int | None:
    if render_context is None:
        render_context = {}

    scene_time = float(render_context.get("scene_time", 0.0))
    scene_fps = float(render_context.get("fps", 24.0))
    scene_start = float(video_data.get("scene_start", 0.0))
    if scene_time < scene_start:
        return None

    source_start = float(video_data.get("source_start", 0.0))
    playback_rate = float(video_data.get("playback_rate", 1.0))
    playback_rate = max(playback_rate, 1e-9)

    override_source_fps = video_data.get("source_fps", None)
    if override_source_fps is not None:
        try:
            video_fps = float(override_source_fps)
        except (TypeError, ValueError):
            video_fps = float(video_meta.get("fps") or scene_fps)
    else:
        video_fps = float(video_meta.get("fps") or scene_fps)

    elapsed_scene = max(scene_time - scene_start, 0.0)
    source_time = max(source_start + elapsed_scene * playback_rate, 0.0)
    frame_index = int(np.floor(source_time * video_fps + 1e-8))

    nframes = video_meta.get("nframes")
    if isinstance(nframes, int) and nframes > 0:
        loop = bool(video_data.get("loop", True))
        if loop:
            frame_index = frame_index % nframes
        else:
            frame_index = int(np.clip(frame_index, 0, nframes - 1))

    return frame_index


def _get_video_frame_surface(media_path: str, frame_index: int) -> cairo.ImageSurface:
    normalized_path = _normalize_media_path(media_path)
    cache_key = (normalized_path, frame_index)
    if cache_key in _VIDEO_FRAME_SURFACE_CACHE:
        _VIDEO_FRAME_SURFACE_CACHE.move_to_end(cache_key)
        return _VIDEO_FRAME_SURFACE_CACHE[cache_key][0]

    reader = _get_video_reader(normalized_path)
    video_meta = _get_video_meta(normalized_path)

    try:
        frame = reader.get_data(frame_index)
    except IndexError:
        nframes = video_meta.get("nframes")
        if isinstance(nframes, int) and nframes > 0:
            frame_index = int(np.clip(frame_index, 0, nframes - 1))
            frame = reader.get_data(frame_index)
        else:
            frame = reader.get_data(0)

    rgba = _normalize_to_rgba(np.asarray(frame))
    surface, buffer = _rgba_to_cairo_surface(rgba)
    _VIDEO_FRAME_SURFACE_CACHE[cache_key] = (surface, buffer)
    _VIDEO_FRAME_SURFACE_CACHE.move_to_end(cache_key)

    if len(_VIDEO_FRAME_SURFACE_CACHE) > _VIDEO_FRAME_CACHE_SIZE:
        _VIDEO_FRAME_SURFACE_CACHE.popitem(last=False)

    return surface


def _draw_surface_on_points(
    ctx: cairo.Context,
    surface: cairo.ImageSurface,
    points: list[tuple[float, float]],
    opacity: float,
) -> None:
    if len(points) < 3 or opacity <= 0:
        return

    p0 = (float(points[0][0]), float(points[0][1]))
    p1 = (float(points[1][0]), float(points[1][1]))
    p2 = (float(points[2][0]), float(points[2][1]))

    surface_width = surface.get_width()
    surface_height = surface.get_height()
    if surface_width <= 0 or surface_height <= 0:
        return

    xx = (p1[0] - p0[0]) / surface_width
    yx = (p1[1] - p0[1]) / surface_width
    xy = (p2[0] - p0[0]) / surface_height
    yy = (p2[1] - p0[1]) / surface_height

    ctx.save()
    ctx.translate(*p0)
    ctx.transform(cairo.Matrix(xx=xx, yx=yx, xy=xy, yy=yy, x0=0, y0=0))
    ctx.rectangle(0, 0, surface_width, surface_height)
    ctx.clip()
    ctx.set_source_surface(surface, 0, 0)
    if opacity < 1.0:
        ctx.paint_with_alpha(opacity)
    else:
        ctx.paint()
    ctx.restore()


@atexit.register
def _cleanup_video_readers() -> None:
    for reader in _VIDEO_READER_CACHE.values():
        try:
            reader.close()
        except Exception:
            continue


class OpsType(Enum):
    SET_PEN = "set_pen"
    MOVE_TO = "move_to"
    METADATA = "metadata"
    # this is a dummy opsset that does nothing except hold some metadata
    LINE_TO = "line_to"
    CURVE_TO = "curve_to"
    QUAD_CURVE_TO = "quad_curve_to"
    CLOSE_PATH = "close_path"
    DOT = "dot"
    IMAGE = "image"
    VIDEO = "video"
    POLYGON_3D = "polygon_3d"
    POLYLINE_3D = "polyline_3d"


def _normalize_vector(vector: np.ndarray) -> np.ndarray:
    norm = float(np.linalg.norm(vector))
    if norm <= 1e-9:
        return np.zeros_like(vector, dtype=float)
    return np.asarray(vector, dtype=float) / norm


def _rotation_matrix_3d(
    axis: tuple[float, float, float] | np.ndarray, angle_degrees: float
) -> np.ndarray:
    unit_axis = _normalize_vector(np.array(axis, dtype=float))
    if np.linalg.norm(unit_axis) <= 1e-9:
        return np.identity(3, dtype=float)

    x_coord, y_coord, z_coord = unit_axis
    angle_radians = float(np.deg2rad(angle_degrees))
    cos_theta = float(np.cos(angle_radians))
    sin_theta = float(np.sin(angle_radians))
    one_minus_cos = 1.0 - cos_theta
    return np.array(
        [
            [
                cos_theta + x_coord * x_coord * one_minus_cos,
                x_coord * y_coord * one_minus_cos - z_coord * sin_theta,
                x_coord * z_coord * one_minus_cos + y_coord * sin_theta,
            ],
            [
                y_coord * x_coord * one_minus_cos + z_coord * sin_theta,
                cos_theta + y_coord * y_coord * one_minus_cos,
                y_coord * z_coord * one_minus_cos - x_coord * sin_theta,
            ],
            [
                z_coord * x_coord * one_minus_cos - y_coord * sin_theta,
                z_coord * y_coord * one_minus_cos + x_coord * sin_theta,
                cos_theta + z_coord * z_coord * one_minus_cos,
            ],
        ],
        dtype=float,
    )


def _build_path_ops(
    points: list[tuple[float, float]],
    close: bool,
    color: tuple[float, float, float] | None,
    opacity: float,
    width: float,
    mode: str,
) -> "OpsSet":
    opsset = OpsSet(initial_set=[])
    if not points or color is None or opacity <= 0:
        return opsset
    if mode == "stroke" and width <= 0:
        return opsset
    opsset.add(
        Ops(
            type=OpsType.SET_PEN,
            data={
                "color": tuple(color),
                "opacity": float(opacity),
                "width": float(width),
                "mode": mode,
            },
        )
    )
    opsset.add(Ops(type=OpsType.MOVE_TO, data=[points[0]]))
    for point in points[1:]:
        opsset.add(Ops(type=OpsType.LINE_TO, data=[point]))
    if close:
        opsset.add(Ops(type=OpsType.CLOSE_PATH, data=None))
    return opsset


def _shade_color(
    base_color: tuple[float, float, float] | None,
    normal: np.ndarray,
    face_center: np.ndarray,
    light_source: np.ndarray,
    shading_factor: float,
) -> tuple[float, float, float] | None:
    if base_color is None:
        return None
    normal_unit = _normalize_vector(normal)
    if np.linalg.norm(normal_unit) <= 1e-9:
        return (float(base_color[0]), float(base_color[1]), float(base_color[2]))
    light_direction = _normalize_vector(
        np.array(light_source, dtype=float) - np.array(face_center, dtype=float)
    )
    diffuse = max(float(np.dot(normal_unit, light_direction)), 0.0)
    brightness = (1.0 - shading_factor) + shading_factor * diffuse
    shaded = np.clip(np.array(base_color, dtype=float) * brightness, 0.0, 1.0)
    return (float(shaded[0]), float(shaded[1]), float(shaded[2]))


def _interpolate_to_z_plane(point_a: np.ndarray, point_b: np.ndarray, max_z: float) -> np.ndarray:
    delta_z = float(point_b[2] - point_a[2])
    if abs(delta_z) <= 1e-9:
        return np.array(point_a, dtype=float)
    alpha = np.clip((max_z - point_a[2]) / delta_z, 0.0, 1.0)
    return np.array(point_a + alpha * (point_b - point_a), dtype=float)


def _clip_polygon_to_max_z(points: np.ndarray, max_z: float) -> np.ndarray:
    if len(points) == 0:
        return np.empty((0, 3), dtype=float)

    clipped_points: list[np.ndarray] = []
    previous_point = np.array(points[-1], dtype=float)
    previous_inside = bool(previous_point[2] <= max_z)

    for current_point_raw in points:
        current_point = np.array(current_point_raw, dtype=float)
        current_inside = bool(current_point[2] <= max_z)

        if current_inside:
            if not previous_inside:
                clipped_points.append(_interpolate_to_z_plane(previous_point, current_point, max_z))
            clipped_points.append(current_point)
        elif previous_inside:
            clipped_points.append(_interpolate_to_z_plane(previous_point, current_point, max_z))

        previous_point = current_point
        previous_inside = current_inside

    if not clipped_points:
        return np.empty((0, 3), dtype=float)
    return np.array(clipped_points, dtype=float)


def _clip_polyline_to_max_z(
    points: np.ndarray, max_z: float, closed: bool = False
) -> list[np.ndarray]:
    if len(points) < 2:
        return []

    point_list = [np.array(point, dtype=float) for point in points]
    segment_pairs = list(zip(point_list[:-1], point_list[1:]))
    if closed:
        segment_pairs.append((point_list[-1], point_list[0]))

    clipped_paths: list[list[np.ndarray]] = []
    current_path: list[np.ndarray] = []

    for point_a, point_b in segment_pairs:
        a_inside = bool(point_a[2] <= max_z)
        b_inside = bool(point_b[2] <= max_z)

        if a_inside and b_inside:
            if not current_path:
                current_path.append(point_a)
            current_path.append(point_b)
            continue

        if a_inside and not b_inside:
            if not current_path:
                current_path.append(point_a)
            current_path.append(_interpolate_to_z_plane(point_a, point_b, max_z))
            if len(current_path) >= 2:
                clipped_paths.append(current_path)
            current_path = []
            continue

        if (not a_inside) and b_inside:
            current_path = [_interpolate_to_z_plane(point_a, point_b, max_z), point_b]
            continue

        if len(current_path) >= 2:
            clipped_paths.append(current_path)
        current_path = []

    if len(current_path) >= 2:
        clipped_paths.append(current_path)

    return [np.array(path, dtype=float) for path in clipped_paths]


class Ops:
    """
    Represents a drawing operation to be performed in the animation system.

    Attributes:
        SETUP_OPS_TYPES (List[OpsType]): Types of operations considered setup operations.
        type (OpsType): The type of drawing operation.
        data (Any): The data used to perform the drawing operation.
        partial (float, optional): Fraction of the operation to be performed, defaults to 1.0.
    """

    SETUP_OPS_TYPES = [OpsType.SET_PEN, OpsType.MOVE_TO, OpsType.METADATA]

    def __init__(
        self, type: OpsType, data: Any, partial: float = 1.0, meta: dict | None = None
    ) -> None:
        self.type = type
        self.data = data  # the data to use to perform draw operation
        self.partial = partial  # how much of the ops needs to be performed
        self.meta = meta

    def __repr__(self) -> str:
        if isinstance(self.data, (list, np.ndarray)):
            rounded_data = [[np.round(x, 2) for x in point] for point in self.data]
        else:
            rounded_data = self.data
        return f"Ops({self.type}, {json.dumps(rounded_data)}, {self.partial})"


_OPS_3D_TYPES = frozenset({OpsType.POLYGON_3D, OpsType.POLYLINE_3D})


class OpsSet:
    """
    Represents a collection of drawing operations with methods for manipulation and rendering.

    Provides functionality to:
    - Add, extend, and manage a list of drawing operations
    - Calculate bounding box and center of gravity
    - Perform transformations like translation, scaling, and rotation
    - Render operations to a Cairo context

    Attributes:
        opsset (List[Ops]): A list of drawing operations to be performed.
    """

    def __init__(
        self,
        initial_set: list[Ops] | None = None,
        *,
        has_3d_ops: bool | None = None,
    ) -> None:
        if initial_set is None:
            initial_set = []
        self.opsset: list[Ops] = initial_set
        if has_3d_ops is None:
            self._has_3d_ops = any(op.type in _OPS_3D_TYPES for op in initial_set)
        else:
            self._has_3d_ops = bool(has_3d_ops)

    def __repr__(self) -> str:
        if len(self.opsset) <= 10:
            return "OpsSet:" + "\n\t".join([str(ops) for ops in self.opsset])
        return (
            "OpsSet:\n"
            + "\n".join([str(ops) for ops in self.opsset[:5]])
            + f"\n\t(... {len(self.opsset) - 10} more rows)\n"
            + "\n".join([str(ops) for ops in self.opsset[-5:]])
        )

    def add_meta(self, meta: dict | None = None) -> None:
        if meta is None:
            meta = {}
        for ops in self.opsset:
            if ops.meta is None:
                ops.meta = meta
            ops.meta.update(meta)  # merge the key and values

    def filter_by_meta_query(self, meta_key: str, meta_value: Any) -> "OpsSet":
        new_opsset: list[Ops] = []
        has_3d_ops = False
        for ops in self.opsset:
            if ops.meta is None:
                continue
            if ops.meta.get(meta_key) == meta_value:
                new_opsset.append(ops)
                has_3d_ops = has_3d_ops or ops.type in _OPS_3D_TYPES
        return OpsSet(new_opsset, has_3d_ops=has_3d_ops)

    def add(self, ops: Ops | dict) -> None:
        if isinstance(ops, dict):
            ops = Ops(**ops)
        self.opsset.append(ops)
        if ops.type in _OPS_3D_TYPES:
            self._has_3d_ops = True

    def extend(self, other_opsset: Any) -> None:
        if isinstance(other_opsset, OpsSet):
            self.opsset.extend(other_opsset.opsset)
            if other_opsset._has_3d_ops:
                self._has_3d_ops = True
        else:
            msg = "other value is not an opsset"
            raise TypeError(msg)

    def clone(self) -> "OpsSet":
        """Return a shallow structural copy of the opsset."""
        return OpsSet(initial_set=list(self.opsset), has_3d_ops=self._has_3d_ops)

    def get_meta_chunks(self, meta_key: str) -> list[tuple[Any | None, "OpsSet"]]:
        chunks: list[tuple[Any | None, OpsSet]] = []
        current_chunk: list[Ops] = []
        current_value: Any | None = None

        for ops in self.opsset:
            value = ops.meta.get(meta_key) if ops.meta is not None else None
            if not current_chunk:
                current_chunk = [ops]
                current_value = value
                continue
            if value == current_value:
                current_chunk.append(ops)
                continue
            chunks.append((current_value, OpsSet(initial_set=current_chunk)))
            current_chunk = [ops]
            current_value = value

        if current_chunk:
            chunks.append((current_value, OpsSet(initial_set=current_chunk)))
        return chunks

    def has_3d_ops(self) -> bool:
        return self._has_3d_ops

    def transform_points(self, point_transform) -> None:
        """Apply a pointwise transformation to supported point-bearing ops."""

        def _normalize_point(point):
            new_point = point_transform((float(point[0]), float(point[1])))
            return (float(new_point[0]), float(new_point[1]))

        new_ops = []
        for ops in self.opsset:
            if isinstance(ops.data, list):
                new_data = [_normalize_point(point) for point in ops.data]
                new_ops.append(Ops(ops.type, new_data, ops.partial, ops.meta))
            elif isinstance(ops.data, dict) and isinstance(ops.data.get("points"), list):
                new_data = dict(ops.data)
                new_data["points"] = [
                    _normalize_point(point) for point in ops.data.get("points", [])
                ]
                new_ops.append(Ops(ops.type, new_data, ops.partial, ops.meta))
            elif isinstance(ops.data, dict) and "center" in ops.data:
                new_data = dict(ops.data)
                new_data["center"] = _normalize_point(ops.data.get("center", (0, 0)))
                new_ops.append(Ops(ops.type, new_data, ops.partial, ops.meta))
            else:
                new_ops.append(ops)
        self.opsset = new_ops

    def transform_points_3d(self, point_transform) -> None:
        """Apply a pointwise transformation to 3D point-bearing ops."""

        def _normalize_point(point):
            new_point = point_transform(np.array(point, dtype=float))
            return (
                float(new_point[0]),
                float(new_point[1]),
                float(new_point[2]),
            )

        new_ops = []
        for ops in self.opsset:
            if isinstance(ops.data, dict) and isinstance(ops.data.get("points"), list):
                sample_points = ops.data.get("points", [])
                if sample_points and len(sample_points[0]) == 3:
                    new_data = dict(ops.data)
                    new_data["points"] = [_normalize_point(point) for point in sample_points]
                    new_ops.append(Ops(ops.type, new_data, ops.partial, ops.meta))
                    continue
            new_ops.append(ops)
        self.opsset = new_ops

    def get_bbox(self) -> tuple[float, float, float, float]:
        """
        Calculate the bounding box that encompasses all points in the operations set.

        Returns:
            A tuple of (min_x, min_y, max_x, max_y) representing the coordinates
            of the bounding box. Returns (0, 0, 0, 0) if the operations set is empty.

        Note:
            Currently supports only list-type point data. Curve calculations
            are not fully implemented.
        """
        if len(self.opsset) == 0:
            return (0, 0, 0, 0)
        min_x = min_y = float("inf")
        max_x = max_y = float("-inf")
        current_point = (0, 0)
        for ops in self.opsset:
            if ops.type in [OpsType.CURVE_TO, OpsType.QUAD_CURVE_TO]:
                p0 = current_point  # current point is the start of the curve
                p1: tuple[float, float]
                p2: tuple[float, float]
                p3: tuple[float, float]
                if ops.type == OpsType.CURVE_TO:
                    p1, p2, p3 = ops.data
                else:  # QUAD_CURVE_TO
                    q1, q2 = ops.data
                    p1, p2, p3 = get_bezier_points_from_quadcurve(p0, q1, q2)
                current_point = p3  # update current point to end of curve
                # now get the range
                xmin, xmax, ymin, ymax = get_bezier_extreme_points(p0, p1, p2, p3)
                min_x = min(min_x, xmin)
                max_x = max(max_x, xmax)
                min_y = min(min_y, ymin)
                max_y = max(max_y, ymax)
            else:
                data = ops.data
                points: list[tuple[float, float]] = []
                if isinstance(data, list):
                    points = [(float(point[0]), float(point[1])) for point in data]
                elif isinstance(data, dict) and isinstance(data.get("points"), list):
                    data_points = [
                        (float(point[0]), float(point[1])) for point in data.get("points", [])
                    ]
                    points = data_points

                    # For media ops we track a parallelogram with p0, p1, p2;
                    # include the implicit p3 in bbox calculations.
                    if len(data_points) >= 3:
                        p0, p1, p2 = data_points[:3]
                        points.append((p1[0] + p2[0] - p0[0], p1[1] + p2[1] - p0[1]))

                for point in points:
                    # update current point
                    current_point = point

                    # update bounding box
                    min_x = min(min_x, point[0])
                    min_y = min(min_y, point[1])
                    max_x = max(max_x, point[0])
                    max_y = max(max_y, point[1])
        return float(min_x), float(min_y), float(max_x), float(max_y)

    def get_center_of_gravity(self) -> tuple[float, float]:
        """
        Calculate the approximate geometric center of the operations set.

        Returns:
            A tuple of (x, y) coordinates representing the center point,
            computed as the midpoint of the bounding box.
        """
        min_x, min_y, max_x, max_y = self.get_bbox()
        return (min_x + max_x) / 2, (min_y + max_y) / 2

    def get_bbox_3d(self) -> tuple[float, float, float, float, float, float]:
        min_x = min_y = min_z = float("inf")
        max_x = max_y = max_z = float("-inf")
        found_point = False
        for ops in self.opsset:
            if not isinstance(ops.data, dict) or not isinstance(ops.data.get("points"), list):
                continue
            for point in ops.data.get("points", []):
                if len(point) != 3:
                    continue
                found_point = True
                min_x = min(min_x, float(point[0]))
                min_y = min(min_y, float(point[1]))
                min_z = min(min_z, float(point[2]))
                max_x = max(max_x, float(point[0]))
                max_y = max(max_y, float(point[1]))
                max_z = max(max_z, float(point[2]))
        if not found_point:
            return (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
        return (min_x, min_y, min_z, max_x, max_y, max_z)

    def get_center_of_gravity_3d(self) -> tuple[float, float, float]:
        min_x, min_y, min_z, max_x, max_y, max_z = self.get_bbox_3d()
        return (
            (min_x + max_x) / 2,
            (min_y + max_y) / 2,
            (min_z + max_z) / 2,
        )

    def get_last_ops(self, start_index: int = 0) -> tuple[float | None, Ops | None]:
        """
        Retrieve the last valid operation from the operations set.

        Args:
            start_index (int, optional): Starting index for searching backwards. Defaults to 0.

        Returns:
            Tuple[Optional[float], Optional[Ops]]: A tuple containing the index and the last valid operation.
            Returns (None, None) if no valid operation is found.

        Note:
            Valid operations include MOVE_TO, LINE_TO, CURVE_TO, and QUAD_CURVE_TO.
        """
        if start_index >= len(self.opsset):
            return None, None
        for index, ops in enumerate(self.opsset[::-1][start_index:]):
            if ops.type in {
                OpsType.MOVE_TO,
                OpsType.LINE_TO,
                OpsType.CURVE_TO,
                OpsType.QUAD_CURVE_TO,
            }:
                return index, ops
        return None, None

    def get_current_point(self):
        """
        Retrieves the current drawing point from the last operation in the operations set.

        Returns:
            A tuple (x, y) representing the current drawing point, considering partial operations
            and different types of drawing operations (move, line, curve, quadratic curve).
            Returns (0, 0) if no valid point can be determined.
        """
        if len(self.opsset) == 0:
            return (0, 0)
        last_index, last_op = self.get_last_ops()
        if last_op is None:
            return (0, 0)

        second_last_op = (
            self.get_last_ops(int(last_index) + 1)[1] if last_index is not None else None
        )
        if second_last_op is None:
            return last_op.data[0]
        if last_op.type == OpsType.MOVE_TO:
            return last_op.data[0]
        if last_op.type == OpsType.LINE_TO:
            if last_op.partial < 1:
                x0, y0 = second_last_op.data[0]
                x1, y1 = last_op.data[0]
                x = x0 + last_op.partial * (x1 - x0)  # calculate vectors
                y = y0 + last_op.partial * (y1 - y0)
                return (x, y)
            return last_op.data[0]
        if last_op.type == OpsType.CURVE_TO:
            if last_op.partial < 1:
                p0 = second_last_op.data[0]
                p1, p2, p3 = last_op.data[0], last_op.data[1], last_op.data[2]
                cp1, cp2, ep = slice_bezier(p0, p1, p2, p3, float(last_op.partial))
                return ep
            return last_op.data[-1]
        if last_op.type == OpsType.QUAD_CURVE_TO:
            if last_op.partial < 1:
                p0 = second_last_op.data[0]
                q1, q2 = last_op.data[0], last_op.data[1]
                p1, p2, p3 = get_bezier_points_from_quadcurve(p0, q1, q2)
                _cp1, _cp2, ep = slice_bezier(p0, p1, p2, p3, float(last_op.partial))
                return ep
            return last_op.data[-1]
        return None

    def translate(self, offset_x: float, offset_y: float) -> None:
        """
        Translates all operations in the opsset by a specified (x, y) offset.

        Applies the translation relative to the current center of gravity of the operations.
        Modifies the operations in-place by adding the offset to each point's coordinates.
        Non-point operations (like set pen type) are preserved without modification.

        Args:
            offset_x (float): The x-axis translation amount
            offset_y (float): The y-axis translation amount
        """
        new_ops = []
        for ops in self.opsset:
            if isinstance(ops.data, list):
                # ops.data is list means, everything is a point
                new_data = [(x + offset_x, y + offset_y) for x, y in ops.data]
                new_ops.append(Ops(ops.type, new_data, ops.partial, ops.meta))
            elif isinstance(ops.data, dict) and isinstance(ops.data.get("points"), list):
                new_data = dict(ops.data)
                new_data["points"] = [
                    (x + offset_x, y + offset_y) for x, y in ops.data.get("points", [])
                ]
                new_ops.append(Ops(ops.type, new_data, ops.partial, ops.meta))
            else:
                new_ops.append(ops)  # keep same ops
        self.opsset = new_ops

    def translate_3d(self, offset_x: float, offset_y: float, offset_z: float) -> None:
        self.transform_points_3d(
            lambda point: np.array(
                [point[0] + offset_x, point[1] + offset_y, point[2] + offset_z],
                dtype=float,
            )
        )

    def scale(self, scale_x: float, scale_y: float | None = None) -> None:
        """
        Scales the operations in the opsset relative to its center of gravity.

        Applies uniform or non-uniform scaling to all point-based operations. If only scale_x is provided,
        the scaling is uniform in both x and y directions. The scaling is performed relative to the
        current center of gravity of the operations.

        Args:
            scale_x (float): The scaling factor for the x-axis.
            scale_y (float, optional): The scaling factor for the y-axis.
                                        Defaults to the same value as scale_x for uniform scaling.
        """
        if scale_y is None:
            scale_y = scale_x

        # first translate so that center of gravity is at (0, 0)
        center_of_gravity = self.get_center_of_gravity()

        # now apply scaling
        new_ops = []
        for ops in self.opsset:
            if isinstance(ops.data, list):
                # ops.data is list means, everything is a point
                new_data = [
                    (
                        center_of_gravity[0] + scale_x * (x - center_of_gravity[0]),
                        center_of_gravity[1] + scale_y * (y - center_of_gravity[1]),
                    )
                    for x, y in ops.data
                ]
                new_ops.append(Ops(ops.type, new_data, ops.partial, ops.meta))
            elif isinstance(ops.data, dict) and isinstance(ops.data.get("points"), list):
                new_data_dict = dict(ops.data)
                new_data_dict["points"] = [
                    (
                        center_of_gravity[0] + scale_x * (x - center_of_gravity[0]),
                        center_of_gravity[1] + scale_y * (y - center_of_gravity[1]),
                    )
                    for x, y in ops.data.get("points", [])
                ]
                new_ops.append(Ops(ops.type, new_data_dict, ops.partial, ops.meta))
            else:
                new_ops.append(ops)  # keep same ops for set pen type operations
        self.opsset = new_ops  # update the ops list

    def scale_3d(
        self,
        scale_x: float,
        scale_y: float | None = None,
        scale_z: float | None = None,
        center_of_scaling: tuple[float, float, float] | None = None,
    ) -> None:
        if scale_y is None:
            scale_y = scale_x
        if scale_z is None:
            scale_z = scale_x
        if center_of_scaling is None:
            center_of_scaling = self.get_center_of_gravity_3d()

        cx, cy, cz = center_of_scaling
        self.transform_points_3d(
            lambda point: np.array(
                [
                    cx + scale_x * (point[0] - cx),
                    cy + scale_y * (point[1] - cy),
                    cz + scale_z * (point[2] - cz),
                ],
                dtype=float,
            )
        )

    def move_to_3d(self, point: tuple[float, float, float] | np.ndarray) -> None:
        cx, cy, cz = self.get_center_of_gravity_3d()
        point_array = np.array(point, dtype=float)
        self.translate_3d(point_array[0] - cx, point_array[1] - cy, point_array[2] - cz)

    def rotate(self, angle: float, center_of_rotation: tuple[float, float] | None = None) -> None:
        """
        Rotates the operations in the opsset by a specified angle around its center of gravity.

        Applies a rotation transformation to all point-based operations relative to the current
        center of gravity. The rotation is performed in degrees and uses a standard 2D rotation matrix.

        Args:
            angle (float): The rotation angle in degrees. Positive values rotate counterclockwise.
        """
        # first translate so that center of gravity is at (0, 0)
        if center_of_rotation is None:
            center_of_rotation = self.get_center_of_gravity()
        rotation_values = [np.cos(np.deg2rad(angle)), np.sin(np.deg2rad(angle))]

        new_ops = []
        for ops in self.opsset:
            if isinstance(ops.data, list):
                # ops.data is list means, everything is a point
                new_data = [
                    (
                        center_of_rotation[0]
                        + rotation_values[0] * (x - center_of_rotation[0])
                        - rotation_values[1] * (y - center_of_rotation[1]),
                        center_of_rotation[1]
                        + rotation_values[1] * (x - center_of_rotation[0])
                        + rotation_values[0] * (y - center_of_rotation[1]),
                    )
                    for x, y in ops.data
                ]  # performs multiplication of rotation matrix explcitly
                new_ops.append(Ops(ops.type, new_data, ops.partial, ops.meta))
            elif isinstance(ops.data, dict) and isinstance(ops.data.get("points"), list):
                new_data_dict = dict(ops.data)
                new_data_dict["points"] = [
                    (
                        center_of_rotation[0]
                        + rotation_values[0] * (x - center_of_rotation[0])
                        - rotation_values[1] * (y - center_of_rotation[1]),
                        center_of_rotation[1]
                        + rotation_values[1] * (x - center_of_rotation[0])
                        + rotation_values[0] * (y - center_of_rotation[1]),
                    )
                    for x, y in ops.data.get("points", [])
                ]
                new_ops.append(Ops(ops.type, new_data_dict, ops.partial, ops.meta))
            else:
                new_ops.append(ops)  # keep same ops for set pen type operations
        self.opsset = new_ops  # update the ops list

    def rotate_3d(
        self,
        angle: float,
        axis: tuple[float, float, float] | np.ndarray = (0.0, 0.0, 1.0),
        center_of_rotation: tuple[float, float, float] | None = None,
    ) -> None:
        if center_of_rotation is None:
            center_of_rotation = self.get_center_of_gravity_3d()
        center_array = np.array(center_of_rotation, dtype=float)
        rotation_matrix = _rotation_matrix_3d(axis=axis, angle_degrees=angle)
        self.transform_points_3d(
            lambda point: center_array
            + rotation_matrix @ (np.array(point, dtype=float) - center_array)
        )

    def project_3d(self, camera: ThreeDCamera) -> "OpsSet":
        projected_ops = OpsSet(initial_set=[], has_3d_ops=False)
        depth_entries: list[tuple[float, OpsSet]] = []
        object_center_world = np.array(self.get_center_of_gravity_3d(), dtype=float)
        object_center_camera = camera.transform_points_to_camera_space(
            np.array([object_center_world], dtype=float)
        )[0]
        near_plane_z = camera.focal_distance - camera.get_near_clip_epsilon()

        for ops in self.opsset:
            if ops.type not in {OpsType.POLYGON_3D, OpsType.POLYLINE_3D}:
                projected_ops.add(ops)
                continue

            point_array = np.array(ops.data.get("points", []), dtype=float)
            if point_array.size == 0:
                continue
            camera_points = camera.transform_points_to_camera_space(point_array)

            if ops.type == OpsType.POLYLINE_3D:
                clipped_paths = _clip_polyline_to_max_z(
                    camera_points,
                    max_z=near_plane_z,
                    closed=bool(ops.data.get("closed", False)),
                )
                for clipped_path in clipped_paths:
                    screen_points, depths = camera.project_camera_space_points(clipped_path)
                    if not np.isfinite(screen_points).all():
                        continue
                    flat_points = [(float(point[0]), float(point[1])) for point in screen_points]
                    depth_value = float(np.mean(depths))
                    path_ops = _build_path_ops(
                        points=flat_points,
                        close=bool(ops.data.get("closed", False)) and len(clipped_paths) == 1,
                        color=ops.data.get("stroke_color"),
                        opacity=float(ops.data.get("stroke_opacity", 1.0)),
                        width=float(ops.data.get("stroke_width", 1.0)),
                        mode="stroke",
                    )
                    path_ops.add_meta({"depth_3d": depth_value})
                    depth_entries.append((depth_value, path_ops))
                continue

            clipped_camera_points = _clip_polygon_to_max_z(camera_points, max_z=near_plane_z)
            if len(clipped_camera_points) < 3:
                continue

            normal_camera = np.cross(
                clipped_camera_points[1] - clipped_camera_points[0],
                clipped_camera_points[2] - clipped_camera_points[0],
            )
            if (
                float(
                    np.dot(
                        normal_camera, np.mean(clipped_camera_points, axis=0) - object_center_camera
                    )
                )
                < 0
            ):
                normal_camera = -normal_camera
            backface_cull = bool(ops.data.get("backface_cull", False))
            visibility_score = float(
                np.dot(
                    normal_camera,
                    np.array([0.0, 0.0, camera.focal_distance], dtype=float)
                    - np.mean(clipped_camera_points, axis=0),
                )
            )
            if backface_cull and visibility_score <= 1e-9:
                continue

            screen_points, depths = camera.project_camera_space_points(clipped_camera_points)
            if not np.isfinite(screen_points).all():
                continue
            flat_points = [(float(point[0]), float(point[1])) for point in screen_points]
            face_center = np.mean(point_array, axis=0)
            if len(point_array) >= 3:
                normal = np.cross(point_array[1] - point_array[0], point_array[2] - point_array[0])
                if float(np.dot(normal, face_center - object_center_world)) < 0:
                    normal = -normal
            else:
                normal = np.array([0.0, 0.0, 1.0], dtype=float)
            shading_factor = ops.data.get("shading_factor")
            if shading_factor is None:
                shading_factor = camera.shading_factor
            fill_color = _shade_color(
                base_color=ops.data.get("fill_color"),
                normal=normal,
                face_center=face_center,
                light_source=np.array(camera.light_source, dtype=float),
                shading_factor=float(shading_factor),
            )
            face_ops = OpsSet(initial_set=[])
            face_ops.extend(
                _build_path_ops(
                    points=flat_points,
                    close=True,
                    color=fill_color,
                    opacity=float(ops.data.get("fill_opacity", 0.0)),
                    width=0.0,
                    mode="fill",
                )
            )
            face_ops.extend(
                _build_path_ops(
                    points=flat_points,
                    close=True,
                    color=ops.data.get("stroke_color"),
                    opacity=float(ops.data.get("stroke_opacity", 1.0)),
                    width=float(ops.data.get("stroke_width", 1.0)),
                    mode="stroke",
                )
            )
            depth_value = float(np.mean(depths))
            face_ops.add_meta({"depth_3d": depth_value})
            depth_entries.append((depth_value, face_ops))

        for _depth, path_ops in sorted(depth_entries, key=lambda item: item[0]):
            projected_ops.extend(path_ops)
        return projected_ops

    def render(
        self,
        ctx: cairo.Context,
        initial_mode: str = "stroke",
        render_context: dict[str, Any] | None = None,
    ) -> None:
        """
        Renders the operation set on a Cairo graphics context.

        This method iterates through a series of drawing operations and applies them to the
        provided Cairo context. It supports various operation types including move, line,
        curve, and quadratic curve drawing, as well as path closing and pen/style configuration.

        Args:
            ctx (cairo.Context): The Cairo graphics context to render operations on.
            initial_mode (str, optional): The initial rendering mode, either "stroke" or "fill".
                Defaults to "stroke".

        Raises:
            NotImplementedError: If an unsupported operation type is encountered.
        """
        if render_context is None:
            render_context = {}

        if self.has_3d_ops() and render_context.get("camera_3d") is not None:
            projected_ops = self.project_3d(render_context["camera_3d"])
            projected_ops.render(ctx, initial_mode=initial_mode, render_context=render_context)
            return

        mode = initial_mode
        has_path = False  # initially there is no path

        def flush_pending_path() -> None:
            nonlocal has_path
            if has_path and mode == "stroke":
                ctx.stroke()
            elif has_path and mode == "fill":
                ctx.fill()
            has_path = False

        for ops in self.opsset:
            if ops.type == OpsType.MOVE_TO:
                ctx.move_to(*ops.data[0])
            elif ops.type == OpsType.LINE_TO:
                has_path = True
                if ops.partial < 1.0:
                    x0, y0 = ctx.get_current_point()
                    x1, y1 = ops.data[0]
                    x = x0 + ops.partial * (x1 - x0)  # calculate vectors
                    y = y0 + ops.partial * (y1 - y0)
                    ctx.line_to(x, y)
                else:
                    ctx.line_to(*ops.data[0])
            elif ops.type == OpsType.CURVE_TO:
                has_path = True
                if ops.partial < 1.0:
                    p0 = ctx.get_current_point()
                    p1, p2, p3 = ops.data[0], ops.data[1], ops.data[2]
                    cp1, cp2, ep = slice_bezier(p0, p1, p2, p3, ops.partial)
                    ctx.curve_to(cp1[0], cp1[1], cp2[0], cp2[1], ep[0], ep[1])
                else:
                    ctx.curve_to(
                        ops.data[0][0],
                        ops.data[0][1],
                        ops.data[1][0],
                        ops.data[1][1],
                        ops.data[2][0],
                        ops.data[2][1],
                    )
            elif ops.type == OpsType.QUAD_CURVE_TO:
                has_path = True
                q1, q2 = ops.data[0], ops.data[1]
                p0 = ctx.get_current_point()
                p1, p2, p3 = get_bezier_points_from_quadcurve(p0, q1, q2)
                if ops.partial < 1.0:
                    cp1, cp2, ep = slice_bezier(p0, p1, p2, p3, ops.partial)
                    ctx.curve_to(cp1[0], cp1[1], cp2[0], cp2[1], ep[0], ep[1])
                else:
                    ctx.curve_to(p1[0], p1[1], p2[0], p2[1], p3[0], p3[1])
            elif ops.type == OpsType.CLOSE_PATH:
                has_path = True
                ctx.close_path()
            elif ops.type == OpsType.SET_PEN:
                flush_pending_path()  # handle last stroke / fill performed
                mode = ops.data.get("mode", "stroke")  # update the mode based on current ops
                if ops.data.get("color"):
                    r, g, b = ops.data.get("color")
                    ctx.set_source_rgba(r, g, b, ops.data.get("opacity", 1))
                if ops.data.get("width"):
                    ctx.set_line_width(ops.data.get("width"))
                ctx.set_line_cap(cairo.LineCap.ROUND)
                ctx.set_line_join(cairo.LineJoin.ROUND)
            elif ops.type == OpsType.METADATA:
                pass  # ignore metadata ops
            elif ops.type == OpsType.DOT:
                has_path = True
                x, y = ops.data.get("center", (0, 0))
                ctx.move_to(x, y)
                ctx.arc(x, y, ops.data.get("radius", 1), 0, 2 * np.pi)
            elif ops.type == OpsType.IMAGE:
                flush_pending_path()
                image_path = ops.data.get("path")
                image_points = ops.data.get("points", [])
                image_opacity = float(ops.data.get("opacity", 1.0))
                if image_path is None:
                    continue
                image_surface = _get_image_surface(str(image_path))
                _draw_surface_on_points(ctx, image_surface, image_points, image_opacity)
            elif ops.type == OpsType.VIDEO:
                flush_pending_path()
                video_path = ops.data.get("path")
                video_points = ops.data.get("points", [])
                video_opacity = float(ops.data.get("opacity", 1.0))
                if video_path is None:
                    continue

                video_meta = _get_video_meta(str(video_path))
                video_frame_index = _resolve_video_frame_index(
                    ops.data,
                    render_context,
                    video_meta,
                )
                if video_frame_index is None:
                    continue

                video_surface = _get_video_frame_surface(str(video_path), video_frame_index)
                _draw_surface_on_points(ctx, video_surface, video_points, video_opacity)
            else:
                msg = f"Unknown operation type {ops.type}"
                raise NotImplementedError(msg)

        # at the end of everything, check if stroke or fill is needed to complete the drawing
        if has_path and mode == "stroke":
            ctx.stroke()
        elif has_path and mode == "fill":
            ctx.fill()

    def quick_view(
        self,
        width: int = 800,
        height: int = 600,
        background_color: tuple[float, float, float] = (1, 1, 1),
        block: bool = True,
    ) -> None:
        """
        Renders the OpsSet to a temporary SVG file and opens it in a web browser for quick viewing.

        This is a utility for debugging. It automatically creates a viewport that fits the content.

        Args:
            width (int): The width of the output SVG image.
            height (int): The height of the output SVG image.
            background_color (Tuple[float, float, float]): The RGB background color. Defaults to white.
            block (bool): If True, the script will pause execution until Enter is pressed in the console.
        """
        if not self.opsset:
            return

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".svg", delete=False, encoding="utf-8"
        ) as tmp_file:
            tmp_filename = tmp_file.name

        # Get bounding box to create a viewport that fits the content
        viewport = Viewport(
            world_xrange=(0, 1000 * (width / height)),
            world_yrange=(0, 1000),
            screen_width=width,
            screen_height=height,
            margin=20,
        )

        with cairo.SVGSurface(tmp_filename, width, height) as surface:
            ctx = cairo.Context(surface)
            ctx.set_source_rgb(*background_color)
            ctx.paint()
            viewport.apply_to_context(ctx)
            self.render(ctx)
            surface.finish()

        webbrowser.open_new_tab(f"file://{tmp_filename}")

        if block:
            input()
