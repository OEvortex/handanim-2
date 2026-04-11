import json
from functools import lru_cache

import numpy as np
import matplotlib as mpl
from fontTools.ttLib import TTFont
from matplotlib.font_manager import FontProperties
from matplotlib.mathtext import MathTextParser
from matplotlib.path import Path as MatplotlibPath
from matplotlib.textpath import TextPath

from handanim.core.draw_ops import Ops, OpsSet, OpsType
from handanim.core.drawable import Drawable
from handanim.core.styles import StrokePressure
from handanim.stylings.fonts import get_font_path
from handanim.stylings.strokes import apply_stroke_pressure

from .lines import Line
from .svg import SVG
from .text import CustomPen


def _set_pen_op(stroke_style) -> Ops:
    return Ops(
        OpsType.SET_PEN,
        {
            "color": stroke_style.color,
            "opacity": stroke_style.opacity,
            "width": stroke_style.width,
        },
    )


def _normalize_mathtex_expression(tex_expression: str) -> str:
    stripped = tex_expression.strip()
    if "$" in stripped:
        return stripped
    return f"${stripped}$"


def _font_properties_from_name(font_name: str | None) -> FontProperties | None:
    if font_name is None:
        return None

    font_path = get_font_path(font_name)
    if font_path.endswith(".json"):
        return None
    return FontProperties(fname=font_path)


@lru_cache(maxsize=1024)
def _cached_mathtex_path(
    tex_expression: str,
    font_name: str | None,
    font_size: int,
    usetex: bool,
) -> TextPath:
    import matplotlib as mpl
    
    expression = _normalize_mathtex_expression(tex_expression)
    
    # Configure a LaTeX preamble with the packages we rely on when using usetex.
    # amsmath provides \text, and amssymb provides \mathbb.
    if usetex:
        original_preamble = mpl.rcParams['text.latex.preamble']
        mpl.rcParams['text.latex.preamble'] = r'\usepackage{amsmath,amssymb}'
    
    try:
        return TextPath(
            xy=(0.0, 0.0),
            s=expression,
            size=font_size,
            prop=_font_properties_from_name(font_name),
            usetex=usetex,
        )
    finally:
        if usetex:
            mpl.rcParams['text.latex.preamble'] = original_preamble


@lru_cache(maxsize=4096)
def _cached_standard_math_glyph_ops(
    font_path: str,
    unicode: int,
    font_size: float,
) -> tuple[tuple[Ops, ...], float, float]:
    font = TTFont(font_path)
    glyph_set = font.getGlyphSet()
    cmap = font.getBestCmap()
    if cmap is None:
        return (), 1.0, 1.0

    units_per_em = int(font["head"].unitsPerEm)
    glyph_name = cmap.get(unicode)
    if glyph_name is None:
        return (), 1.0, 1.0

    scale = font_size / units_per_em
    glyph = glyph_set[glyph_name]
    pen = CustomPen(glyph_set, scale=scale)
    glyph.draw(pen)

    dx, dy = pen.min_x, pen.min_y
    pen.opsset.translate(-dx, -dy)

    width = glyph.width * scale
    height = pen.max_y - pen.min_y
    return tuple(pen.opsset.opsset), height, width


@lru_cache(maxsize=4096)
def _cached_custom_math_glyph_ops(
    font_path: str,
    unicode: int,
    font_size: float,
) -> tuple[tuple[Ops, ...], float, float]:
    with open(font_path) as f:
        font_details = json.load(f)

    glyphs = font_details.get("glyphs")
    metadata = font_details.get("metadata")
    if not isinstance(glyphs, dict) or not isinstance(metadata, dict):
        return (), 1.0, 1.0

    if str(unicode) not in glyphs:
        return (), 1.0, 1.0

    glyph_svg_paths = glyphs[str(unicode)]
    svg = SVG(svg_paths=glyph_svg_paths)
    svg_ops = svg.draw()
    font_units_raw = metadata.get("font_size")
    font_units = float(font_units_raw) if font_units_raw is not None else 1.0
    font_scale = font_size / font_units
    svg_ops.scale(font_scale)

    min_x, min_y, max_x, max_y = svg.get_bbox()
    width = (max_x - min_x) * font_scale
    height = (max_y - min_y) * font_scale
    svg_ops.translate(-min_x, -min_y)
    return tuple(svg_ops.opsset), height, width


def _matplotlib_path_to_opsset(path: MatplotlibPath) -> OpsSet:
    opsset = OpsSet(initial_set=[])
    vertices = path.vertices.tolist()
    codes = path.codes

    if codes is None:
        if len(vertices) == 0:
            return opsset
        opsset.add(Ops(OpsType.MOVE_TO, [(float(vertices[0][0]), float(vertices[0][1]))]))
        for vertex in vertices[1:]:
            opsset.add(Ops(OpsType.LINE_TO, [(float(vertex[0]), float(vertex[1]))]))
        return opsset

    index = 0
    while index < len(vertices):
        code = int(codes[index])
        vertex = vertices[index]
        point = (float(vertex[0]), float(vertex[1]))

        if code == MatplotlibPath.MOVETO:
            opsset.add(Ops(OpsType.MOVE_TO, [point]))
            index += 1
        elif code == MatplotlibPath.LINETO:
            opsset.add(Ops(OpsType.LINE_TO, [point]))
            index += 1
        elif code == MatplotlibPath.CURVE3:
            if index + 1 >= len(vertices):
                msg = "Malformed matplotlib path: CURVE3 is missing its endpoint."
                raise ValueError(msg)
            control = point
            end_vertex = vertices[index + 1]
            end = (float(end_vertex[0]), float(end_vertex[1]))
            opsset.add(Ops(OpsType.QUAD_CURVE_TO, [control, end]))
            index += 2
        elif code == MatplotlibPath.CURVE4:
            if index + 2 >= len(vertices):
                msg = "Malformed matplotlib path: CURVE4 is missing control points or endpoint."
                raise ValueError(msg)
            control1 = point
            control2_vertex = vertices[index + 1]
            end_vertex = vertices[index + 2]
            control2 = (float(control2_vertex[0]), float(control2_vertex[1]))
            end = (float(end_vertex[0]), float(end_vertex[1]))
            opsset.add(Ops(OpsType.CURVE_TO, [control1, control2, end]))
            index += 3
        elif code == MatplotlibPath.CLOSEPOLY:
            opsset.add(Ops(OpsType.CLOSE_PATH, {}))
            index += 1
        else:
            msg = f"Unsupported matplotlib path code: {code}"
            raise ValueError(msg)

    return opsset


class MathTex(Drawable):
    """
    Render LaTeX-style math expressions as vector paths.

    By default this uses Matplotlib's mathtext engine, which supports a TeX-like subset
    without needing a local LaTeX installation. Set ``usetex=True`` to request external
    LaTeX rendering when a TeX toolchain is available.
    """

    def __init__(
        self,
        *tex_strings: str,
        position: tuple[float, float],
        font_size: int = 12,
        font_name: str | None = None,
        usetex: bool = False,
        **kwargs,
    ) -> None:
        tex_expression = kwargs.pop("tex_expression", None)
        rect_box = kwargs.pop("rect_box", None)
        rect_padding = float(kwargs.pop("rect_padding", 0.0))
        align = kwargs.pop("align", "center")
        
        # Handle color parameter - convert to stroke_style if provided
        color = kwargs.pop("color", None)
        if color is not None and "stroke_style" not in kwargs:
            from handanim.core.styles import StrokeStyle
            kwargs["stroke_style"] = StrokeStyle(color=color)
        
        super().__init__(**kwargs)

        if tex_strings and tex_expression is not None:
            msg = "Pass either positional TeX strings or tex_expression, not both."
            raise ValueError(msg)

        if tex_expression is None:
            if not tex_strings:
                msg = "MathTex requires at least one TeX string."
                raise ValueError(msg)
            tex_expression = "".join(tex_strings)

        self.tex_expression = tex_expression
        self.position = position
        self.font_size = int(font_size)
        self.font_name = font_name
        self.usetex = bool(usetex)
        self.rect_box: tuple[float, float, float, float] | None = rect_box
        self.rect_padding = rect_padding
        self.align = align

        if self.font_size <= 0:
            msg = "font_size must be positive"
            raise ValueError(msg)
        if self.rect_box is not None:
            if len(self.rect_box) != 4:
                msg = "rect_box must be a tuple of (x, y, width, height)"
                raise ValueError(msg)
            if self.rect_box[2] <= 0 or self.rect_box[3] <= 0:
                msg = "rect_box width and height must be positive"
                raise ValueError(msg)
        if self.rect_padding < 0:
            msg = "rect_padding must be non-negative"
            raise ValueError(msg)
        if self.align not in {"left", "center", "right"}:
            msg = "align must be one of: left, center, right"
            raise ValueError(msg)

    def _get_target_anchor(self) -> tuple[float, float]:
        if self.rect_box is None:
            return self.position
        box_x, box_y, box_width, box_height = self.rect_box
        if self.align == "left":
            anchor_x = box_x + self.rect_padding
        elif self.align == "right":
            anchor_x = box_x + box_width - self.rect_padding
        else:
            anchor_x = box_x + box_width / 2
        return (anchor_x, box_y + box_height / 2)

    def _position_opsset(
        self,
        opsset: OpsSet,
        anchor_position: tuple[float, float],
        bbox: tuple[float, float, float, float] | None = None,
    ) -> None:
        if bbox is None:
            bbox = opsset.get_bbox()
        min_x, min_y, max_x, max_y = bbox
        if not np.isfinite([min_x, min_y, max_x, max_y]).all():
            return

        center_y = (min_y + max_y) / 2
        if self.align == "left":
            anchor_x = min_x
        elif self.align == "right":
            anchor_x = max_x
        else:
            anchor_x = (min_x + max_x) / 2

        opsset.translate(anchor_position[0] - anchor_x, anchor_position[1] - center_y)

    def _fit_to_rect_box(
        self,
        opsset: OpsSet,
        anchor_position: tuple[float, float],
        bbox: tuple[float, float, float, float] | None = None,
    ) -> None:
        if self.rect_box is None:
            return

        _x, _y, box_width, box_height = self.rect_box
        available_width = max(box_width - 2 * self.rect_padding, 1e-6)
        available_height = max(box_height - 2 * self.rect_padding, 1e-6)

        if bbox is None:
            bbox = opsset.get_bbox()
        min_x, min_y, max_x, max_y = bbox
        if not np.isfinite([min_x, min_y, max_x, max_y]).all():
            return

        tex_width = max_x - min_x
        tex_height = max_y - min_y
        if tex_width <= 0 or tex_height <= 0:
            return

        fit_scale = min(available_width / tex_width, available_height / tex_height)
        if fit_scale < 1:
            opsset.scale(fit_scale)
            self._position_opsset(opsset, anchor_position)

    def _build_text_path(self) -> TextPath:
        try:
            return _cached_mathtex_path(self.tex_expression, self.font_name, self.font_size, self.usetex)
        except Exception as exc:
            if self.usetex:
                msg = (
                    "MathTex with usetex=True requires a working LaTeX toolchain "
                    "available to Matplotlib."
                )
                raise RuntimeError(msg) from exc
            raise

    def draw(self) -> OpsSet:
        opsset = OpsSet(initial_set=[_set_pen_op(self.stroke_style)])
        text_path = self._build_text_path()
        path_opsset = _matplotlib_path_to_opsset(text_path)
        path_opsset.transform_points(lambda point: (point[0], -point[1]))
        opsset.extend(path_opsset)

        target_anchor = self._get_target_anchor()
        bbox = opsset.get_bbox()
        self._position_opsset(opsset, target_anchor, bbox=bbox)
        self._fit_to_rect_box(opsset, target_anchor, bbox=bbox)

        if self.stroke_style.stroke_pressure != StrokePressure.CONSTANT:
            opsset = apply_stroke_pressure(opsset, self.stroke_style.stroke_pressure)
        return opsset


# Alias for backward compatibility - Math is now MathTex
Math = MathTex
