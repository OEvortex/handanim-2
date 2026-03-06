from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..core.animation import AnimationEvent, AnimationEventType
from ..core.camera_3d import ThreeDCamera
from ..core.draw_ops import OpsSet


def _resolve_progress(progress: float, easing_fun=None) -> float:
    progress = float(np.clip(progress, 0.0, 1.0))
    if callable(easing_fun):
        return float(easing_fun(progress))
    return progress


class ThreeDTransformAnimation(AnimationEvent):
    apply_stage = "pre_projection"


class Translate3DAnimation(ThreeDTransformAnimation):
    def __init__(self, offset: tuple[float, float, float], start_time=0.0, duration=0.0, easing_fun=None):
        super().__init__(AnimationEventType.MUTATION, start_time, duration, easing_fun, data={"offset": offset})

    def apply(self, opsset: OpsSet, progress: float) -> OpsSet:
        eased = _resolve_progress(progress, self.easing_fun)
        output = opsset.clone()
        dx, dy, dz = self.data["offset"]
        output.translate_3d(dx * eased, dy * eased, dz * eased)
        return output


class Scale3DAnimation(ThreeDTransformAnimation):
    def __init__(
        self,
        scale_x: float,
        scale_y: float | None = None,
        scale_z: float | None = None,
        start_time=0.0,
        duration=0.0,
        easing_fun=None,
        center_of_scaling: tuple[float, float, float] | None = None,
    ):
        super().__init__(
            AnimationEventType.MUTATION,
            start_time,
            duration,
            easing_fun,
            data={
                "scale_x": scale_x,
                "scale_y": scale_y,
                "scale_z": scale_z,
                "center_of_scaling": center_of_scaling,
            },
        )

    def apply(self, opsset: OpsSet, progress: float) -> OpsSet:
        eased = _resolve_progress(progress, self.easing_fun)
        sx = 1.0 + (float(self.data["scale_x"]) - 1.0) * eased
        raw_sy = self.data["scale_y"]
        raw_sz = self.data["scale_z"]
        sy = 1.0 + ((float(raw_sy) if raw_sy is not None else float(self.data["scale_x"])) - 1.0) * eased
        sz = 1.0 + ((float(raw_sz) if raw_sz is not None else float(self.data["scale_x"])) - 1.0) * eased
        output = opsset.clone()
        output.scale_3d(sx, sy, sz, center_of_scaling=self.data["center_of_scaling"])
        return output


class Rotate3DAnimation(ThreeDTransformAnimation):
    def __init__(
        self,
        angle: float,
        axis: tuple[float, float, float] = (0.0, 0.0, 1.0),
        start_time=0.0,
        duration=0.0,
        easing_fun=None,
        center_of_rotation: tuple[float, float, float] | None = None,
    ):
        super().__init__(
            AnimationEventType.MUTATION,
            start_time,
            duration,
            easing_fun,
            data={
                "angle": angle,
                "axis": axis,
                "center_of_rotation": center_of_rotation,
            },
        )

    def apply(self, opsset: OpsSet, progress: float) -> OpsSet:
        eased = _resolve_progress(progress, self.easing_fun)
        output = opsset.clone()
        output.rotate_3d(
            angle=float(self.data["angle"]) * eased,
            axis=self.data["axis"],
            center_of_rotation=self.data["center_of_rotation"],
        )
        return output


class MoveTo3DAnimation(ThreeDTransformAnimation):
    def __init__(self, target: tuple[float, float, float], start_time=0.0, duration=0.0, easing_fun=None):
        super().__init__(AnimationEventType.MUTATION, start_time, duration, easing_fun, data={"target": target})

    def apply(self, opsset: OpsSet, progress: float) -> OpsSet:
        eased = _resolve_progress(progress, self.easing_fun)
        output = opsset.clone()
        start_center = np.array(output.get_center_of_gravity_3d(), dtype=float)
        target = np.array(self.data["target"], dtype=float)
        destination = start_center + (target - start_center) * eased
        output.move_to_3d(destination)
        return output


@dataclass
class CameraAnimation3D:
    start_time: float = 0.0
    duration: float | None = 0.0
    _start_state: ThreeDCamera | None = None

    def bind_start_state(self, camera: ThreeDCamera) -> None:
        if self._start_state is None:
            self._start_state = camera.copy()

    def progress_at_time(self, scene_time: float) -> float:
        if self.duration is None or self.duration <= 0:
            return 1.0
        return float(np.clip((scene_time - self.start_time) / self.duration, 0.0, 1.0))

    def has_started(self, scene_time: float) -> bool:
        return scene_time >= self.start_time

    def apply_at_time(self, camera: ThreeDCamera, scene_time: float) -> ThreeDCamera:
        raise NotImplementedError


@dataclass
class MoveCameraAnimation(CameraAnimation3D):
    phi: float | None = None
    theta: float | None = None
    gamma: float | None = None
    zoom: float | None = None
    focal_distance: float | None = None
    frame_center: tuple[float, float, float] | None = None

    def apply_at_time(self, camera: ThreeDCamera, scene_time: float) -> ThreeDCamera:
        self.bind_start_state(camera)
        start = self._start_state or camera
        progress = self.progress_at_time(scene_time)
        output = camera.copy()

        def lerp(current, target):
            return float(current + (target - current) * progress)

        if self.phi is not None:
            output.phi = lerp(start.phi, self.phi)
        if self.theta is not None:
            output.theta = lerp(start.theta, self.theta)
        if self.gamma is not None:
            output.gamma = lerp(start.gamma, self.gamma)
        if self.zoom is not None:
            output.zoom = lerp(start.zoom, self.zoom)
        if self.focal_distance is not None:
            output.focal_distance = lerp(start.focal_distance, self.focal_distance)
        if self.frame_center is not None:
            target_center = np.array(self.frame_center, dtype=float)
            output.frame_center = start.frame_center + (target_center - start.frame_center) * progress
        return output


@dataclass
class AmbientCameraRotationAnimation(CameraAnimation3D):
    about: str = "theta"
    rate: float = 15.0
    duration: float | None = None

    def apply_at_time(self, camera: ThreeDCamera, scene_time: float) -> ThreeDCamera:
        self.bind_start_state(camera)
        start = self._start_state or camera
        output = camera.copy()
        elapsed = max(scene_time - self.start_time, 0.0)
        if self.duration is not None:
            elapsed = min(elapsed, self.duration)
        value = getattr(start, self.about) + self.rate * elapsed
        setattr(output, self.about, value)
        return output


@dataclass
class IllusionCameraRotationAnimation(CameraAnimation3D):
    rate: float = 1.0
    origin_phi: float | None = None
    origin_theta: float | None = None
    theta_amplitude: float = 11.459155902616466
    phi_amplitude: float = 5.729577951308233

    def apply_at_time(self, camera: ThreeDCamera, scene_time: float) -> ThreeDCamera:
        self.bind_start_state(camera)
        start = self._start_state or camera
        output = camera.copy()
        elapsed = max(scene_time - self.start_time, 0.0)
        if self.duration is not None:
            elapsed = min(elapsed, self.duration)
        phase = elapsed * self.rate
        base_theta = start.theta if self.origin_theta is None else self.origin_theta
        base_phi = start.phi if self.origin_phi is None else self.origin_phi
        output.theta = float(base_theta + self.theta_amplitude * np.sin(phase))
        output.phi = float(base_phi + self.phi_amplitude * np.cos(phase) - self.phi_amplitude)
        return output