import cairo
import numpy as np

from handanim.animations import SketchAnimation
from handanim.core import Scene, SketchStyle, StrokeStyle
from handanim.core.draw_ops import OpsType
from handanim.core.utils import cairo_surface_to_numpy
from handanim.primitives import Eraser, Rectangle, Text


def _rgb_at(frame: np.ndarray, x: int, y: int) -> tuple[int, int, int]:
    pixel = frame[y, x]
    return int(pixel[0]), int(pixel[1]), int(pixel[2])


def test_eraser_covers_each_drawable_with_solid_background_fill():
    scene = Scene(width=500, height=320, background_color=(0.2, 0.4, 0.6))
    sketch = SketchStyle(roughness=0, bowing=0, disable_multi_stroke=True, disable_font_mixture=True)

    title = Text(
        text="Erase me",
        position=(140, 100),
        font_size=48,
        stroke_style=StrokeStyle(color=(0.0, 0.0, 0.0), width=3),
        sketch_style=sketch,
    )
    panel = Rectangle(
        top_left=(260, 60),
        width=110,
        height=90,
        stroke_style=StrokeStyle(color=(0.0, 0.0, 0.0), width=3),
        sketch_style=sketch,
    )

    scene.add(SketchAnimation(duration=1.0), drawable=title)
    scene.add(SketchAnimation(duration=1.0), drawable=panel)

    eraser = Eraser(
        objects_to_erase=[title, panel],
        drawable_cache=scene.drawable_cache,
        erase_color=scene.background_color,
        sketch_style=sketch,
    )
    opsset = eraser.draw()

    set_pen_ops = [ops for ops in opsset.opsset if ops.type == OpsType.SET_PEN]
    assert len(set_pen_ops) == 2
    assert all(ops.data["mode"] == "fill" for ops in set_pen_ops)
    assert all(ops.data["color"] == scene.background_color for ops in set_pen_ops)

    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, scene.width, scene.height)
    ctx = cairo.Context(surface)
    ctx.set_source_rgb(1.0, 0.0, 1.0)
    ctx.paint()
    opsset.render(ctx)
    frame = cairo_surface_to_numpy(surface)

    title_bbox = scene.drawable_cache.get_drawable_opsset(title.id).get_bbox()
    panel_bbox = scene.drawable_cache.get_drawable_opsset(panel.id).get_bbox()
    title_center = (int(round((title_bbox[0] + title_bbox[2]) / 2)), int(round((title_bbox[1] + title_bbox[3]) / 2)))
    panel_center = (int(round((panel_bbox[0] + panel_bbox[2]) / 2)), int(round((panel_bbox[1] + panel_bbox[3]) / 2)))

    expected = tuple(int(round(channel * 255)) for channel in scene.background_color)
    assert _rgb_at(frame, *title_center) == expected
    assert _rgb_at(frame, *panel_center) == expected
    assert _rgb_at(frame, 20, 20) == (255, 0, 255)
