from pathlib import Path

import imageio.v2 as imageio
import numpy as np

from handanim.core.draw_ops import Ops, OpsSet, OpsType
from handanim.core.drawable import Drawable


def _resolve_media_path(path: str) -> str:
    resolved = Path(path).expanduser().resolve()
    if not resolved.exists():
        msg = f"Media file does not exist: {path}"
        raise FileNotFoundError(msg)
    return str(resolved)


def _resolve_target_size(
    intrinsic_width: float,
    intrinsic_height: float,
    width: float | None,
    height: float | None,
    preserve_aspect_ratio: bool,
) -> tuple[float, float]:
    resolved_width = width
    resolved_height = height

    if resolved_width is None and resolved_height is None:
        resolved_width = intrinsic_width
        resolved_height = intrinsic_height
    elif resolved_width is None:
        if preserve_aspect_ratio:
            resolved_width = float(resolved_height) * intrinsic_width / intrinsic_height
        else:
            resolved_width = intrinsic_width
    elif resolved_height is None:
        if preserve_aspect_ratio:
            resolved_height = float(resolved_width) * intrinsic_height / intrinsic_width
        else:
            resolved_height = intrinsic_height

    if resolved_width is None or resolved_height is None:
        msg = "Could not resolve media width/height"
        raise ValueError(msg)
    if resolved_width <= 0 or resolved_height <= 0:
        msg = "Media width and height must be > 0"
        raise ValueError(msg)

    return float(resolved_width), float(resolved_height)


def _extract_frame_size(frame: np.ndarray) -> tuple[int, int]:
    data = np.asarray(frame)
    if data.ndim == 4:
        data = data[0]
    if data.ndim < 2:
        msg = f"Unsupported media frame shape: {data.shape}"
        raise ValueError(msg)
    height, width = data.shape[:2]
    return int(width), int(height)


def _build_media_points(top_left: tuple[float, float], width: float, height: float):
    x, y = float(top_left[0]), float(top_left[1])
    return [
        (x, y),
        (x + width, y),
        (x, y + height),
    ]


class Image(Drawable):
    """
    Draw a raster image into a scene.

    Args:
        path (str): Path to an image file.
        top_left (tuple[float, float]): Top-left anchor point in world coordinates.
        width (float | None): Target width. If omitted, image intrinsic width is used.
        height (float | None): Target height. If omitted, image intrinsic height is used.
        preserve_aspect_ratio (bool): Keep intrinsic aspect ratio when only one dimension is provided.
        opacity (float): Opacity in range [0, 1].
    """

    def __init__(
        self,
        path: str,
        top_left: tuple[float, float] = (0.0, 0.0),
        width: float | None = None,
        height: float | None = None,
        preserve_aspect_ratio: bool = True,
        opacity: float = 1.0,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.path = _resolve_media_path(path)
        self.top_left = (float(top_left[0]), float(top_left[1]))

        image_frame = imageio.imread(self.path)
        intrinsic_width, intrinsic_height = _extract_frame_size(image_frame)
        self.intrinsic_size = (intrinsic_width, intrinsic_height)
        self.width, self.height = _resolve_target_size(
            intrinsic_width=float(intrinsic_width),
            intrinsic_height=float(intrinsic_height),
            width=width,
            height=height,
            preserve_aspect_ratio=preserve_aspect_ratio,
        )

        self.opacity = float(opacity)
        if not 0.0 <= self.opacity <= 1.0:
            msg = "Image opacity must be between 0 and 1"
            raise ValueError(msg)

    @classmethod
    def from_file(cls, image_path: str, **kwargs):
        return cls(path=image_path, **kwargs)

    def draw(self) -> OpsSet:
        opsset = OpsSet(initial_set=[])
        opsset.add(
            Ops(
                OpsType.IMAGE,
                {
                    "path": self.path,
                    "points": _build_media_points(self.top_left, self.width, self.height),
                    "opacity": self.opacity,
                },
            )
        )
        return opsset


class Video(Drawable):
    """
    Draw a video stream into a scene.

    Args:
        path (str): Path to a video file.
        top_left (tuple[float, float]): Top-left anchor point in world coordinates.
        width (float | None): Target width. If omitted, video intrinsic width is used.
        height (float | None): Target height. If omitted, video intrinsic height is used.
        preserve_aspect_ratio (bool): Keep intrinsic aspect ratio when only one dimension is provided.
        opacity (float): Opacity in range [0, 1].
        scene_start (float): Scene timestamp (seconds) where playback starts.
        source_start (float): Source video timestamp (seconds) to start from.
        playback_rate (float): Playback speed multiplier.
        loop (bool): Whether to loop playback after the last frame.
        source_fps (float | None): Optional FPS override for deterministic playback timing.
    """

    def __init__(
        self,
        path: str,
        top_left: tuple[float, float] = (0.0, 0.0),
        width: float | None = None,
        height: float | None = None,
        preserve_aspect_ratio: bool = True,
        opacity: float = 1.0,
        scene_start: float = 0.0,
        source_start: float = 0.0,
        playback_rate: float = 1.0,
        loop: bool = True,
        source_fps: float | None = None,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.path = _resolve_media_path(path)
        self.top_left = (float(top_left[0]), float(top_left[1]))

        reader = imageio.get_reader(self.path)
        try:
            video_meta = reader.get_meta_data() or {}
            size = video_meta.get("size")
            if isinstance(size, (tuple, list)) and len(size) >= 2:
                intrinsic_width = int(size[0])
                intrinsic_height = int(size[1])
            else:
                first_frame = reader.get_data(0)
                intrinsic_width, intrinsic_height = _extract_frame_size(first_frame)

            native_fps_raw = video_meta.get("fps")
            try:
                native_fps = float(native_fps_raw) if native_fps_raw is not None else None
            except (TypeError, ValueError):
                native_fps = None
        finally:
            reader.close()

        self.intrinsic_size = (intrinsic_width, intrinsic_height)
        self.native_fps = native_fps
        self.width, self.height = _resolve_target_size(
            intrinsic_width=float(intrinsic_width),
            intrinsic_height=float(intrinsic_height),
            width=width,
            height=height,
            preserve_aspect_ratio=preserve_aspect_ratio,
        )

        self.opacity = float(opacity)
        if not 0.0 <= self.opacity <= 1.0:
            msg = "Video opacity must be between 0 and 1"
            raise ValueError(msg)

        self.scene_start = float(scene_start)
        self.source_start = float(source_start)
        self.playback_rate = float(playback_rate)
        self.loop = bool(loop)
        self.source_fps = float(source_fps) if source_fps is not None else None

        if self.scene_start < 0:
            msg = "scene_start must be >= 0"
            raise ValueError(msg)
        if self.source_start < 0:
            msg = "source_start must be >= 0"
            raise ValueError(msg)
        if self.playback_rate <= 0:
            msg = "playback_rate must be > 0"
            raise ValueError(msg)
        if self.source_fps is not None and self.source_fps <= 0:
            msg = "source_fps must be > 0 when provided"
            raise ValueError(msg)

    @classmethod
    def from_file(cls, video_path: str, **kwargs):
        return cls(path=video_path, **kwargs)

    def draw(self) -> OpsSet:
        opsset = OpsSet(initial_set=[])
        opsset.add(
            Ops(
                OpsType.VIDEO,
                {
                    "path": self.path,
                    "points": _build_media_points(self.top_left, self.width, self.height),
                    "opacity": self.opacity,
                    "scene_start": self.scene_start,
                    "source_start": self.source_start,
                    "playback_rate": self.playback_rate,
                    "loop": self.loop,
                    "source_fps": self.source_fps,
                },
            )
        )
        return opsset
