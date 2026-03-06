from __future__ import annotations

from handanim.core.draw_ops import OpsSet
from handanim.core.drawable import Drawable, DrawableGroup
from handanim.core.styles import StrokeStyle

from .arrow import Arrow
from .lines import LinearPath
from .polygons import Polygon, Rectangle, RoundedRectangle
from .text import Text


def _dedupe_points(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    unique_points: list[tuple[float, float]] = []
    for point in points:
        if not unique_points or unique_points[-1] != point:
            unique_points.append(point)
    return unique_points


class FlowchartConnector(Drawable):
    def __init__(
        self,
        start: tuple[float, float],
        end: tuple[float, float],
        waypoints: list[tuple[float, float]] | None = None,
        arrow_head_type: str = "->",
        arrow_head_size: float = 10.0,
        arrow_head_angle: float = 45.0,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.arrow_head_type = arrow_head_type
        self.arrow_head_size = arrow_head_size
        self.arrow_head_angle = arrow_head_angle
        self.points = _dedupe_points([start, *(waypoints or []), end])
        if len(self.points) < 2:
            msg = "FlowchartConnector requires at least two unique points"
            raise ValueError(msg)

    def draw(self) -> OpsSet:
        if len(self.points) == 2:
            return Arrow(
                start_point=self.points[0],
                end_point=self.points[1],
                arrow_head_type=self.arrow_head_type,
                arrow_head_size=self.arrow_head_size,
                arrow_head_angle=self.arrow_head_angle,
                stroke_style=self.stroke_style,
                sketch_style=self.sketch_style,
            ).draw()

        opsset = OpsSet(initial_set=[])
        if len(self.points[:-1]) >= 2:
            opsset.extend(
                LinearPath(
                    points=self.points[:-1],
                    stroke_style=self.stroke_style,
                    sketch_style=self.sketch_style,
                ).draw()
            )
        opsset.extend(
            Arrow(
                start_point=self.points[-2],
                end_point=self.points[-1],
                arrow_head_type=self.arrow_head_type,
                arrow_head_size=self.arrow_head_size,
                arrow_head_angle=self.arrow_head_angle,
                stroke_style=self.stroke_style,
                sketch_style=self.sketch_style,
            ).draw()
        )
        return opsset


class FlowchartNode(Drawable):
    def __init__(
        self,
        text: str,
        top_left: tuple[float, float],
        width: float,
        height: float,
        font_size: int = 30,
        font_name: str | None = None,
        text_padding: float = 18.0,
        text_stroke_style: StrokeStyle | None = None,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.text = text
        self.top_left = top_left
        self.width = width
        self.height = height
        self.font_size = font_size
        self.font_name = font_name
        self.text_padding = text_padding
        self.text_stroke_style = text_stroke_style or self.stroke_style

    @property
    def center(self) -> tuple[float, float]:
        return (self.top_left[0] + self.width / 2, self.top_left[1] + self.height / 2)

    def anchor_point(self, side: str) -> tuple[float, float]:
        anchor_map = {
            "top": (self.center[0], self.top_left[1]),
            "right": (self.top_left[0] + self.width, self.center[1]),
            "bottom": (self.center[0], self.top_left[1] + self.height),
            "left": (self.top_left[0], self.center[1]),
            "center": self.center,
        }
        if side not in anchor_map:
            msg = f"Unsupported anchor side: {side}"
            raise ValueError(msg)
        return anchor_map[side]

    def _auto_side_towards(self, other: FlowchartNode) -> str:
        dx = other.center[0] - self.center[0]
        dy = other.center[1] - self.center[1]
        if abs(dx) >= abs(dy):
            return "right" if dx >= 0 else "left"
        return "bottom" if dy >= 0 else "top"

    def _make_text(self) -> Text | None:
        if not self.text:
            return None
        return Text(
            text=self.text,
            position=self.center,
            font_size=self.font_size,
            font_name=self.font_name,
            rect_box=(self.top_left[0], self.top_left[1], self.width, self.height),
            rect_padding=self.text_padding,
            stroke_style=self.text_stroke_style,
            sketch_style=self.sketch_style,
        )

    def _make_body(self) -> Drawable:
        msg = f"Body creation not implemented for {self.__class__.__name__}"
        raise NotImplementedError(msg)

    def draw(self) -> OpsSet:
        elements = [self._make_body()]
        label = self._make_text()
        if label is not None:
            elements.append(label)
        return DrawableGroup(elements).draw()

    def connect_to(
        self,
        other: FlowchartNode,
        start_side: str | None = None,
        end_side: str | None = None,
        waypoints: list[tuple[float, float]] | None = None,
        elbow: str | None = None,
        **kwargs,
    ) -> FlowchartConnector:
        start_side = start_side or self._auto_side_towards(other)
        end_side = end_side or other._auto_side_towards(self)
        start = self.anchor_point(start_side)
        end = other.anchor_point(end_side)

        if waypoints is None and elbow is not None:
            if elbow == "horizontal":
                waypoints = [(end[0], start[1])]
            elif elbow == "vertical":
                waypoints = [(start[0], end[1])]
            else:
                msg = f"Unsupported elbow type: {elbow}"
                raise ValueError(msg)

        return FlowchartConnector(start=start, end=end, waypoints=waypoints, **kwargs)


class FlowchartProcess(FlowchartNode):
    def _make_body(self) -> Drawable:
        return Rectangle(
            top_left=self.top_left,
            width=self.width,
            height=self.height,
            stroke_style=self.stroke_style,
            sketch_style=self.sketch_style,
            fill_style=self.fill_style,
        )


class FlowchartTerminator(FlowchartNode):
    def __init__(self, *args, border_radius: float = 0.45, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.border_radius = border_radius

    def _make_body(self) -> Drawable:
        return RoundedRectangle(
            top_left=self.top_left,
            width=self.width,
            height=self.height,
            border_radius=self.border_radius,
            stroke_style=self.stroke_style,
            sketch_style=self.sketch_style,
            fill_style=self.fill_style,
        )


class FlowchartDecision(FlowchartNode):
    def _make_body(self) -> Drawable:
        x, y = self.top_left
        half_width = self.width / 2
        half_height = self.height / 2
        return Polygon(
            points=[
                (x + half_width, y),
                (x + self.width, y + half_height),
                (x + half_width, y + self.height),
                (x, y + half_height),
            ],
            stroke_style=self.stroke_style,
            sketch_style=self.sketch_style,
            fill_style=self.fill_style,
        )


class FlowchartInputOutput(FlowchartNode):
    def __init__(self, *args, slant: float | None = None, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.slant = slant or min(self.width * 0.18, self.height * 0.35)

    def _make_body(self) -> Drawable:
        x, y = self.top_left
        return Polygon(
            points=[
                (x + self.slant, y),
                (x + self.width, y),
                (x + self.width - self.slant, y + self.height),
                (x, y + self.height),
            ],
            stroke_style=self.stroke_style,
            sketch_style=self.sketch_style,
            fill_style=self.fill_style,
        )