from __future__ import annotations

from dataclasses import dataclass, field
import math

import numpy as np


def _rotation_about_x(angle_radians: float) -> np.ndarray:
    cos_theta = math.cos(angle_radians)
    sin_theta = math.sin(angle_radians)
    return np.array(
        [
            [1.0, 0.0, 0.0],
            [0.0, cos_theta, -sin_theta],
            [0.0, sin_theta, cos_theta],
        ],
        dtype=float,
    )


def _rotation_about_z(angle_radians: float) -> np.ndarray:
    cos_theta = math.cos(angle_radians)
    sin_theta = math.sin(angle_radians)
    return np.array(
        [
            [cos_theta, -sin_theta, 0.0],
            [sin_theta, cos_theta, 0.0],
            [0.0, 0.0, 1.0],
        ],
        dtype=float,
    )


@dataclass
class ThreeDCamera:
    phi: float = 70.0
    theta: float = -135.0
    gamma: float = 0.0
    zoom: float = 1.0
    focal_distance: float = 20.0
    frame_center: np.ndarray = field(default_factory=lambda: np.zeros(3, dtype=float))
    light_source: np.ndarray = field(default_factory=lambda: np.array([-7.0, -9.0, 10.0], dtype=float))
    shading_factor: float = 0.25
    perspective: bool = True
    exponential_projection: bool = False

    def copy(self) -> "ThreeDCamera":
        return ThreeDCamera(
            phi=float(self.phi),
            theta=float(self.theta),
            gamma=float(self.gamma),
            zoom=float(self.zoom),
            focal_distance=float(self.focal_distance),
            frame_center=np.array(self.frame_center, dtype=float),
            light_source=np.array(self.light_source, dtype=float),
            shading_factor=float(self.shading_factor),
            perspective=bool(self.perspective),
            exponential_projection=bool(self.exponential_projection),
        )

    def set_phi(self, value: float) -> None:
        self.phi = float(value)

    def set_theta(self, value: float) -> None:
        self.theta = float(value)

    def set_gamma(self, value: float) -> None:
        self.gamma = float(value)

    def set_zoom(self, value: float) -> None:
        self.zoom = float(value)

    def set_focal_distance(self, value: float) -> None:
        self.focal_distance = max(float(value), 1e-6)

    def set_frame_center(self, value: tuple[float, float, float] | np.ndarray) -> None:
        self.frame_center = np.array(value, dtype=float)

    def increment_phi(self, delta: float) -> None:
        self.phi += float(delta)

    def increment_theta(self, delta: float) -> None:
        self.theta += float(delta)

    def increment_gamma(self, delta: float) -> None:
        self.gamma += float(delta)

    def get_rotation_matrix(self) -> np.ndarray:
        phi = math.radians(self.phi)
        theta = math.radians(self.theta)
        gamma = math.radians(self.gamma)
        matrices = [
            _rotation_about_z(-theta - math.pi / 2),
            _rotation_about_x(-phi),
            _rotation_about_z(gamma),
        ]
        result = np.identity(3, dtype=float)
        for matrix in matrices:
            result = matrix @ result
        return result

    def transform_points_to_camera_space(self, points: np.ndarray) -> np.ndarray:
        centered = np.asarray(points, dtype=float) - self.frame_center
        return centered @ self.get_rotation_matrix().T

    def get_camera_position(self) -> np.ndarray:
        rotation = self.get_rotation_matrix()
        return self.frame_center + np.array([0.0, 0.0, self.focal_distance], dtype=float) @ rotation

    def project_points(self, points: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        camera_points = self.transform_points_to_camera_space(points)
        projected, depths = self.project_camera_space_points(camera_points)
        return projected, depths, camera_points

    def get_near_clip_epsilon(self) -> float:
        return max(1e-3, 0.01 * float(self.focal_distance))

    def project_camera_space_points(self, camera_points: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        camera_points = np.asarray(camera_points, dtype=float)
        projected = np.array(camera_points[:, :2], dtype=float)
        projected[:, 1] *= -1.0
        depths = np.array(camera_points[:, 2], dtype=float)

        if self.perspective:
            denominator = self.focal_distance - depths
            if self.exponential_projection:
                factor = np.exp(depths / self.focal_distance)
                behind_mask = depths < 0
                factor[behind_mask] = self.focal_distance / np.maximum(denominator[behind_mask], 1e-6)
            else:
                factor = self.focal_distance / np.maximum(denominator, 1e-6)
            projected = projected * factor[:, None]

        projected *= self.zoom
        return projected, depths