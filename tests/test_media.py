from pathlib import Path

import cairo
import imageio.v2 as imageio
import numpy as np

from handanim.core.draw_ops import OpsSet, OpsType
from handanim.core.utils import cairo_surface_to_numpy
from handanim.primitives import Image, Video


def _write_test_png(path: Path) -> None:
    frame = np.zeros((8, 12, 3), dtype=np.uint8)
    frame[:, :] = [220, 30, 30]
    imageio.imwrite(path, frame)


def _write_test_gif(path: Path) -> None:
    red = np.zeros((8, 8, 3), dtype=np.uint8)
    red[:, :] = [255, 0, 0]

    green = np.zeros((8, 8, 3), dtype=np.uint8)
    green[:, :] = [0, 255, 0]

    imageio.mimsave(path, [red, green], format="GIF", duration=[0.5, 0.5])  # ty:ignore[no-matching-overload]


def _render_opsset(
    opsset: OpsSet,
    scene_time: float,
    width: int = 32,
    height: int = 32,
) -> np.ndarray:
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
    ctx = cairo.Context(surface)
    ctx.set_source_rgb(1, 1, 1)
    ctx.paint()
    opsset.render(
        ctx,
        render_context={
            "scene_time": scene_time,
            "frame_index": int(scene_time * 24),
            "fps": 24,
        },
    )
    return cairo_surface_to_numpy(surface)


def test_image_draw_generates_media_op(tmp_path):
    image_path = tmp_path / "sample.png"
    _write_test_png(image_path)

    image = Image(path=str(image_path), top_left=(3, 4))
    opsset = image.draw()

    assert len(opsset.opsset) == 1
    image_op = opsset.opsset[0]
    assert image_op.type is OpsType.IMAGE

    p0, p1, p2 = image_op.data["points"]
    assert p0 == (3.0, 4.0)
    assert np.isclose(p1[0] - p0[0], 12.0)
    assert np.isclose(p2[1] - p0[1], 8.0)


def test_video_draw_generates_video_op(tmp_path):
    video_path = tmp_path / "sample.gif"
    _write_test_gif(video_path)

    video = Video(path=str(video_path), top_left=(1, 2), width=16, source_fps=1.0)
    opsset = video.draw()

    assert len(opsset.opsset) == 1
    video_op = opsset.opsset[0]
    assert video_op.type is OpsType.VIDEO
    assert np.isclose(video.width, 16.0)
    assert np.isclose(video.height, 16.0)
    assert np.isclose(video_op.data["source_fps"], 1.0)


def test_image_render_paints_pixels(tmp_path):
    image_path = tmp_path / "sample.png"
    _write_test_png(image_path)

    image = Image(path=str(image_path), top_left=(4, 4), width=12, height=10)
    rendered = _render_opsset(image.draw(), scene_time=0.0)

    painted_pixel = rendered[8, 8, :3]
    assert painted_pixel[0] > 150
    assert painted_pixel[1] < 80
    assert painted_pixel[2] < 80


def test_video_render_changes_frame_over_time(tmp_path):
    video_path = tmp_path / "sample.gif"
    _write_test_gif(video_path)

    video = Video(
        path=str(video_path),
        top_left=(2, 2),
        width=12,
        height=12,
        loop=False,
        source_fps=1.0,
    )
    opsset = video.draw()

    first_frame = _render_opsset(opsset, scene_time=0.0)
    second_frame = _render_opsset(opsset, scene_time=1.0)

    first_pixel = first_frame[6, 6, :3]
    second_pixel = second_frame[6, 6, :3]

    assert first_pixel[0] > first_pixel[1]
    assert second_pixel[1] > second_pixel[0]
