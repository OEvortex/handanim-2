from __future__ import annotations

import math
from typing import Callable

import numpy as np

from ..core.drawable import Drawable, DrawableGroup
from ..core.draw_ops import Ops, OpsSet, OpsType
from ..core.styles import FillStyle, SketchStyle, StrokeStyle


def _as_3d(point: tuple[float, float, float] | np.ndarray) -> np.ndarray:
    point_array = np.array(point, dtype=float)
    if point_array.shape != (3,):
        msg = f"Expected a 3D point, got shape {point_array.shape}"
        raise ValueError(msg)
    return point_array


class PolyLine3D(Drawable):
    def __init__(self, points: list[tuple[float, float, float] | np.ndarray], closed=False, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.points = [_as_3d(point) for point in points]
        self.closed = closed

    def draw(self) -> OpsSet:
        opsset = OpsSet(initial_set=[])
        opsset.add(
            Ops(
                type=OpsType.POLYLINE_3D,
                data={
                    "points": [tuple(point.tolist()) for point in self.points],
                    "closed": self.closed,
                    "stroke_color": self.stroke_style.color,
                    "stroke_width": self.stroke_style.width,
                    "stroke_opacity": self.stroke_style.opacity,
                },
                meta={"drawable_id": self.id},
            )
        )
        return opsset


class Line3D(PolyLine3D):
    def __init__(self, start, end, *args, **kwargs):
        self.start = _as_3d(start)
        self.end = _as_3d(end)
        super().__init__([self.start, self.end], closed=False, *args, **kwargs)


class Mesh3D(Drawable):
    def __init__(
        self,
        vertices: list[tuple[float, float, float] | np.ndarray],
        faces: list[list[int] | tuple[int, ...]],
        face_fill_colors: list[tuple[float, float, float] | None] | None = None,
        shading_factor: float | None = None,
        backface_cull: bool = True,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.vertices = [_as_3d(vertex) for vertex in vertices]
        self.faces = [list(face) for face in faces]
        self.face_fill_colors = face_fill_colors
        self.shading_factor = shading_factor
        self.backface_cull = backface_cull

    def draw(self) -> OpsSet:
        opsset = OpsSet(initial_set=[])
        for index, face in enumerate(self.faces):
            fill_color = None
            if self.fill_style is not None:
                fill_color = self.fill_style.color
            if self.face_fill_colors is not None and index < len(self.face_fill_colors):
                fill_color = self.face_fill_colors[index]
            opsset.add(
                Ops(
                    type=OpsType.POLYGON_3D,
                    data={
                        "points": [tuple(self.vertices[vertex_index].tolist()) for vertex_index in face],
                        "fill_color": fill_color,
                        "fill_opacity": 0.0 if self.fill_style is None else self.fill_style.opacity,
                        "stroke_color": self.stroke_style.color,
                        "stroke_width": self.stroke_style.width,
                        "stroke_opacity": self.stroke_style.opacity,
                        "shading_factor": self.shading_factor,
                        "backface_cull": self.backface_cull,
                    },
                    meta={"drawable_id": self.id, "face_index": index},
                )
            )
        return opsset


class ParametricSurface(Drawable):
    def __init__(
        self,
        func: Callable[[float, float], tuple[float, float, float] | np.ndarray],
        u_range: tuple[float, float] = (0.0, 1.0),
        v_range: tuple[float, float] = (0.0, 1.0),
        resolution: tuple[int, int] = (24, 24),
        checkerboard_colors: tuple[tuple[float, float, float], tuple[float, float, float]] | None = None,
        backface_cull: bool = False,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.func = func
        self.u_range = u_range
        self.v_range = v_range
        self.resolution = resolution
        self.checkerboard_colors = checkerboard_colors
        self.backface_cull = backface_cull

    def _get_face_color(self, u_index: int, v_index: int):
        if self.checkerboard_colors is not None:
            return self.checkerboard_colors[(u_index + v_index) % len(self.checkerboard_colors)]
        if self.fill_style is None:
            return None
        return self.fill_style.color

    def draw(self) -> OpsSet:
        u_steps, v_steps = self.resolution
        u_values = np.linspace(self.u_range[0], self.u_range[1], u_steps + 1)
        v_values = np.linspace(self.v_range[0], self.v_range[1], v_steps + 1)
        grid = [[_as_3d(self.func(float(u), float(v))) for v in v_values] for u in u_values]
        opsset = OpsSet(initial_set=[])

        for u_index in range(u_steps):
            for v_index in range(v_steps):
                points = [
                    grid[u_index][v_index],
                    grid[u_index + 1][v_index],
                    grid[u_index + 1][v_index + 1],
                    grid[u_index][v_index + 1],
                ]
                opsset.add(
                    Ops(
                        type=OpsType.POLYGON_3D,
                        data={
                            "points": [tuple(point.tolist()) for point in points],
                            "fill_color": self._get_face_color(u_index, v_index),
                            "fill_opacity": 0.0 if self.fill_style is None else self.fill_style.opacity,
                            "stroke_color": self.stroke_style.color,
                            "stroke_width": self.stroke_style.width,
                            "stroke_opacity": self.stroke_style.opacity,
                            "backface_cull": self.backface_cull,
                        },
                        meta={"drawable_id": self.id, "u_index": u_index, "v_index": v_index},
                    )
                )
        return opsset


Surface = ParametricSurface


class Sphere(ParametricSurface):
    def __init__(self, radius: float = 1.0, center=(0.0, 0.0, 0.0), *args, **kwargs):
        center_vec = _as_3d(center)
        kwargs.setdefault("backface_cull", True)

        def surface_func(u: float, v: float):
            return center_vec + radius * np.array(
                [
                    math.cos(u) * math.sin(v),
                    math.sin(u) * math.sin(v),
                    math.cos(v),
                ],
                dtype=float,
            )

        super().__init__(surface_func, u_range=(0.0, 2 * math.pi), v_range=(0.0, math.pi), *args, **kwargs)


class Cylinder(ParametricSurface):
    def __init__(self, radius: float = 1.0, height: float = 2.0, center=(0.0, 0.0, 0.0), *args, **kwargs):
        center_vec = _as_3d(center)
        kwargs.setdefault("backface_cull", True)

        def surface_func(u: float, v: float):
            return center_vec + np.array(
                [radius * math.cos(u), radius * math.sin(u), v],
                dtype=float,
            )

        super().__init__(surface_func, u_range=(0.0, 2 * math.pi), v_range=(-height / 2, height / 2), *args, **kwargs)


class Cone(ParametricSurface):
    def __init__(self, base_radius: float = 1.0, height: float = 2.0, center=(0.0, 0.0, 0.0), *args, **kwargs):
        center_vec = _as_3d(center)
        kwargs.setdefault("backface_cull", True)

        def surface_func(u: float, v: float):
            radius = base_radius * (1.0 - (v / height))
            return center_vec + np.array(
                [radius * math.cos(u), radius * math.sin(u), v - height / 2],
                dtype=float,
            )

        super().__init__(surface_func, u_range=(0.0, 2 * math.pi), v_range=(0.0, height), *args, **kwargs)


class Torus(ParametricSurface):
    def __init__(
        self,
        major_radius: float = 2.0,
        minor_radius: float = 0.5,
        center=(0.0, 0.0, 0.0),
        *args,
        **kwargs,
    ):
        center_vec = _as_3d(center)
        kwargs.setdefault("backface_cull", True)

        def surface_func(u: float, v: float):
            ring = major_radius + minor_radius * math.cos(v)
            return center_vec + np.array(
                [ring * math.cos(u), ring * math.sin(u), minor_radius * math.sin(v)],
                dtype=float,
            )

        super().__init__(surface_func, u_range=(0.0, 2 * math.pi), v_range=(0.0, 2 * math.pi), *args, **kwargs)


class Cube(Mesh3D):
    def __init__(self, side_length: float = 2.0, center=(0.0, 0.0, 0.0), *args, **kwargs):
        cx, cy, cz = _as_3d(center)
        half = side_length / 2
        vertices = [
            (cx - half, cy - half, cz - half),
            (cx + half, cy - half, cz - half),
            (cx + half, cy + half, cz - half),
            (cx - half, cy + half, cz - half),
            (cx - half, cy - half, cz + half),
            (cx + half, cy - half, cz + half),
            (cx + half, cy + half, cz + half),
            (cx - half, cy + half, cz + half),
        ]
        faces = [
            [0, 3, 2, 1],
            [4, 5, 6, 7],
            [0, 1, 5, 4],
            [1, 2, 6, 5],
            [2, 3, 7, 6],
            [3, 0, 4, 7],
        ]
        super().__init__(vertices=vertices, faces=faces, *args, **kwargs)


class Prism(Cube):
    def __init__(self, dimensions=(2.0, 2.0, 2.0), center=(0.0, 0.0, 0.0), *args, **kwargs):
        cx, cy, cz = _as_3d(center)
        dx, dy, dz = [float(value) / 2 for value in dimensions]
        vertices = [
            (cx - dx, cy - dy, cz - dz),
            (cx + dx, cy - dy, cz - dz),
            (cx + dx, cy + dy, cz - dz),
            (cx - dx, cy + dy, cz - dz),
            (cx - dx, cy - dy, cz + dz),
            (cx + dx, cy - dy, cz + dz),
            (cx + dx, cy + dy, cz + dz),
            (cx - dx, cy + dy, cz + dz),
        ]
        faces = [
            [0, 3, 2, 1],
            [4, 5, 6, 7],
            [0, 1, 5, 4],
            [1, 2, 6, 5],
            [2, 3, 7, 6],
            [3, 0, 4, 7],
        ]
        Mesh3D.__init__(self, vertices=vertices, faces=faces, *args, **kwargs)


class Dot3D(Sphere):
    def __init__(self, point=(0.0, 0.0, 0.0), radius: float = 0.08, *args, **kwargs):
        super().__init__(radius=radius, center=point, resolution=(12, 12), *args, **kwargs)


class ThreeDAxes(DrawableGroup):
    def __init__(
        self,
        x_range: tuple[float, float, float] = (-4.0, 4.0, 1.0),
        y_range: tuple[float, float, float] = (-4.0, 4.0, 1.0),
        z_range: tuple[float, float, float] = (-4.0, 4.0, 1.0),
        x_length: float = 8.0,
        y_length: float = 8.0,
        z_length: float = 8.0,
        include_ticks: bool = True,
        tick_size: float = 0.12,
        axis_stroke_style: StrokeStyle | None = None,
        sketch_style: SketchStyle = SketchStyle(),
        id: str | None = None,
    ) -> None:
        self.x_range = x_range
        self.y_range = y_range
        self.z_range = z_range
        self.x_length = x_length
        self.y_length = y_length
        self.z_length = z_length
        self.include_ticks = include_ticks
        self.tick_size = tick_size
        if axis_stroke_style is None:
            axis_stroke_style = StrokeStyle(color=(0.15, 0.15, 0.15), width=1.2, opacity=1)

        elements: list[Drawable] = [
            Line3D(self.c2p(x_range[0], 0, 0), self.c2p(x_range[1], 0, 0), stroke_style=axis_stroke_style),
            Line3D(self.c2p(0, y_range[0], 0), self.c2p(0, y_range[1], 0), stroke_style=axis_stroke_style),
            Line3D(self.c2p(0, 0, z_range[0]), self.c2p(0, 0, z_range[1]), stroke_style=axis_stroke_style),
        ]
        if include_ticks:
            elements.extend(self._build_ticks(axis_stroke_style))
        super().__init__(elements=elements, grouping_method="parallel", stroke_style=axis_stroke_style, sketch_style=sketch_style, id=id)

    def _axis_coordinate_to_world(self, value: float, axis_range, axis_length: float) -> float:
        axis_min, axis_max = axis_range[0], axis_range[1]
        midpoint = (axis_min + axis_max) / 2
        return (value - midpoint) * axis_length / (axis_max - axis_min)

    def c2p(self, x: float, y: float, z: float) -> np.ndarray:
        return np.array(
            [
                self._axis_coordinate_to_world(x, self.x_range, self.x_length),
                self._axis_coordinate_to_world(y, self.y_range, self.y_length),
                self._axis_coordinate_to_world(z, self.z_range, self.z_length),
            ],
            dtype=float,
        )

    coords_to_point = c2p

    def _build_ticks(self, stroke_style: StrokeStyle) -> list[Drawable]:
        tick_drawables: list[Drawable] = []
        for value in np.arange(self.x_range[0], self.x_range[1] + 1e-9, self.x_range[2]):
            tick_point = self.c2p(float(value), 0.0, 0.0)
            tick_drawables.append(
                Line3D(
                    tick_point + np.array([0.0, -self.tick_size, 0.0]),
                    tick_point + np.array([0.0, self.tick_size, 0.0]),
                    stroke_style=stroke_style,
                )
            )
        for value in np.arange(self.y_range[0], self.y_range[1] + 1e-9, self.y_range[2]):
            tick_point = self.c2p(0.0, float(value), 0.0)
            tick_drawables.append(
                Line3D(
                    tick_point + np.array([-self.tick_size, 0.0, 0.0]),
                    tick_point + np.array([self.tick_size, 0.0, 0.0]),
                    stroke_style=stroke_style,
                )
            )
        for value in np.arange(self.z_range[0], self.z_range[1] + 1e-9, self.z_range[2]):
            tick_point = self.c2p(0.0, 0.0, float(value))
            tick_drawables.append(
                Line3D(
                    tick_point + np.array([-self.tick_size, 0.0, 0.0]),
                    tick_point + np.array([self.tick_size, 0.0, 0.0]),
                    stroke_style=stroke_style,
                )
            )
        return tick_drawables