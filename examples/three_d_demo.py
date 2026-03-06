import os

import numpy as np

from handanim.animations import FadeInAnimation, Rotate3DAnimation, Translate3DAnimation
from handanim.core import DrawableGroup, FillStyle, SpecialThreeDScene, StrokeStyle
from handanim.primitives import Cylinder, Prism, Sphere, Text


def smoothstep(value: float) -> float:
    value = float(np.clip(value, 0.0, 1.0))
    return value * value * (3.0 - 2.0 * value)


def build_car(center: tuple[float, float, float]) -> tuple[DrawableGroup, list[DrawableGroup]]:
    cx, cy, _cz = center
    paint = FillStyle(color=(0.84, 0.12, 0.08), opacity=0.96)
    paint_dark = FillStyle(color=(0.66, 0.08, 0.07), opacity=0.96)
    glass = FillStyle(color=(0.67, 0.86, 0.98), opacity=0.58)
    metal = FillStyle(color=(0.8, 0.82, 0.86), opacity=0.92)
    rubber = FillStyle(color=(0.08, 0.08, 0.1), opacity=0.99)
    lamp = FillStyle(color=(1.0, 0.95, 0.68), opacity=0.98)
    tail = FillStyle(color=(0.88, 0.18, 0.14), opacity=0.98)
    shadow = FillStyle(color=(0.02, 0.02, 0.03), opacity=0.22)
    stroke = StrokeStyle(color=(0.06, 0.06, 0.08), width=0.28, opacity=0.28)

    parts = [
        Prism(dimensions=(4.6, 2.0, 0.48), center=(cx, cy, 0.42), stroke_style=stroke, fill_style=paint),
        Prism(dimensions=(2.2, 1.7, 0.48), center=(cx - 0.2, cy, 0.94), stroke_style=stroke, fill_style=paint_dark),
        Prism(dimensions=(1.15, 1.86, 0.24), center=(cx + 1.42, cy, 0.7), stroke_style=stroke, fill_style=paint),
        Prism(dimensions=(0.95, 1.78, 0.22), center=(cx - 1.55, cy, 0.66), stroke_style=stroke, fill_style=paint_dark),
        Prism(dimensions=(0.32, 1.56, 0.46), center=(cx + 0.72, cy, 0.94), stroke_style=stroke, fill_style=glass),
        Prism(dimensions=(0.3, 1.46, 0.4), center=(cx - 1.0, cy, 0.9), stroke_style=stroke, fill_style=glass),
        Prism(dimensions=(0.9, 1.52, 0.38), center=(cx - 0.14, cy, 1.08), stroke_style=stroke, fill_style=glass),
        Prism(dimensions=(0.22, 2.02, 0.14), center=(cx + 2.29, cy, 0.34), stroke_style=stroke, fill_style=metal),
        Prism(dimensions=(0.18, 1.96, 0.14), center=(cx - 2.3, cy, 0.3), stroke_style=stroke, fill_style=metal),
        Prism(dimensions=(3.5, 0.08, 0.08), center=(cx, cy + 1.01, 0.32), stroke_style=stroke, fill_style=shadow),
        Prism(dimensions=(3.5, 0.08, 0.08), center=(cx, cy - 1.01, 0.32), stroke_style=stroke, fill_style=shadow),
    ]

    for side in (-0.82, 0.82):
        parts.append(Sphere(radius=0.11, center=(cx + 2.26, cy + side, 0.56), stroke_style=StrokeStyle(color=(0.98, 0.92, 0.72), width=0.06, opacity=0.22), fill_style=lamp, resolution=(10, 10)))
        parts.append(Sphere(radius=0.09, center=(cx - 2.28, cy + side, 0.52), stroke_style=StrokeStyle(color=(0.72, 0.12, 0.12), width=0.05, opacity=0.22), fill_style=tail, resolution=(10, 10)))
        parts.append(Sphere(radius=0.06, center=(cx + 0.56, cy + side * 1.14, 0.92), stroke_style=StrokeStyle(color=(0.2, 0.2, 0.24), width=0.04, opacity=0.18), fill_style=metal, resolution=(8, 8)))

    wheels: list[DrawableGroup] = []
    for wheel_x in (cx - 1.42, cx + 1.42):
        for wheel_y in (cy - 1.0, cy + 1.0):
            tire = Cylinder(radius=0.46, height=0.28, center=(wheel_x, wheel_y, 0.34), resolution=(22, 10), stroke_style=StrokeStyle(color=(0.03, 0.03, 0.03), width=0.09, opacity=0.18), fill_style=rubber).rotate3d(90, axis=(1.0, 0.0, 0.0))
            rim = Cylinder(radius=0.2, height=0.3, center=(wheel_x, wheel_y, 0.34), resolution=(18, 10), stroke_style=StrokeStyle(color=(0.78, 0.8, 0.84), width=0.04, opacity=0.14), fill_style=metal).rotate3d(90, axis=(1.0, 0.0, 0.0))
            wheel = DrawableGroup([tire, rim], grouping_method="parallel")
            wheels.append(wheel)
            parts.append(wheel)

    return DrawableGroup(parts, grouping_method="parallel"), wheels


def build_scene() -> SpecialThreeDScene:
    scene = SpecialThreeDScene(width=1280, height=720, fps=24, background_color=(0.95, 0.97, 1.0))
    scene.set_to_default_angled_camera_orientation(phi=74, theta=-112, zoom=1.16, frame_center=(0.0, 0.0, 0.6))

    title = Text("3D Sports Car Drive", position=(640, 70), font_size=40, stroke_style=StrokeStyle(color=(0.12, 0.16, 0.22), width=1.7))
    subtitle = Text("Improved model, upright camera, smoother motion", position=(640, 110), font_size=22, stroke_style=StrokeStyle(color=(0.28, 0.35, 0.45), width=1.0))
    scene.add_fixed_in_frame_mobjects(title, subtitle)

    road = Prism(dimensions=(30.0, 8.2, 0.06), center=(0.0, 0.0, -0.03), stroke_style=StrokeStyle(color=(0.16, 0.18, 0.2), width=0.08, opacity=0.08), fill_style=FillStyle(color=(0.2, 0.22, 0.26), opacity=0.98))
    shoulder_top = Prism(dimensions=(30.0, 0.42, 0.03), center=(0.0, 4.15, 0.01), stroke_style=StrokeStyle(color=(0.94, 0.94, 0.94), width=0.04, opacity=0.06), fill_style=FillStyle(color=(0.94, 0.94, 0.94), opacity=0.98))
    shoulder_bottom = Prism(dimensions=(30.0, 0.42, 0.03), center=(0.0, -4.15, 0.01), stroke_style=StrokeStyle(color=(0.94, 0.94, 0.94), width=0.04, opacity=0.06), fill_style=FillStyle(color=(0.94, 0.94, 0.94), opacity=0.98))
    grass_top = Prism(dimensions=(30.0, 5.0, 0.02), center=(0.0, 6.8, -0.04), stroke_style=StrokeStyle(color=(0.28, 0.46, 0.25), width=0.05, opacity=0.06), fill_style=FillStyle(color=(0.55, 0.74, 0.5), opacity=0.95))
    grass_bottom = Prism(dimensions=(30.0, 5.0, 0.02), center=(0.0, -6.8, -0.04), stroke_style=StrokeStyle(color=(0.28, 0.46, 0.25), width=0.05, opacity=0.06), fill_style=FillStyle(color=(0.55, 0.74, 0.5), opacity=0.95))
    lane_dashes = DrawableGroup([Prism(dimensions=(1.6, 0.16, 0.03), center=(x, 0.0, 0.01), stroke_style=StrokeStyle(color=(0.98, 0.98, 0.98), width=0.03, opacity=0.05), fill_style=FillStyle(color=(0.98, 0.98, 0.98), opacity=0.97)) for x in (-11.5, -8.7, -5.9, -3.1, -0.3, 2.5, 5.3, 8.1, 10.9)], grouping_method="parallel")

    car, wheels = build_car(center=(-8.0, 0.0, 0.0))
    drive_start, drive_duration, drive_offset = 1.0, 5.9, 15.0
    bounce_height = 0.09

    def car_progress(scene_time: float) -> float:
        return smoothstep((scene_time - drive_start) / drive_duration)

    def car_anchor(_drawable, scene_time: float):
        progress = car_progress(scene_time)
        bounce = bounce_height * np.sin(5.0 * np.pi * progress) * (1.0 - 0.45 * progress)
        return (-8.0 + drive_offset * progress, 0.0, 1.9 + bounce)

    car_label = Text("Sports coupe", position=(0, 0), font_size=24, stroke_style=StrokeStyle(color=(0.12, 0.15, 0.2), width=1.15))
    scene.add_fixed_orientation_mobjects(car_label, center_func=car_anchor)

    scene.add(FadeInAnimation(start_time=0.0, duration=0.35), title)
    scene.add(FadeInAnimation(start_time=0.12, duration=0.4), subtitle)
    for start, drawable in [(0.12, grass_top), (0.12, grass_bottom), (0.25, road), (0.35, shoulder_top), (0.35, shoulder_bottom), (0.45, lane_dashes), (0.78, car), (0.95, car_label)]:
        scene.add(FadeInAnimation(start_time=start, duration=0.7), drawable)

    scene.add(Translate3DAnimation(offset=(drive_offset, 0.0, 0.0), start_time=drive_start, duration=drive_duration, easing_fun=smoothstep), car)
    scene.add(Translate3DAnimation(offset=(0.0, 0.0, bounce_height), start_time=drive_start, duration=drive_duration, easing_fun=lambda t: np.sin(np.pi * 5.0 * smoothstep(t)) * max(0.0, 1.0 - 0.45 * smoothstep(t))), car)
    for wheel in wheels:
        scene.add(Rotate3DAnimation(angle=-2160, axis=(0.0, 1.0, 0.0), start_time=drive_start, duration=drive_duration, easing_fun=smoothstep), wheel)

    scene.move_camera(theta=-104, phi=68, zoom=1.18, frame_center=(-1.0, 0.0, 0.62), start_time=0.0, duration=2.6)
    scene.move_camera(theta=-92, phi=64, zoom=1.24, frame_center=(3.8, 0.0, 0.64), start_time=2.6, duration=3.5)
    return scene


def main() -> None:
    output_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "output")
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "three_d_demo.mp4")
    print(f"Rendering moving car demo to {output_path}...")
    build_scene().render(output_path, max_length=7.4)


if __name__ == "__main__":
    main()