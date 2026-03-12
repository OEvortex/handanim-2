import json

import numpy as np
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


def _matplotlib_path_to_opsset(path: MatplotlibPath) -> OpsSet:
    opsset = OpsSet(initial_set=[])
    vertices = path.vertices
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

    def _position_opsset(self, opsset: OpsSet, anchor_position: tuple[float, float]) -> None:
        min_x, min_y, max_x, max_y = opsset.get_bbox()
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

    def _fit_to_rect_box(self, opsset: OpsSet, anchor_position: tuple[float, float]) -> None:
        if self.rect_box is None:
            return

        _x, _y, box_width, box_height = self.rect_box
        available_width = max(box_width - 2 * self.rect_padding, 1e-6)
        available_height = max(box_height - 2 * self.rect_padding, 1e-6)

        min_x, min_y, max_x, max_y = opsset.get_bbox()
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
        expression = _normalize_mathtex_expression(self.tex_expression)
        try:
            return TextPath(
                xy=(0.0, 0.0),
                s=expression,
                size=self.font_size,
                prop=_font_properties_from_name(self.font_name),
                usetex=self.usetex,
            )
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
        self._position_opsset(opsset, target_anchor)
        self._fit_to_rect_box(opsset, target_anchor)

        if self.stroke_style.stroke_pressure != StrokePressure.CONSTANT:
            opsset = apply_stroke_pressure(opsset, self.stroke_style.stroke_pressure)
        return opsset


class Math(Drawable):
    """
    A Drawable class for rendering mathematical expressions using TeX notation.

    This class parses a TeX expression and renders individual glyphs using a specified font,
    supporting custom positioning, scaling, and stroke styling.

    Attributes:
        tex_expression (str): The TeX mathematical expression to render
        position (Tuple[float, float]): The starting position for rendering the expression
        font_size (int, optional): The size of the font, defaults to 12
        font_name (str): The name of the font to use for rendering, defaults to "feasibly"

    Methods:
        get_glyph_opsset: Extracts the operations set for a single unicode glyph
        draw: Renders the entire mathematical expression as a set of drawing operations
    """

    def __init__(
        self,
        tex_expression: str,
        position: tuple[float, float],
        font_size: int = 12,
        font_name: str = "handanimtype1",
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.tex_expression = tex_expression
        self.position = position
        self.scale_factor = font_size / 10  # base size is 10
        self.parser = MathTextParser("path")
        self.font_name = font_name
        self.font_details = {}
        self.load_font()

    def load_font(self) -> None:
        font_path = get_font_path(self.font_name)
        if font_path.endswith(".json"):
            # this is custom-made svg font
            with open(font_path) as f:
                self.font_details = json.load(f)
                self.font_details["type"] = "custom"
        else:
            font = TTFont(font_path)
            glyph_set = font.getGlyphSet()
            cmap = font.getBestCmap()
            units_per_em = font["head"].unitsPerEm  # usually 1000
            self.font_details = {
                "type": "standard",
                "glyph_set": glyph_set,
                "cmap": cmap,
                "units_per_em": units_per_em,
            }

    def standard_glyph_opsset(
        self, unicode: int, font_size: int
    ) -> tuple[OpsSet, float, float]:
        glyph_set = self.font_details.get("glyph_set")
        cmap = self.font_details.get("cmap")
        units_per_em_raw = self.font_details.get("units_per_em")
        if glyph_set is None or cmap is None or units_per_em_raw is None:
            return OpsSet(initial_set=[]), 1.0, 1.0

        units_per_em = int(units_per_em_raw)
        glyph_name = cmap.get(unicode)
        if glyph_name is None:
            return OpsSet(initial_set=[]), 1.0, 1.0

        scale = font_size / units_per_em  # normalize to desired size
        glyph = glyph_set[glyph_name]
        pen = CustomPen(glyph_set, scale=scale)
        glyph.draw(pen)

        # now get the bounding box
        dx, dy = pen.min_x, pen.min_y
        pen.opsset.translate(-dx, -dy)  # so top-left is (0, 0)

        width = glyph.width * scale
        height = pen.max_y - pen.min_y
        return pen.opsset, height, width

    def custom_glyph_opsset(
        self, unicode: int, font_size: int
    ) -> tuple[OpsSet, float, float]:
        glyphs = self.font_details.get("glyphs")
        metadata = self.font_details.get("metadata")
        assert glyphs is not None
        assert metadata is not None

        if str(unicode) not in glyphs:
            return OpsSet(initial_set=[]), 1.0, 1.0
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
        svg_ops.translate(-min_x, -min_y)  # top-left corner must be at (0, 0)
        return svg_ops, height, width

    def get_glyph_opsset(
        self, unicode: int, font_size: int
    ) -> tuple[OpsSet, float, float]:
        """
        Returns the opset for a single glyph of a unicode number
        """
        if self.font_details["type"] == "custom":
            # this is custom-made svg font
            return self.custom_glyph_opsset(unicode, font_size)
        return self.standard_glyph_opsset(unicode, font_size)

    def draw(self) -> OpsSet:
        opsset = OpsSet(initial_set=[])
        opsset.add(_set_pen_op(self.stroke_style))

        # parse and extract the glyphs from matplotlib parsing
        parse_out = self.parser.parse(self.tex_expression)
        glyphs = (
            parse_out.glyphs
        )  # list of tuple of (font, font_size, char, offset_x, offset_y)
        boxes = parse_out.rects  # list of tuple of (x, y, width, height)

        for glyph in glyphs:
            # offset_x = postion of the glyph relative to start at 0.0
            # offset_y = position of the glyph relative to the baseline
            _font, font_size, unicode, offset_x, offset_y = glyph
            glyph_opsset, glyph_height, _glyph_width = self.get_glyph_opsset(
                unicode,
                font_size=font_size
                * self.scale_factor,  # scale the font size appropriately
            )
            draw_x = offset_x * self.scale_factor + self.position[0]
            draw_y = (
                self.position[1]
                + (10 * self.scale_factor - glyph_height)
                - offset_y * self.scale_factor
            )  # this ensures the lower edge matches the baseline
            glyph_opsset.translate(draw_x, draw_y)

            # draw glyph
            opsset.add(_set_pen_op(self.stroke_style))
            opsset.extend(glyph_opsset)  # continue adding to the opset for each glyph

        # finally draw the lines
        current_stroke_width = self.stroke_style.width
        for box in boxes:
            x, y, width, height = box  # we will approximate by a thick line
            self.stroke_style.width = height / 2 * self.scale_factor
            draw_x, draw_y = (
                self.position[0] + self.scale_factor * x,
                self.position[1] + (10 - height / 2 - y) * self.scale_factor,
            )

            line = Line(
                start=(draw_x, draw_y),
                end=(draw_x + self.scale_factor * width, draw_y),
                stroke_style=self.stroke_style,
            )
            opsset.extend(line.draw())
        self.stroke_style.width = current_stroke_width

        # for the character strokes, apply pen pressures
        if self.stroke_style.stroke_pressure != StrokePressure.CONSTANT:
            opsset = apply_stroke_pressure(opsset, self.stroke_style.stroke_pressure)

        return opsset
