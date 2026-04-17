from __future__ import annotations

import math
from typing import Callable

import numpy as np

from handanim.core.animation import AnimationEvent, AnimationEventType
from handanim.core.draw_ops import OpsSet


class RotateAnimation(AnimationEvent):
    """
    A class representing a rotation animation event.

    This animation rotates an OpsSet around a specified point (default: center of gravity)
    by a given angle over the course of the animation's duration.

    Args:
        angle (float): The total angle to rotate in radians. Positive is clockwise.
        center (tuple[float, float] | None): The point to rotate around. If None, uses center of gravity.
        start_time (float, optional): The start time of the animation. Defaults to 0.
        duration (float, optional): The duration of the animation. Defaults to 0.
        easing_fun (callable, optional): An optional easing function to modify animation progress. Defaults to None.
        data (dict, optional): Additional data associated with the animation. Defaults to None.
    """

    def __init__(
        self,
        angle: float,
        center: tuple[float, float] | None = None,
        start_time: float = 0.0,
        duration: float = 0.0,
        easing_fun: Callable[[float], float] | None = None,
        data: dict | None = None,
    ) -> None:
        super().__init__(AnimationEventType.MUTATION, start_time, duration, easing_fun, data)
        self.angle = angle
        self.center = center

    def _rotate_point(self, point: tuple[float, float], center: tuple[float, float], angle: float) -> tuple[float, float]:
        """Rotate a point around a center by a given angle."""
        px, py = point
        cx, cy = center
        
        # Translate point to origin relative to center
        translated_x = px - cx
        translated_y = py - cy
        
        # Rotate
        cos_theta = math.cos(angle)
        sin_theta = math.sin(angle)
        rotated_x = translated_x * cos_theta - translated_y * sin_theta
        rotated_y = translated_x * sin_theta + translated_y * cos_theta
        
        # Translate back
        return (rotated_x + cx, rotated_y + cy)

    def apply(self, opsset: OpsSet, progress: float) -> OpsSet:
        if self.easing_fun is not None:
            progress = float(self.easing_fun(progress))
        
        current_angle = self.angle * progress
        center = self.center if self.center is not None else opsset.get_center_of_gravity()
        
        new_opsset = opsset.clone()
        new_opsset.transform_points(lambda point: self._rotate_point(point, center, current_angle))
        return new_opsset


class SpinAnimation(RotateAnimation):
    """
    A class representing a spin animation that rotates continuously.

    This is a convenience wrapper around RotateAnimation for spinning effects.

    Args:
        rotations (float): Number of full rotations to perform.
        center (tuple[float, float] | None): The point to rotate around. If None, uses center of gravity.
        start_time (float, optional): The start time of the animation. Defaults to 0.
        duration (float, optional): The duration of the animation. Defaults to 0.
        easing_fun (callable, optional): An optional easing function to modify animation progress. Defaults to None.
        data (dict, optional): Additional data associated with the animation. Defaults to None.
    """

    def __init__(
        self,
        rotations: float = 1.0,
        center: tuple[float, float] | None = None,
        start_time: float = 0.0,
        duration: float = 0.0,
        easing_fun: Callable[[float], float] | None = None,
        data: dict | None = None,
    ) -> None:
        angle = rotations * 2 * math.pi
        super().__init__(angle, center, start_time, duration, easing_fun, data)


__all__ = ["RotateAnimation", "SpinAnimation"]
