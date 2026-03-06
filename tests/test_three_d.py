import numpy as np
import importlib.util
from pathlib import Path

import handanim
from handanim.animations import IllusionCameraRotationAnimation, MoveCameraAnimation, Rotate3DAnimation, SketchAnimation
from handanim.core import SpecialThreeDScene, ThreeDCamera, ThreeDScene
from handanim.core.styles import FillStyle, StrokeStyle
from handanim.primitives import Cube, Line3D, Sphere, Surface, Text, ThreeDAxes


def test_top_level_exports_three_d_symbols():
    assert hasattr(handanim, "ThreeDScene")
    assert hasattr(handanim, "ThreeDCamera")
    assert hasattr(handanim, "SpecialThreeDScene")
    assert hasattr(handanim, "Sphere")
    assert hasattr(handanim, "Cube")
    assert hasattr(handanim, "ThreeDAxes")
    assert hasattr(handanim, "Surface")


def test_three_d_camera_projection_scales_with_depth():
    camera = ThreeDCamera(phi=0, theta=0, gamma=0, focal_distance=20, zoom=1)
    projected, _depths, _camera_points = camera.project_points(np.array([[1.0, 0.0, 0.0], [1.0, 0.0, 5.0]]))
    assert projected[1][0] > projected[0][0]


def test_three_d_camera_projects_positive_z_upward_on_screen():
    camera = ThreeDCamera(phi=72, theta=-98, gamma=0, focal_distance=20, zoom=1)
    projected, _depths, _camera_points = camera.project_points(np.array([[0.0, 0.0, 0.0], [0.0, 0.0, 1.0], [0.0, 0.0, -1.0]]))

    assert projected[1][1] < projected[0][1]
    assert projected[2][1] > projected[0][1]


def test_three_d_primitives_emit_three_d_ops():
    cube = Cube(
        side_length=2.0,
        stroke_style=StrokeStyle(color=(0, 0, 0), width=1),
        fill_style=FillStyle(color=(0.5, 0.7, 0.9), opacity=0.7),
    )
    sphere = Sphere(
        radius=1.0,
        stroke_style=StrokeStyle(color=(0, 0, 0), width=1),
        fill_style=FillStyle(color=(0.9, 0.5, 0.4), opacity=0.7),
    )
    assert cube.draw().has_3d_ops()
    assert sphere.draw().has_3d_ops()


def test_three_d_axes_coords_to_point_mapping():
    axes = ThreeDAxes(x_range=(-2, 2, 1), y_range=(-1, 1, 1), z_range=(-2, 2, 1), x_length=8, y_length=4, z_length=8)
    point = axes.c2p(1, -1, -2)
    assert np.allclose(point, np.array([2.0, -2.0, -4.0]))


def test_three_d_scene_camera_motion_changes_projection():
    scene = ThreeDScene(width=640, height=360, fps=24)
    line = Line3D((0, 0, 0), (2, 0, 0), stroke_style=StrokeStyle(color=(0, 0, 0), width=1.5))
    scene.add_mobjects(line)
    scene.add_camera_animation(MoveCameraAnimation(theta=-45, start_time=0.0, duration=1.0))

    start_ops = scene.get_drawable_opsset_at_scene_time(line.id, 0.0)
    end_ops = scene.get_drawable_opsset_at_scene_time(line.id, 1.0)

    assert start_ops.get_bbox() != end_ops.get_bbox()


def test_three_d_rotation_animation_applies_before_projection():
    scene = ThreeDScene(width=640, height=360, fps=24)
    line = Line3D((-1, 0, 0), (1, 0, 0), stroke_style=StrokeStyle(color=(0, 0, 0), width=1.5))
    scene.add_mobjects(line)
    scene.add(Rotate3DAnimation(angle=90, axis=(0, 1, 0), start_time=0.0, duration=1.0), line)

    start_width = scene.get_drawable_opsset_at_scene_time(line.id, 0.0).get_bbox()[2] - scene.get_drawable_opsset_at_scene_time(line.id, 0.0).get_bbox()[0]
    end_width = scene.get_drawable_opsset_at_scene_time(line.id, 1.0).get_bbox()[2] - scene.get_drawable_opsset_at_scene_time(line.id, 1.0).get_bbox()[0]

    assert end_width < start_width


def test_three_d_sketch_animation_runs_post_projection():
    scene = ThreeDScene(width=640, height=360, fps=24)
    cube = Cube(side_length=2.0, stroke_style=StrokeStyle(color=(0, 0, 0), width=1.0))
    scene.add(SketchAnimation(start_time=0.0, duration=1.0), cube)

    mid_ops = scene.get_drawable_opsset_at_scene_time(cube.id, 0.5)
    end_ops = scene.get_drawable_opsset_at_scene_time(cube.id, 1.0)

    assert len(mid_ops.opsset) > 0
    assert len(end_ops.opsset) >= len(mid_ops.opsset)


def test_fixed_orientation_mobject_tracks_projected_anchor():
    scene = ThreeDScene(width=640, height=360, fps=24)
    label = Text("P", position=(0, 0), font_size=24, stroke_style=StrokeStyle(color=(0, 0, 0), width=1.2))
    scene.add_fixed_orientation_mobjects(label, point=(2.0, 0.0, 0.0))
    scene.move_camera(theta=-45, start_time=0.0, duration=1.0)

    start_bbox = scene.get_drawable_opsset_at_scene_time(label.id, 0.0).get_bbox()
    end_bbox = scene.get_drawable_opsset_at_scene_time(label.id, 1.0).get_bbox()

    assert start_bbox != end_bbox


def test_fixed_in_frame_mobject_stays_in_screen_space():
    scene = ThreeDScene(width=640, height=360, fps=24)
    title = Text("Title", position=(320, 60), font_size=24, stroke_style=StrokeStyle(color=(0, 0, 0), width=1.2))
    scene.add_fixed_in_frame_mobjects(title)

    opsset = scene.get_drawable_opsset_at_scene_time(title.id, 0.0)
    bbox = opsset.get_bbox()
    center = ((bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2)
    screen_center = scene.viewport.world_to_screen(center)

    assert abs(screen_center[0] - 320) < 80
    assert abs(screen_center[1] - 60) < 80


def test_three_d_viewport_handles_signed_world_coordinates():
    scene = ThreeDScene(width=640, height=360, fps=24)
    screen_point = scene.viewport.world_to_screen((0.0, 0.0))

    assert 0 < screen_point[0] < scene.width
    assert 0 < screen_point[1] < scene.height


def test_illusion_camera_rotation_changes_camera_over_time():
    scene = ThreeDScene(width=640, height=360, fps=24)
    scene.begin_3dillusion_camera_rotation(rate=1.0, start_time=0.0, duration=2.0)
    start_camera = scene.get_camera_at_time(0.0)
    mid_camera = scene.get_camera_at_time(1.0)

    assert isinstance(scene.camera_animations[-1], IllusionCameraRotationAnimation)
    assert (start_camera.theta, start_camera.phi) != (mid_camera.theta, mid_camera.phi)


def test_special_three_d_scene_helpers_and_surface_alias():
    scene = SpecialThreeDScene()
    scene.set_camera_to_default_position()
    axes = scene.get_axes()
    sphere = scene.get_sphere()
    surface = Surface(lambda u, v: (u, v, u * v), u_range=(-1, 1), v_range=(-1, 1), resolution=(4, 4))

    assert axes.draw().has_3d_ops()
    assert sphere.draw().has_3d_ops()
    assert surface.draw().has_3d_ops()
    assert scene.get_default_camera_position()["theta"] == -110.0


def test_camera_animation_state_is_deterministic_for_out_of_order_queries():
    scene = ThreeDScene(width=640, height=360, fps=24)
    scene.move_camera(theta=-45, start_time=0.0, duration=2.0)
    scene.move_camera(phi=55, start_time=1.0, duration=2.0)

    late_camera = scene.get_camera_at_time(2.5)
    early_camera = scene.get_camera_at_time(0.5)
    repeated_late_camera = scene.get_camera_at_time(2.5)

    assert early_camera.theta != late_camera.theta
    assert (late_camera.theta, late_camera.phi) == (repeated_late_camera.theta, repeated_late_camera.phi)


def test_near_plane_clipping_keeps_partially_visible_polyline():
    camera = ThreeDCamera(phi=0, theta=0, gamma=0, focal_distance=20, zoom=1)
    line = Line3D((1.0, 0.0, 0.0), (1.0, 0.0, 25.0), stroke_style=StrokeStyle(color=(0, 0, 0), width=1.0))

    projected = line.draw().project_3d(camera)

    assert len(projected.opsset) > 0


def test_backface_culling_reduces_visible_cube_faces():
    camera = ThreeDCamera()
    cube = Cube(
        side_length=2.0,
        stroke_style=StrokeStyle(color=(0, 0, 0), width=1.0),
        fill_style=FillStyle(color=(0.5, 0.7, 0.9), opacity=0.7),
    )

    projected = cube.draw().project_3d(camera)
    fill_ops = [ops for ops in projected.opsset if ops.type.value == "set_pen" and ops.data.get("mode") == "fill"]

    assert 1 <= len(fill_ops) < 6


def test_closed_shapes_default_to_backface_culling():
    sphere = Sphere(radius=1.0)
    surface = Surface(lambda u, v: (u, v, u * v), u_range=(-1, 1), v_range=(-1, 1), resolution=(2, 2))

    sphere_first_face = sphere.draw().opsset[0]
    surface_first_face = surface.draw().opsset[0]

    assert sphere_first_face.data["backface_cull"] is True
    assert surface_first_face.data["backface_cull"] is False


def test_three_d_scene_sorts_depth_across_multiple_objects():
    scene = ThreeDScene(width=640, height=360, fps=24)
    back_cube = Cube(
        side_length=1.5,
        center=(0.0, 0.0, -1.5),
        stroke_style=StrokeStyle(color=(0, 0, 0), width=0.5),
        fill_style=FillStyle(color=(0.7, 0.7, 0.9), opacity=0.8),
    )
    front_cube = Cube(
        side_length=1.5,
        center=(0.0, 0.0, 1.5),
        stroke_style=StrokeStyle(color=(0, 0, 0), width=0.5),
        fill_style=FillStyle(color=(0.9, 0.6, 0.6), opacity=0.8),
    )
    scene.add_mobjects(back_cube, front_cube)

    frame_opsset = scene.create_event_timeline(max_length=1 / scene.fps)[0]
    depth_values = [depth for depth, _chunk in frame_opsset.get_meta_chunks("depth_3d") if depth is not None]

    assert depth_values == sorted(depth_values)


def test_three_d_demo_build_scene_creates_timeline():
    example_path = Path("examples/three_d_demo.py")
    spec = importlib.util.spec_from_file_location("three_d_demo", example_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    scene = module.build_scene()
    timeline = scene.create_event_timeline(max_length=0.4)

    assert len(timeline) > 0