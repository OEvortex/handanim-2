
import numpy as np
from fontTools.pens.basePen import BasePen
from fontTools.ttLib import TTFont

from handanim.core.draw_ops import Ops, OpsSet, OpsType
from handanim.core.drawable import Drawable
from handanim.stylings.fonts import get_font_path, list_fonts


class CustomPen(BasePen):
    # overwrite some methods to capture the strokes

    def __init__(self, glyphSet, scale: float = 0.01) -> None:
        super().__init__(glyphSet)
        self.opsset = OpsSet(initial_set=[])
        self.scale = scale
        self.min_x = self.min_y = float("inf")
        self.max_x = self.max_y = -float("inf")

    def _scale_point(self, pt):
        x, y = pt[0] * self.scale, -pt[1] * self.scale
        # update bounding box
        self.min_x = min(self.min_x, x)
        self.min_y = min(self.min_y, y)
        self.max_x = max(self.max_x, x)
        self.max_y = max(self.max_y, y)
        return (x, y)

    def _moveTo(self, pt) -> None:
        self.opsset.add(Ops(OpsType.MOVE_TO, data=[self._scale_point(pt)]))

    def _lineTo(self, pt) -> None:
        self.opsset.add(Ops(OpsType.LINE_TO, data=[self._scale_point(pt)]))

    def _curveToOne(self, pt1, pt2, pt3) -> None:
        self.opsset.add(
            Ops(
                OpsType.CURVE_TO,
                data=[
                    self._scale_point(pt1),
                    self._scale_point(pt2),
                    self._scale_point(pt3),
                ],
            )
        )

    def _closePath(self) -> None:
        self.opsset.add(Ops(OpsType.CLOSE_PATH, data={}))


class Text(Drawable):
    """
    A Drawable text primitive that renders text using font glyphs with customizable styling.

    Supports rendering text with random font selection, scaling, and sketch-style variations.
    Converts text characters into drawing operations (OpsSet) that can be rendered.

    Attributes:
        text (str): The text to be rendered
        position (Tuple[float, float]): Starting position for text rendering
        font_size (int, optional): Size of the rendered text. Defaults to 12.
        scale_factor (float, optional): Additional scaling factor. Defaults to 1.0.

    Methods:
        get_random_font_choice(): Selects a font for text rendering
        get_glyph_strokes(char): Converts a character into drawing operations
        get_glyph_space(): Calculates character and space widths
        draw(): Generates the complete set of drawing operations for the text
    """

    def __init__(
        self,
        text: str,
        position: tuple[float, float],
        font_size: int = 12,
        font_name: str | None = None,
        *args,
        **kwargs,
    ) -> None:
        scale_factor = kwargs.pop("scale_factor", 1.0)
        rect_box = kwargs.pop("rect_box", None)
        rect_padding = float(kwargs.pop("rect_padding", 0.0))
        align = kwargs.pop("align", "center")
        line_spacing = float(kwargs.pop("line_spacing", 1.25))
        super().__init__(*args, **kwargs)
        self.text = text
        self.position = position
        self.font_size = font_size
        self.font_name = font_name
        self.scale_factor = float(scale_factor)
        self.rect_box: tuple[float, float, float, float] | None = rect_box
        self.rect_padding = rect_padding
        self.align = align
        self.line_spacing = line_spacing

        if self.rect_box is not None:
            if len(self.rect_box) != 4:
                msg = "rect_box must be a tuple of (x, y, width, height)"
                raise ValueError(msg)
            _x, _y, box_width, box_height = self.rect_box
            if box_width <= 0 or box_height <= 0:
                msg = "rect_box width and height must be positive"
                raise ValueError(msg)
        if self.rect_padding < 0:
            msg = "rect_padding must be non-negative"
            raise ValueError(msg)
        if self.align not in {"left", "center", "right"}:
            msg = "align must be one of: left, center, right"
            raise ValueError(msg)
        if self.line_spacing <= 0:
            msg = "line_spacing must be positive"
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

        text_width = max_x - min_x
        text_height = max_y - min_y
        if text_width <= 0 or text_height <= 0:
            return

        fit_scale = min(available_width / text_width, available_height / text_height)
        if fit_scale < 1:
            opsset.scale(fit_scale)
            self._position_opsset(opsset, anchor_position)

    def _get_lines(self) -> list[str]:
        return self.text.split("\n") if self.text else [""]

    def _get_line_step(self) -> float:
        return self.font_size * self.scale_factor * self.line_spacing

    def _render_line(self, line_text: str, offset_y: float) -> OpsSet:
        line_opsset = OpsSet(initial_set=[])
        offset_x = 0.0
        cursor_y = offset_y
        space_width, glyph_scale = self.get_glyph_space()

        for char in line_text:
            if char == " ":
                offset_x += space_width
                continue
            glyph_opsset, glyph_width = self.get_glyph_strokes(char)
            glyph_opsset.translate(offset_x, cursor_y)
            line_opsset.extend(glyph_opsset)

            offset_x += glyph_width + glyph_scale * 5
            cursor_y += np.random.uniform(
                -self.sketch_style.roughness, self.sketch_style.roughness
            )
        return line_opsset

    def _align_lines(self, line_opssets: list[OpsSet]) -> None:
        non_empty_bboxes = [opsset.get_bbox() for opsset in line_opssets if len(opsset.opsset) > 0]
        if not non_empty_bboxes:
            return

        block_left = min(bbox[0] for bbox in non_empty_bboxes)
        block_right = max(bbox[2] for bbox in non_empty_bboxes)
        block_center = (block_left + block_right) / 2

        for line_opsset in line_opssets:
            if len(line_opsset.opsset) == 0:
                continue
            min_x, _min_y, max_x, _max_y = line_opsset.get_bbox()
            if self.align == "left":
                line_opsset.translate(block_left - min_x, 0)
            elif self.align == "right":
                line_opsset.translate(block_right - max_x, 0)
            else:
                line_center = (min_x + max_x) / 2
                line_opsset.translate(block_center - line_center, 0)

    def get_random_font_choice(self) -> tuple[str, str]:
        """
        Chooses a random font from the available fonts
        """
        if self.font_name is not None:
            return (self.font_name, get_font_path(self.font_name))

        font_list = list_fonts()
        if self.sketch_style.disable_font_mixture:
            font_choice = font_list[0]
        else:
            font_choice = np.random.choice(font_list)
        return (font_choice, get_font_path(font_choice))

    def get_glyph_strokes(self, char) -> tuple[OpsSet, float]:
        """
        Gives the glyph operations as well the width of the char for offsetting purpose
        """
        _font_choice, font_path = self.get_random_font_choice()
        font = TTFont(font_path)
        glyph_set = font.getGlyphSet()
        cmap = font.getBestCmap()
        glyph_name = cmap.get(ord(char))
        if glyph_name is None:
            return OpsSet(initial_set=[]), 0.0

        units_per_em = font["head"].unitsPerEm  # usually 1000
        scale = (
            self.scale_factor * self.font_size / units_per_em
        )  # normalize to desired size
        glyph = glyph_set[glyph_name]
        pen = CustomPen(glyph_set, scale=scale)
        glyph.draw(pen)

        width = glyph.width * scale
        return pen.opsset, width

    def get_glyph_space(self) -> tuple[float, float]:
        """
        Gives the width of the space, or an average width
        """
        _font_choice, font_path = self.get_random_font_choice()
        font = TTFont(font_path)
        glyph_set = font.getGlyphSet()
        units_per_em = font["head"].unitsPerEm
        scale = self.scale_factor * self.font_size / units_per_em

        avg_char_width = font["hhea"].advanceWidthMax * scale * 0.5
        space_width = (
            glyph_set["space"].width * scale if "space" in glyph_set else avg_char_width
        )
        return space_width, scale

    def draw(self) -> OpsSet:
        opsset = OpsSet(initial_set=[])
        opsset.add(
            Ops(
                OpsType.SET_PEN,
                {
                    "color": self.stroke_style.color,
                    "opacity": self.stroke_style.opacity,
                    "width": self.stroke_style.width,
                },
            )
        )
        line_opssets = [
            self._render_line(line_text, index * self._get_line_step())
            for index, line_text in enumerate(self._get_lines())
        ]
        self._align_lines(line_opssets)
        for line_opsset in line_opssets:
            opsset.extend(line_opsset)

        target_anchor = self._get_target_anchor()
        self._position_opsset(opsset, target_anchor)
        self._fit_to_rect_box(opsset, target_anchor)
        return opsset
