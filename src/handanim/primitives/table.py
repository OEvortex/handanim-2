from __future__ import annotations

from handanim.core.draw_ops import OpsSet
from handanim.core.drawable import Drawable, DrawableGroup
from handanim.core.styles import FillStyle, StrokeStyle

from .lines import Line
from .polygons import Rectangle
from .text import Text


def _normalize_sizes(name: str, value: float | list[float], count: int) -> list[float]:
    if isinstance(value, int | float):
        sizes = [float(value)] * count
    else:
        sizes = [float(size) for size in value]

    if len(sizes) != count:
        msg = f"{name} must contain exactly {count} values"
        raise ValueError(msg)
    if any(size <= 0 for size in sizes):
        msg = f"{name} values must all be positive"
        raise ValueError(msg)
    return sizes


def _prefix_offsets(sizes: list[float]) -> list[float]:
    offsets = [0.0]
    for size in sizes[:-1]:
        offsets.append(offsets[-1] + size)
    return offsets


class Table(Drawable):
    def __init__(
        self,
        data: list[list[str]],
        top_left: tuple[float, float],
        col_widths: float | list[float],
        row_heights: float | list[float],
        font_size: int = 28,
        font_name: str | None = None,
        cell_padding: float = 12.0,
        text_stroke_style: StrokeStyle | None = None,
        header_rows: int = 0,
        header_columns: int = 0,
        header_fill_style: FillStyle | None = None,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        if not data or not data[0]:
            msg = "Table data must contain at least one row and one column"
            raise ValueError(msg)

        column_count = len(data[0])
        if any(len(row) != column_count for row in data):
            msg = "All table rows must have the same number of columns"
            raise ValueError(msg)
        if cell_padding < 0:
            msg = "cell_padding must be non-negative"
            raise ValueError(msg)
        if header_rows < 0 or header_columns < 0:
            msg = "header_rows and header_columns must be non-negative"
            raise ValueError(msg)
        if header_rows > len(data) or header_columns > column_count:
            msg = "header_rows/header_columns cannot exceed table size"
            raise ValueError(msg)

        self.data = [[str(cell) for cell in row] for row in data]
        self.top_left = top_left
        self.row_count = len(self.data)
        self.column_count = column_count
        self.col_widths = _normalize_sizes("col_widths", col_widths, self.column_count)
        self.row_heights = _normalize_sizes("row_heights", row_heights, self.row_count)
        self.column_offsets = _prefix_offsets(self.col_widths)
        self.row_offsets = _prefix_offsets(self.row_heights)
        self.width = sum(self.col_widths)
        self.height = sum(self.row_heights)
        self.font_size = font_size
        self.font_name = font_name
        self.cell_padding = float(cell_padding)
        self.text_stroke_style = text_stroke_style or self.stroke_style
        self.header_rows = header_rows
        self.header_columns = header_columns
        self.header_fill_style = header_fill_style

    @property
    def center(self) -> tuple[float, float]:
        return (self.top_left[0] + self.width / 2, self.top_left[1] + self.height / 2)

    def cell_bbox(self, row: int, col: int) -> tuple[float, float, float, float]:
        if not 0 <= row < self.row_count or not 0 <= col < self.column_count:
            msg = f"Cell index out of range: ({row}, {col})"
            raise IndexError(msg)
        x = self.top_left[0] + self.column_offsets[col]
        y = self.top_left[1] + self.row_offsets[row]
        return (x, y, self.col_widths[col], self.row_heights[row])

    def cell_center(self, row: int, col: int) -> tuple[float, float]:
        x, y, width, height = self.cell_bbox(row, col)
        return (x + width / 2, y + height / 2)

    def _cell_fill_style(self, row: int, col: int) -> FillStyle | None:
        if (row < self.header_rows or col < self.header_columns) and self.header_fill_style is not None:
            return self.header_fill_style
        return self.fill_style

    def _make_fill_rect(self, row: int, col: int) -> Drawable | None:
        fill_style = self._cell_fill_style(row, col)
        if fill_style is None:
            return None
        x, y, width, height = self.cell_bbox(row, col)
        return Rectangle(
            top_left=(x, y),
            width=width,
            height=height,
            stroke_style=StrokeStyle(color=self.stroke_style.color, width=0, opacity=0),
            sketch_style=self.sketch_style,
            fill_style=fill_style,
        )

    def draw(self) -> OpsSet:
        elements: list[Drawable] = []

        for row in range(self.row_count):
            for col in range(self.column_count):
                fill_rect = self._make_fill_rect(row, col)
                if fill_rect is not None:
                    elements.append(fill_rect)

                cell_text = self.data[row][col]
                if cell_text:
                    x, y, width, height = self.cell_bbox(row, col)
                    elements.append(
                        Text(
                            text=cell_text,
                            position=self.cell_center(row, col),
                            font_size=self.font_size,
                            font_name=self.font_name,
                            rect_box=(x, y, width, height),
                            rect_padding=self.cell_padding,
                            stroke_style=self.text_stroke_style,
                            sketch_style=self.sketch_style,
                        )
                    )

        elements.append(
            Rectangle(
                top_left=self.top_left,
                width=self.width,
                height=self.height,
                stroke_style=self.stroke_style,
                sketch_style=self.sketch_style,
            )
        )

        for col_offset in self.column_offsets[1:]:
            x = self.top_left[0] + col_offset
            elements.append(
                Line(
                    start=(x, self.top_left[1]),
                    end=(x, self.top_left[1] + self.height),
                    stroke_style=self.stroke_style,
                    sketch_style=self.sketch_style,
                )
            )

        for row_offset in self.row_offsets[1:]:
            y = self.top_left[1] + row_offset
            elements.append(
                Line(
                    start=(self.top_left[0], y),
                    end=(self.top_left[0] + self.width, y),
                    stroke_style=self.stroke_style,
                    sketch_style=self.sketch_style,
                )
            )

        return DrawableGroup(elements).draw()