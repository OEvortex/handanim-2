
import numpy as np

from handanim.core.draw_ops import Ops, OpsSet, OpsType
from handanim.core.drawable import Drawable
from handanim.core.utils import get_line_slope_angle

from .curves import Curve
from .lines import Line, LinearPath


class Arrow(Drawable):

    def __init__(
        self,
        start: tuple[float, float],
        end: tuple[float, float],
        arrow_head_type: str = "->",  # valid values are: ->, ->>, -|>
        arrow_head_size: float = 10.0,
        arrow_head_angle: float = 45.0,
        control_points: list[tuple[float, float]] | None = None,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.args = args
        self.kwargs = kwargs
        self.start = start
        self.end = end
        self.arrow_head_type = arrow_head_type
        self.arrow_head_size = arrow_head_size
        self.arrow_head_angle = arrow_head_angle
        self.control_points = control_points

    def draw(self):
        # If control_points provided, use curved arrow logic
        if self.control_points:
            return self._draw_curved()

        # we will draw the arrow from (0, 0) and without rotation,
        # after drawing, we will do the rotation and translation
        opsset = OpsSet(initial_set=[])
        angle = get_line_slope_angle(self.start, self.end)  # get the angle from start to end
        arrow_length = np.sqrt((self.end[1] - self.start[1]) ** 2 + (self.end[0] - self.start[0]) ** 2)
        arrow_head_angle = np.deg2rad(self.arrow_head_angle)

        # now draw the main length
        arrow_line = Line(start=(0, 0), end=(arrow_length, 0), stroke_style=self.stroke_style, sketch_style=self.sketch_style)
        opsset.extend(arrow_line.draw())

        # now draw the arrowhead
        opsset.add(
            Ops(
                type=OpsType.MOVE_TO,
                data=[
                    (
                        arrow_length - np.cos(arrow_head_angle) * self.arrow_head_size,
                        -np.sin(arrow_head_angle) * self.arrow_head_size,
                    )
                ],
            )
        )
        arrow_head = LinearPath(
            points=[
                (
                    arrow_length - np.cos(arrow_head_angle) * self.arrow_head_size,
                    -np.sin(arrow_head_angle) * self.arrow_head_size,
                ),  # the top-left corner of arrowhead
                (arrow_length, 0),  # the tip of the arrowhead
                (
                    arrow_length - np.cos(arrow_head_angle) * self.arrow_head_size,
                    np.sin(arrow_head_angle) * self.arrow_head_size,
                ),
            ],
            stroke_style=self.stroke_style,
            sketch_style=self.sketch_style,
        )
        opsset.extend(arrow_head.draw())

        # check for arrow_head type now
        if self.arrow_head_type == "->>":
            # add another arrowhead
            opsset.add(
                Ops(
                    type=OpsType.MOVE_TO,
                    data=[
                        (
                            arrow_length - self.arrow_head_size / 2 - np.cos(arrow_head_angle) * self.arrow_head_size,
                            -np.sin(arrow_head_angle) * self.arrow_head_size,
                        )
                    ],
                )
            )

            arrow_head_shift = 0 if self.arrow_head_type == "-|>" else self.arrow_head_size / 2
            arrow_head2 = LinearPath(
                points=[
                    (
                        arrow_length - arrow_head_shift - np.cos(arrow_head_angle) * self.arrow_head_size,
                        -np.sin(arrow_head_angle) * self.arrow_head_size,
                    ),  # the top-left corner of arrowhead
                    (arrow_length - self.arrow_head_size / 2, 0),  # the tip of the second arrowhead
                    (
                        arrow_length - arrow_head_shift - np.cos(arrow_head_angle) * self.arrow_head_size,
                        np.sin(arrow_head_angle) * self.arrow_head_size,
                    ),
                ],
                stroke_style=self.stroke_style,
                sketch_style=self.sketch_style,
            )
            opsset.extend(arrow_head2.draw())
        elif self.arrow_head_type == "-|>":
            bar_x = arrow_length - self.arrow_head_size / 2
            bar_half_height = np.sin(arrow_head_angle) * self.arrow_head_size
            arrow_bar = LinearPath(
                points=[
                    (bar_x, -bar_half_height),
                    (bar_x, bar_half_height),
                ],
                stroke_style=self.stroke_style,
                sketch_style=self.sketch_style,
            )
            opsset.extend(arrow_bar.draw())

        opsset.rotate(np.rad2deg(angle), center_of_rotation=(0, 0))
        opsset.translate(offset_x=self.start[0], offset_y=self.start[1])
        return opsset

    def _draw_curved(self):
        """Draw a curved arrow using control points."""
        from .curves import Curve  # Import here to avoid circular import

        opsset = OpsSet(initial_set=[])

        # Build the full path: start -> control_points -> end
        points = [self.start] + self.control_points + [self.end]

        # Get the angle from last segment for arrowhead orientation
        if len(points) >= 2:
            angle = get_line_slope_angle(points[-2], self.end)
        else:
            angle = 0
        arrow_head_angle = np.deg2rad(self.arrow_head_angle)

        # Draw the curve through all points
        curve = Curve(points, stroke_style=self.stroke_style, sketch_style=self.sketch_style)
        opsset.extend(curve.draw())

        # Draw arrowhead at the end point
        # Calculate arrowhead points based on the angle of the last segment
        cos_a = np.cos(angle)
        sin_a = np.sin(angle)

        # Arrowhead wing points (rotated relative to end point)
        wing1_x = self.end[0] - self.arrow_head_size * np.cos(arrow_head_angle) * cos_a + self.arrow_head_size * np.sin(arrow_head_angle) * sin_a
        wing1_y = self.end[1] - self.arrow_head_size * np.cos(arrow_head_angle) * sin_a - self.arrow_head_size * np.sin(arrow_head_angle) * cos_a

        wing2_x = self.end[0] - self.arrow_head_size * np.cos(arrow_head_angle) * cos_a - self.arrow_head_size * np.sin(arrow_head_angle) * sin_a
        wing2_y = self.end[1] - self.arrow_head_size * np.cos(arrow_head_angle) * sin_a + self.arrow_head_size * np.sin(arrow_head_angle) * cos_a

        # Draw arrowhead wings
        arrow_head1 = Line(
            start=(wing1_x, wing1_y),
            end=self.end,
            stroke_style=self.stroke_style,
            sketch_style=self.sketch_style,
        )
        arrow_head2 = Line(
            start=(wing2_x, wing2_y),
            end=self.end,
            stroke_style=self.stroke_style,
            sketch_style=self.sketch_style,
        )
        opsset.extend(arrow_head1.draw())
        opsset.extend(arrow_head2.draw())

        # Handle double arrow (->>) and bar (-|>) types
        if self.arrow_head_type == "->>":
            # Draw second arrowhead shifted back
            shift = self.arrow_head_size / 2
            shift_x = shift * cos_a
            shift_y = shift * sin_a
            mid_point = (self.end[0] - shift_x, self.end[1] - shift_y)

            wing1_x2 = mid_point[0] - self.arrow_head_size * np.cos(arrow_head_angle) * cos_a + self.arrow_head_size * np.sin(arrow_head_angle) * sin_a
            wing1_y2 = mid_point[1] - self.arrow_head_size * np.cos(arrow_head_angle) * sin_a - self.arrow_head_size * np.sin(arrow_head_angle) * cos_a

            wing2_x2 = mid_point[0] - self.arrow_head_size * np.cos(arrow_head_angle) * cos_a - self.arrow_head_size * np.sin(arrow_head_angle) * sin_a
            wing2_y2 = mid_point[1] - self.arrow_head_size * np.cos(arrow_head_angle) * sin_a + self.arrow_head_size * np.sin(arrow_head_angle) * cos_a

            arrow_head3 = Line(start=(wing1_x2, wing1_y2), end=mid_point, stroke_style=self.stroke_style, sketch_style=self.sketch_style)
            arrow_head4 = Line(start=(wing2_x2, wing2_y2), end=mid_point, stroke_style=self.stroke_style, sketch_style=self.sketch_style)
            opsset.extend(arrow_head3.draw())
            opsset.extend(arrow_head4.draw())

        elif self.arrow_head_type == "-|>":
            # Draw bar
            bar_x = self.end[0] - (self.arrow_head_size / 2) * cos_a
            bar_y = self.end[1] - (self.arrow_head_size / 2) * sin_a
            bar_half_height = np.sin(arrow_head_angle) * self.arrow_head_size

            bar_start = (bar_x - bar_half_height * sin_a, bar_y + bar_half_height * cos_a)
            bar_end = (bar_x + bar_half_height * sin_a, bar_y - bar_half_height * cos_a)

            arrow_bar = Line(start=bar_start, end=bar_end, stroke_style=self.stroke_style, sketch_style=self.sketch_style)
            opsset.extend(arrow_bar.draw())

        return opsset


class CurvedArrow(Drawable):

    def __init__(
        self,
        points: list[tuple[float, float]],  # the list of points that defines the curve
        arrow_head_type: str = "->",  # valid values are: ->, ->>, -|>
        arrow_head_size: float = 10.0,
        arrow_head_angle: float = 45.0,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.args = args
        self.kwargs = kwargs
        self.points = points
        self.arrow_head_type = arrow_head_type
        self.arrow_head_size = arrow_head_size
        self.arrow_head_angle = arrow_head_angle

    def draw(self) -> OpsSet:
        opsset = OpsSet(initial_set=[])

        # get the arrow head angle from last two points
        if len(self.points) < 2:
            msg = "CurvedArrow must have at least two points"
            raise ValueError(msg)

        end_point = self.points[-1]
        angle = get_line_slope_angle(self.points[-2], end_point)
        arrow_head_angle = np.deg2rad(self.arrow_head_angle)
        rotation_values = [np.cos(-angle), np.sin(-angle)]

        # do negative rotation for the points
        rotated_points = [
            (
                end_point[0] + rotation_values[0] * (x - end_point[0]) - rotation_values[1] * (y - end_point[1]),
                end_point[1] + rotation_values[1] * (x - end_point[0]) + rotation_values[0] * (y - end_point[1]),
            )
            for x, y in self.points
        ]

        # draw the curve
        curve = Curve(rotated_points, *self.args, **self.kwargs)
        opsset.extend(curve.draw())

        # draw the arrow head
        for arrow_scale in [-1, 1]:
            arrow_line = Line(
                start=self.points[0],
                end=(
                    end_point[0] - np.cos(arrow_head_angle) * self.arrow_head_size,
                    end_point[1] + arrow_scale * np.sin(arrow_head_angle) * self.arrow_head_size,
                ),
                stroke_style=self.stroke_style,
                sketch_style=self.sketch_style,
            )
            opsset.extend(arrow_line.draw())
            opsset.add(Ops(OpsType.MOVE_TO, data=[end_point]))  # move to the end point again

        # check for the arrow head type
        if self.arrow_head_type == "->>":
            for arrow_scale in [-1, 1]:
                arrow_line = Line(
                    start=(end_point[0] - self.arrow_head_size / 2, end_point[1]),
                    end=(
                        end_point[0] - self.arrow_head_size / 2 - np.cos(arrow_head_angle) * self.arrow_head_size,
                        end_point[1] + arrow_scale * np.sin(arrow_head_angle) * self.arrow_head_size,
                    ),
                    stroke_style=self.stroke_style,
                    sketch_style=self.sketch_style,
                )
                opsset.extend(arrow_line.draw())
                opsset.add(Ops(OpsType.MOVE_TO, data=[end_point]))  # move to the end point again

        elif self.arrow_head_type == "-|>":
            bar_x = end_point[0] - self.arrow_head_size / 2
            bar_half_height = np.sin(arrow_head_angle) * self.arrow_head_size
            arrow_bar = Line(
                start=(bar_x, end_point[1] - bar_half_height),
                end=(bar_x, end_point[1] + bar_half_height),
                stroke_style=self.stroke_style,
                sketch_style=self.sketch_style,
            )
            opsset.extend(arrow_bar.draw())
            opsset.add(Ops(OpsType.MOVE_TO, data=[end_point]))  # move to the end point again

        # finally, rotate the opset back to the original angle
        opsset.rotate(np.rad2deg(angle), center_of_rotation=end_point)
        return opsset
