from __future__ import annotations

from typing import Callable

import numpy as np

from handanim.core.animation import AnimationEvent, AnimationEventType
from handanim.core.draw_ops import OpsSet


class SlideInAnimation(AnimationEvent):
    """
    A class representing a slide-in animation event.

    This animation creates an entrance effect where the object slides in from a specified direction.
    The object starts off-screen and slides into its final position.

    Args:
        direction (str): Direction to slide from - "left", "right", "up", "down". Defaults to "left".
        distance (float | None): Distance to slide in pixels. If None, uses screen width/height estimate. Defaults to None.
        start_time (float, optional): The start time of the animation. Defaults to 0.
        duration (float, optional): The duration of the animation. Defaults to 0.
        easing_fun (callable, optional): An optional easing function to modify animation progress. Defaults to None.
        data (dict, optional): Additional data associated with the animation. Defaults to None.
    """

    def __init__(
        self,
        direction: str = "left",
        distance: float | None = None,
        start_time: float = 0.0,
        duration: float = 0.0,
        easing_fun: Callable[[float], float] | None = None,
        data: dict | None = None,
    ) -> None:
        super().__init__(AnimationEventType.CREATION, start_time, duration, easing_fun, data)
        self.direction = direction.lower()
        self.distance = distance or 1000.0  # Default large distance

    def apply(self, opsset: OpsSet, progress: float) -> OpsSet:
        if self.easing_fun is not None:
            progress = float(self.easing_fun(progress))
        
        # Calculate offset based on direction
        if self.direction == "left":
            dx = -self.distance * (1 - progress)
            dy = 0
        elif self.direction == "right":
            dx = self.distance * (1 - progress)
            dy = 0
        elif self.direction == "up":
            dx = 0
            dy = -self.distance * (1 - progress)
        elif self.direction == "down":
            dx = 0
            dy = self.distance * (1 - progress)
        else:
            raise ValueError(f"Invalid direction: {self.direction}. Must be 'left', 'right', 'up', or 'down'")
        
        new_opsset = opsset.clone()
        new_opsset.translate(dx, dy)
        return new_opsset


class SlideOutAnimation(AnimationEvent):
    """
    A class representing a slide-out animation event.

    This animation creates an exit effect where the object slides out in a specified direction.
    The object starts at its current position and slides off-screen.

    Args:
        direction (str): Direction to slide to - "left", "right", "up", "down". Defaults to "right".
        distance (float | None): Distance to slide in pixels. If None, uses screen width/height estimate. Defaults to None.
        start_time (float, optional): The start time of the animation. Defaults to 0.
        duration (float, optional): The duration of the animation. Defaults to 0.
        easing_fun (callable, optional): An optional easing function to modify animation progress. Defaults to None.
        data (dict, optional): Additional data associated with the animation. Defaults to None.
    """

    def __init__(
        self,
        direction: str = "right",
        distance: float | None = None,
        start_time: float = 0.0,
        duration: float = 0.0,
        easing_fun: Callable[[float], float] | None = None,
        data: dict | None = None,
    ) -> None:
        super().__init__(AnimationEventType.DELETION, start_time, duration, easing_fun, data)
        self.direction = direction.lower()
        self.distance = distance or 1000.0  # Default large distance

    def apply(self, opsset: OpsSet, progress: float) -> OpsSet:
        if self.easing_fun is not None:
            progress = float(self.easing_fun(progress))
        
        # Calculate offset based on direction
        if self.direction == "left":
            dx = -self.distance * progress
            dy = 0
        elif self.direction == "right":
            dx = self.distance * progress
            dy = 0
        elif self.direction == "up":
            dx = 0
            dy = -self.distance * progress
        elif self.direction == "down":
            dx = 0
            dy = self.distance * progress
        else:
            raise ValueError(f"Invalid direction: {self.direction}. Must be 'left', 'right', 'up', or 'down'")
        
        new_opsset = opsset.clone()
        new_opsset.translate(dx, dy)
        return new_opsset


class SlideAnimation(AnimationEvent):
    """
    A class representing a slide animation event between two points.

    This animation slides an object from a starting point to an ending point.
    It's useful for repositioning elements smoothly.

    Args:
        start_point (tuple[float, float]): The starting position (x, y).
        end_point (tuple[float, float]): The ending position (x, y).
        start_time (float, optional): The start time of the animation. Defaults to 0.
        duration (float, optional): The duration of the animation. Defaults to 0.
        easing_fun (callable, optional): An optional easing function to modify animation progress. Defaults to None.
        data (dict, optional): Additional data associated with the animation. Defaults to None.
    """

    def __init__(
        self,
        start_point: tuple[float, float],
        end_point: tuple[float, float],
        start_time: float = 0.0,
        duration: float = 0.0,
        easing_fun: Callable[[float], float] | None = None,
        data: dict | None = None,
    ) -> None:
        super().__init__(AnimationEventType.MUTATION, start_time, duration, easing_fun, data)
        self.start_point = start_point
        self.end_point = end_point

    def apply(self, opsset: OpsSet, progress: float) -> OpsSet:
        if self.easing_fun is not None:
            progress = float(self.easing_fun(progress))
        
        # Calculate current position by interpolating
        current_x = self.start_point[0] + (self.end_point[0] - self.start_point[0]) * progress
        current_y = self.start_point[1] + (self.end_point[1] - self.start_point[1]) * progress
        
        # Calculate offset from original position
        center_x, center_y = opsset.get_center_of_gravity()
        dx = current_x - center_x
        dy = current_y - center_y
        
        new_opsset = opsset.clone()
        new_opsset.translate(dx, dy)
        return new_opsset


__all__ = ["SlideInAnimation", "SlideOutAnimation", "SlideAnimation"]
