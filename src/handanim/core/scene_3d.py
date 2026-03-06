from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import numpy as np

from ..animations.three_d import (
    AmbientCameraRotationAnimation,
    CameraAnimation3D,
    IllusionCameraRotationAnimation,
    MoveCameraAnimation,
)
from .draw_ops import OpsSet
from .scene import Scene
from .viewport import Viewport
from .camera_3d import ThreeDCamera
from .drawable import Drawable


FixedOrientationCenterFunc = Callable[..., tuple[float, float, float] | np.ndarray]


@dataclass
class FixedOrientationConfig:
    point: tuple[float, float, float] | None = None
    center_func: FixedOrientationCenterFunc | None = None
    use_static_center_func: bool = False
    static_point: tuple[float, float, float] | None = None


class ThreeDScene(Scene):
    def __init__(
        self,
        width: int = 1280,
        height: int = 720,
        fps: int = 24,
        background_color: tuple[float, float, float] = (1, 1, 1),
        viewport: Viewport | None = None,
        camera: ThreeDCamera | None = None,
    ) -> None:
        if viewport is None:
            world_y_radius = 4.0
            aspect_ratio = width / height
            viewport = Viewport(
                world_xrange=(-world_y_radius * aspect_ratio, world_y_radius * aspect_ratio),
                world_yrange=(-world_y_radius, world_y_radius),
                screen_width=width,
                screen_height=height,
                margin=20,
            )
        super().__init__(width=width, height=height, fps=fps, background_color=background_color, viewport=viewport)
        self.camera = camera.copy() if camera is not None else ThreeDCamera()
        self.camera_animations: list[CameraAnimation3D] = []
        self.fixed_in_frame_ids: set[str] = set()
        self.fixed_orientation_configs: dict[str, FixedOrientationConfig] = {}
        self.default_angled_camera_orientation_kwargs = {"phi": 70.0, "theta": -135.0}

    def add_mobjects(self, *drawables: Drawable, start_time: float = 0.0, end_time: float | None = None) -> None:
        for drawable in drawables:
            self.drawable_cache.set_drawable_opsset(drawable)
            self.drawable_cache.drawables[drawable.id] = drawable
            timeline = [float(start_time)]
            if end_time is not None:
                timeline.append(float(end_time))
            self.object_timelines[drawable.id] = timeline

    def add_fixed_in_frame_mobjects(self, *drawables: Drawable) -> None:
        self.add_mobjects(*drawables, start_time=0.0)
        for drawable in drawables:
            self.fixed_in_frame_ids.add(drawable.id)

    def add_fixed_orientation_mobjects(
        self,
        *drawables: Drawable,
        point: tuple[float, float, float] | None = None,
        points: list[tuple[float, float, float]] | None = None,
        center_func: FixedOrientationCenterFunc | None = None,
        use_static_center_func: bool = False,
    ) -> None:
        if points is not None and len(points) != len(drawables):
            msg = "Length of points must match number of drawables"
            raise ValueError(msg)
        self.add_mobjects(*drawables, start_time=0.0)
        for index, drawable in enumerate(drawables):
            config = FixedOrientationConfig(
                point=point if points is None else points[index],
                center_func=center_func,
                use_static_center_func=use_static_center_func,
            )
            if use_static_center_func:
                config.static_point = self._resolve_fixed_orientation_point(drawable, 0.0, config)
            self.fixed_orientation_configs[drawable.id] = config

    def remove_fixed_orientation_mobjects(self, *drawables: Drawable) -> None:
        for drawable in drawables:
            self.fixed_orientation_configs.pop(drawable.id, None)

    def remove_fixed_in_frame_mobjects(self, *drawables: Drawable) -> None:
        for drawable in drawables:
            self.fixed_in_frame_ids.discard(drawable.id)

    def set_camera_orientation(
        self,
        phi: float | None = None,
        theta: float | None = None,
        gamma: float | None = None,
        zoom: float | None = None,
        focal_distance: float | None = None,
        frame_center: tuple[float, float, float] | None = None,
    ) -> None:
        if phi is not None:
            self.camera.phi = float(phi)
        if theta is not None:
            self.camera.theta = float(theta)
        if gamma is not None:
            self.camera.gamma = float(gamma)
        if zoom is not None:
            self.camera.zoom = float(zoom)
        if focal_distance is not None:
            self.camera.focal_distance = float(focal_distance)
        if frame_center is not None:
            self.camera.frame_center = np.array(frame_center, dtype=float)
        for animation in self.camera_animations:
            animation._start_state = None

    def add_camera_animation(self, animation: CameraAnimation3D) -> None:
        self.camera_animations.append(animation)
        self.camera_animations.sort(key=lambda item: item.start_time)
        for existing_animation in self.camera_animations:
            existing_animation._start_state = None

    def set_to_default_angled_camera_orientation(self, **kwargs) -> None:
        config = dict(self.default_angled_camera_orientation_kwargs)
        config.update(kwargs)
        self.set_camera_orientation(**config)

    def set_camera_to_default_position(self) -> None:
        self.set_to_default_angled_camera_orientation()

    def get_default_camera_position(self) -> dict[str, float]:
        return dict(self.default_angled_camera_orientation_kwargs)

    def move_camera(self, start_time: float = 0.0, duration: float = 0.0, **kwargs) -> MoveCameraAnimation:
        animation = MoveCameraAnimation(start_time=start_time, duration=duration, **kwargs)
        self.add_camera_animation(animation)
        return animation

    def begin_ambient_camera_rotation(
        self,
        rate: float = 15.0,
        about: str = "theta",
        start_time: float = 0.0,
        duration: float | None = None,
    ) -> AmbientCameraRotationAnimation:
        animation = AmbientCameraRotationAnimation(start_time=start_time, duration=duration, about=about, rate=rate)
        self.add_camera_animation(animation)
        return animation

    def begin_3dillusion_camera_rotation(
        self,
        rate: float = 1.0,
        origin_phi: float | None = None,
        origin_theta: float | None = None,
        start_time: float = 0.0,
        duration: float | None = None,
    ) -> IllusionCameraRotationAnimation:
        animation = IllusionCameraRotationAnimation(
            start_time=start_time,
            duration=duration,
            rate=rate,
            origin_phi=origin_phi,
            origin_theta=origin_theta,
        )
        self.add_camera_animation(animation)
        return animation

    def stop_ambient_camera_rotation(self, stop_time: float, about: str = "theta") -> None:
        for animation in reversed(self.camera_animations):
            if isinstance(animation, AmbientCameraRotationAnimation) and animation.about == about:
                animation.duration = float(stop_time) - animation.start_time
                return
        msg = f"No ambient camera rotation found for axis '{about}'"
        raise ValueError(msg)

    def stop_3dillusion_camera_rotation(self, stop_time: float) -> None:
        for animation in reversed(self.camera_animations):
            if isinstance(animation, IllusionCameraRotationAnimation):
                animation.duration = float(stop_time) - animation.start_time
                return
        msg = "No 3D illusion camera rotation found"
        raise ValueError(msg)

    def get_camera_at_time(self, scene_time: float) -> ThreeDCamera:
        camera = self.camera.copy()
        for index, animation in enumerate(self.camera_animations):
            if animation._start_state is None:
                start_camera = self.camera.copy()
                for previous_animation in self.camera_animations[:index]:
                    if previous_animation.has_started(animation.start_time):
                        start_camera = previous_animation.apply_at_time(start_camera, animation.start_time)
                animation._start_state = start_camera.copy()
            if not animation.has_started(scene_time):
                continue
            camera = animation.apply_at_time(camera, scene_time)
        return camera

    def project_point(
        self,
        point: tuple[float, float, float] | np.ndarray,
        scene_time: float = 0.0,
        camera: ThreeDCamera | None = None,
    ) -> tuple[float, float]:
        point_array = np.array([point], dtype=float)
        active_camera = camera if camera is not None else self.get_camera_at_time(scene_time)
        projected, _depths, _camera_points = active_camera.project_points(point_array)
        return (float(projected[0][0]), float(projected[0][1]))

    def _resolve_fixed_orientation_point(
        self,
        drawable: Drawable,
        scene_time: float,
        config: FixedOrientationConfig,
    ) -> tuple[float, float, float]:
        if config.static_point is not None:
            return (
                float(config.static_point[0]),
                float(config.static_point[1]),
                float(config.static_point[2]),
            )
        if config.point is not None:
            return (
                float(config.point[0]),
                float(config.point[1]),
                float(config.point[2]),
            )
        center_func = config.center_func
        if center_func is not None:
            try:
                value = center_func(drawable, scene_time)
            except TypeError:
                try:
                    value = center_func(drawable)
                except TypeError:
                    value = center_func()
            point_array = np.asarray(value, dtype=float)
            return (float(point_array[0]), float(point_array[1]), float(point_array[2]))
        msg = "Fixed orientation mobjects require point, points, or center_func"
        raise ValueError(msg)

    def _get_fixed_orientation_opsset_at_time(
        self,
        drawable_id: str,
        scene_time: float,
        event_and_progress,
        camera: ThreeDCamera,
    ) -> OpsSet:
        drawable = self.drawable_cache.get_drawable(drawable_id)
        opsset = self.drawable_cache.get_drawable_opsset(drawable_id).clone()
        for event, progress in event_and_progress:
            opsset = event.apply(opsset, progress)
        config = self.fixed_orientation_configs[drawable_id]
        point3d = self._resolve_fixed_orientation_point(drawable, scene_time, config)
        projected_screen_point = self.viewport.world_to_screen(
            self.project_point(point3d, scene_time=scene_time, camera=camera)
        )
        center_x, center_y = opsset.get_center_of_gravity()
        opsset.translate(projected_screen_point[0] - center_x, projected_screen_point[1] - center_y)
        opsset.transform_points(lambda point: self.viewport.screen_to_world(point))
        return opsset

    def _get_fixed_in_frame_opsset_at_time(self, drawable_id: str, event_and_progress) -> OpsSet:
        opsset = self.drawable_cache.get_drawable_opsset(drawable_id).clone()
        for event, progress in event_and_progress:
            opsset = event.apply(opsset, progress)
        opsset.transform_points(lambda point: self.viewport.screen_to_world(point))
        return opsset

    def _is_three_d_drawable(
        self,
        drawable_id: str,
        event_and_progress,
    ) -> bool:
        initial_ops = self.drawable_cache.get_drawable_opsset(drawable_id)
        return initial_ops.has_3d_ops() or any(
            getattr(event, "apply_stage", "post_projection") == "pre_projection"
            for event, _progress in event_and_progress
        )

    def _get_three_d_animated_opsset_at_time(self, drawable_id: str, event_and_progress, camera: ThreeDCamera) -> OpsSet:
        raw_opsset = self.drawable_cache.get_drawable_opsset(drawable_id).clone()
        post_projection_events = []
        for event, progress in event_and_progress:
            stage = getattr(event, "apply_stage", "post_projection")
            if stage == "pre_projection":
                raw_opsset = event.apply(raw_opsset, progress)
            else:
                post_projection_events.append((event, progress))

        projected_opsset = raw_opsset if drawable_id in self.fixed_in_frame_ids else raw_opsset.project_3d(camera)
        for event, progress in post_projection_events:
            projected_opsset = event.apply(projected_opsset, progress)
        return projected_opsset

    def get_drawable_opsset_at_scene_time(self, drawable_id: str, scene_time: float) -> OpsSet:
        if drawable_id not in self.drawable_cache.drawables:
            return OpsSet(initial_set=[])
        _key_frames, drawable_events_mapping = self.find_key_frames()
        frame_index = int(round(scene_time * self.fps))
        event_and_progress = self.get_object_event_and_progress(drawable_id, frame_index, drawable_events_mapping)
        self.drawablegroup_frame_cache = {}
        self.drawablegroup_transformed_frame_cache = {}
        if drawable_id in self.fixed_in_frame_ids:
            return self._get_fixed_in_frame_opsset_at_time(drawable_id, event_and_progress)
        if drawable_id in self.fixed_orientation_configs:
            return self._get_fixed_orientation_opsset_at_time(
                drawable_id=drawable_id,
                scene_time=scene_time,
                event_and_progress=event_and_progress,
                camera=self.get_camera_at_time(scene_time),
            )
        if self._is_three_d_drawable(drawable_id, event_and_progress):
            return self._get_three_d_animated_opsset_at_time(
                drawable_id=drawable_id,
                event_and_progress=event_and_progress,
                camera=self.get_camera_at_time(scene_time),
            )
        return super().get_animated_opsset_at_time(
            drawable_id=drawable_id,
            t=frame_index,
            event_and_progress=event_and_progress,
            drawable_events_mapping=drawable_events_mapping,
        )

    def _infer_default_length(self) -> float:
        event_end_times = [event.end_time for event, _drawable_id in self.events]
        camera_end_times = []
        for animation in self.camera_animations:
            if animation.duration is not None:
                camera_end_times.append(animation.start_time + animation.duration)
        candidates = event_end_times + camera_end_times
        return max(candidates) if candidates else 1.0 / self.fps

    def _extend_with_depth_sorted_chunks(
        self,
        target_opsset: OpsSet,
        opsset: OpsSet,
        depth_entries: list[tuple[float, OpsSet]],
    ) -> None:
        for depth_value, chunk_opsset in opsset.get_meta_chunks("depth_3d"):
            if depth_value is None:
                target_opsset.extend(chunk_opsset)
            else:
                depth_entries.append((float(depth_value), chunk_opsset))

    def create_event_timeline(self, max_length: float | None = None):
        if max_length is None:
            max_length = self._infer_default_length()

        _key_frames, drawable_events_mapping = self.find_key_frames()
        total_frames = max(1, int(np.ceil(max_length * self.fps)))
        scene_opsset_list = []

        for frame_index in range(total_frames):
            scene_time = frame_index / self.fps
            active_objects = self.get_active_objects(scene_time)
            frame_opsset = OpsSet(initial_set=[])
            fixed_frame_opsset = OpsSet(initial_set=[])
            depth_entries: list[tuple[float, OpsSet]] = []
            self.drawablegroup_frame_cache = {}
            self.drawablegroup_transformed_frame_cache = {}
            camera = self.get_camera_at_time(scene_time)

            for object_id in active_objects:
                event_and_progress = self.get_object_event_and_progress(object_id, frame_index, drawable_events_mapping)
                if object_id in self.fixed_in_frame_ids:
                    opsset = self._get_fixed_in_frame_opsset_at_time(object_id, event_and_progress)
                elif object_id in self.fixed_orientation_configs:
                    opsset = self._get_fixed_orientation_opsset_at_time(object_id, scene_time, event_and_progress, camera)
                elif self._is_three_d_drawable(object_id, event_and_progress):
                    opsset = self._get_three_d_animated_opsset_at_time(object_id, event_and_progress, camera)
                else:
                    opsset = super().get_animated_opsset_at_time(
                        drawable_id=object_id,
                        t=frame_index,
                        event_and_progress=event_and_progress,
                        drawable_events_mapping=drawable_events_mapping,
                    )
                if object_id in self.fixed_in_frame_ids:
                    fixed_frame_opsset.extend(opsset)
                elif self._is_three_d_drawable(object_id, event_and_progress):
                    self._extend_with_depth_sorted_chunks(frame_opsset, opsset, depth_entries)
                else:
                    frame_opsset.extend(opsset)

            for _depth, chunk_opsset in sorted(depth_entries, key=lambda item: item[0]):
                frame_opsset.extend(chunk_opsset)
            frame_opsset.extend(fixed_frame_opsset)
            scene_opsset_list.append(frame_opsset)
        return scene_opsset_list


class SpecialThreeDScene(ThreeDScene):
    def __init__(
        self,
        sphere_config: dict | None = None,
        three_d_axes_config: dict | None = None,
        default_angled_camera_position: dict | None = None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.sphere_config = sphere_config or {"radius": 1.5, "resolution": (20, 20)}
        self.three_d_axes_config = three_d_axes_config or {}
        self.default_angled_camera_orientation_kwargs = default_angled_camera_position or {"phi": 70.0, "theta": -110.0}

    def get_axes(self):
        from ..primitives import ThreeDAxes

        return ThreeDAxes(**self.three_d_axes_config)

    def get_sphere(self, **kwargs):
        from ..primitives import Sphere

        config = dict(self.sphere_config)
        config.update(kwargs)
        return Sphere(**config)