from __future__ import annotations

import math
from typing import Callable

import numpy as np

from handanim.core.animation import AnimationEvent, AnimationEventType
from handanim.core.draw_ops import Ops, OpsSet, OpsType


class PulseAnimation(AnimationEvent):
    """
    A class representing a pulse animation event.

    This animation creates a pulsing effect by repeatedly scaling the object up and down.
    It's useful for drawing attention to an element.

    Args:
        scale_min (float): The minimum scale factor. Defaults to 0.8.
        scale_max (float): The maximum scale factor. Defaults to 1.2.
        cycles (float): Number of pulse cycles to complete. Defaults to 1.0.
        start_time (float, optional): The start time of the animation. Defaults to 0.
        duration (float, optional): The duration of the animation. Defaults to 0.
        easing_fun (callable, optional): An optional easing function to modify animation progress. Defaults to None.
        data (dict, optional): Additional data associated with the animation. Defaults to None.
    """

    def __init__(
        self,
        scale_min: float = 0.8,
        scale_max: float = 1.2,
        cycles: float = 1.0,
        start_time: float = 0.0,
        duration: float = 0.0,
        easing_fun: Callable[[float], float] | None = None,
        data: dict | None = None,
    ) -> None:
        super().__init__(AnimationEventType.MUTATION, start_time, duration, easing_fun, data)
        self.scale_min = scale_min
        self.scale_max = scale_max
        self.cycles = cycles

    def apply(self, opsset: OpsSet, progress: float) -> OpsSet:
        if self.easing_fun is not None:
            progress = float(self.easing_fun(progress))
        
        # Create a sine wave for pulsing effect
        angle = 2 * math.pi * self.cycles * progress
        sine_value = (math.sin(angle) + 1) / 2  # Normalize to 0-1
        current_scale = self.scale_min + (self.scale_max - self.scale_min) * sine_value
        
        new_opsset = opsset.clone()
        new_opsset.scale(current_scale, current_scale)
        return new_opsset


class WiggleAnimation(AnimationEvent):
    """
    A class representing a wiggle animation event.

    This animation creates a wiggling effect by rotating the object back and forth.
    It's useful for playful or attention-grabbing effects.

    Args:
        angle (float): The maximum rotation angle in radians. Defaults to 0.1.
        cycles (float): Number of wiggle cycles to complete. Defaults to 1.0.
        start_time (float, optional): The start time of the animation. Defaults to 0.
        duration (float, optional): The duration of the animation. Defaults to 0.
        easing_fun (callable, optional): An optional easing function to modify animation progress. Defaults to None.
        data (dict, optional): Additional data associated with the animation. Defaults to None.
    """

    def __init__(
        self,
        angle: float = 0.1,
        cycles: float = 1.0,
        start_time: float = 0.0,
        duration: float = 0.0,
        easing_fun: Callable[[float], float] | None = None,
        data: dict | None = None,
    ) -> None:
        super().__init__(AnimationEventType.MUTATION, start_time, duration, easing_fun, data)
        self.angle = angle
        self.cycles = cycles

    def _rotate_point(self, point: tuple[float, float], center: tuple[float, float], angle: float) -> tuple[float, float]:
        """Rotate a point around a center by a given angle."""
        px, py = point
        cx, cy = center
        
        translated_x = px - cx
        translated_y = py - cy
        
        cos_theta = math.cos(angle)
        sin_theta = math.sin(angle)
        rotated_x = translated_x * cos_theta - translated_y * sin_theta
        rotated_y = translated_x * sin_theta + translated_y * cos_theta
        
        return (rotated_x + cx, rotated_y + cy)

    def apply(self, opsset: OpsSet, progress: float) -> OpsSet:
        if self.easing_fun is not None:
            progress = float(self.easing_fun(progress))
        
        # Create a sine wave for wiggling effect
        angle = 2 * math.pi * self.cycles * progress
        current_angle = self.angle * math.sin(angle)
        
        center = opsset.get_center_of_gravity()
        new_opsset = opsset.clone()
        new_opsset.transform_points(lambda point: self._rotate_point(point, center, current_angle))
        return new_opsset


class FlashAnimation(AnimationEvent):
    """
    A class representing a flash animation event.

    This animation creates a flashing effect by temporarily changing the color
    and then returning to the original. It's useful for highlighting or emphasis.

    Args:
        flash_color (tuple[float, float, float]): The color to flash to (RGB). Defaults to white (1, 1, 1).
        flash_opacity (float): The opacity of the flash effect. Defaults to 1.0.
        start_time (float, optional): The start time of the animation. Defaults to 0.
        duration (float, optional): The duration of the animation. Defaults to 0.
        easing_fun (callable, optional): An optional easing function to modify animation progress. Defaults to None.
        data (dict, optional): Additional data associated with the animation. Defaults to None.
    """

    def __init__(
        self,
        flash_color: tuple[float, float, float] = (1.0, 1.0, 1.0),
        flash_opacity: float = 1.0,
        start_time: float = 0.0,
        duration: float = 0.0,
        easing_fun: Callable[[float], float] | None = None,
        data: dict | None = None,
    ) -> None:
        super().__init__(AnimationEventType.MUTATION, start_time, duration, easing_fun, data)
        self.flash_color = flash_color
        self.flash_opacity = flash_opacity

    def apply(self, opsset: OpsSet, progress: float) -> OpsSet:
        if self.easing_fun is not None:
            progress = float(self.easing_fun(progress))
        
        # Flash intensity follows a bell curve (flash at 0.5, fade at ends)
        if progress < 0.5:
            intensity = progress * 2
        else:
            intensity = (1 - progress) * 2
        
        current_ops = []
        for op in opsset.opsset:
            if op.type == OpsType.SET_PEN and isinstance(op.data, dict):
                old_color = op.data.get("color", self.flash_color)
                source = np.asarray(old_color, dtype=float)
                target = np.asarray(self.flash_color, dtype=float)
                
                # Blend colors based on flash intensity
                blended = tuple(((1 - intensity) * source + intensity * target).tolist())
                
                data = dict(op.data)
                data["color"] = blended
                current_ops.append(Ops(op.type, data, op.partial, op.meta))
            else:
                current_ops.append(op)
        
        return OpsSet(initial_set=current_ops, has_3d_ops=opsset.has_3d_ops())


class JitterAnimation(AnimationEvent):
    """
    A class representing a jitter animation event.

    This animation creates a jittering effect by randomly moving the object slightly.
    It's useful for creating nervous or energetic effects.

    Args:
        magnitude (float): The maximum jitter distance in pixels. Defaults to 5.0.
        seed (int | None): Random seed for reproducibility. Defaults to None.
        start_time (float, optional): The start time of the animation. Defaults to 0.
        duration (float, optional): The duration of the animation. Defaults to 0.
        easing_fun (callable, optional): An optional easing function to modify animation progress. Defaults to None.
        data (dict, optional): Additional data associated with the animation. Defaults to None.
    """

    def __init__(
        self,
        magnitude: float = 5.0,
        seed: int | None = None,
        start_time: float = 0.0,
        duration: float = 0.0,
        easing_fun: Callable[[float], float] | None = None,
        data: dict | None = None,
    ) -> None:
        super().__init__(AnimationEventType.MUTATION, start_time, duration, easing_fun, data)
        self.magnitude = magnitude
        self.seed = seed
        if seed is not None:
            np.random.seed(seed)

    def apply(self, opsset: OpsSet, progress: float) -> OpsSet:
        if self.easing_fun is not None:
            progress = float(self.easing_fun(progress))
        
        # Jitter intensity follows a bell curve (maximum at 0.5)
        if progress < 0.5:
            intensity = progress * 2
        else:
            intensity = (1 - progress) * 2
        
        dx = (np.random.random() - 0.5) * 2 * self.magnitude * intensity
        dy = (np.random.random() - 0.5) * 2 * self.magnitude * intensity
        
        new_opsset = opsset.clone()
        new_opsset.translate(dx, dy)
        return new_opsset


__all__ = ["PulseAnimation", "WiggleAnimation", "FlashAnimation", "JitterAnimation"]
