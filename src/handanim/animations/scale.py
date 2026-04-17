from __future__ import annotations

from typing import Callable

import numpy as np

from handanim.core.animation import AnimationEvent, AnimationEventType
from handanim.core.draw_ops import OpsSet


class GrowFromCenterAnimation(AnimationEvent):
    """
    A class representing a grow from center animation event.

    This animation scales an OpsSet from zero scale to full scale, growing from its center of gravity.
    It's useful for entrance effects where objects appear to expand from nothing.

    Args:
        scale_factor (float): The final scale factor. Defaults to 1.0.
        start_time (float, optional): The start time of the animation. Defaults to 0.
        duration (float, optional): The duration of the animation. Defaults to 0.
        easing_fun (callable, optional): An optional easing function to modify animation progress. Defaults to None.
        data (dict, optional): Additional data associated with the animation. Defaults to None.
    """

    def __init__(
        self,
        scale_factor: float = 1.0,
        start_time: float = 0.0,
        duration: float = 0.0,
        easing_fun: Callable[[float], float] | None = None,
        data: dict | None = None,
    ) -> None:
        super().__init__(AnimationEventType.CREATION, start_time, duration, easing_fun, data)
        self.scale_factor = scale_factor

    def apply(self, opsset: OpsSet, progress: float) -> OpsSet:
        if self.easing_fun is not None:
            progress = float(self.easing_fun(progress))
        
        current_scale = self.scale_factor * progress
        
        new_opsset = opsset.clone()
        new_opsset.scale(current_scale, current_scale)
        return new_opsset


class ShrinkToPointAnimation(AnimationEvent):
    """
    A class representing a shrink to point animation event.

    This animation scales an OpsSet from its current size down to zero at a specified point.
    It's useful for exit effects where objects appear to shrink into nothing.

    Args:
        point (tuple[float, float]): The point to shrink toward. If None, uses center of gravity.
        start_time (float, optional): The start time of the animation. Defaults to 0.
        duration (float, optional): The duration of the animation. Defaults to 0.
        easing_fun (callable, optional): An optional easing function to modify animation progress. Defaults to None.
        data (dict, optional): Additional data associated with the animation. Defaults to None.
    """

    def __init__(
        self,
        point: tuple[float, float] | None = None,
        start_time: float = 0.0,
        duration: float = 0.0,
        easing_fun: Callable[[float], float] | None = None,
        data: dict | None = None,
    ) -> None:
        super().__init__(AnimationEventType.DELETION, start_time, duration, easing_fun, data)
        self.point = point

    def apply(self, opsset: OpsSet, progress: float) -> OpsSet:
        if self.easing_fun is not None:
            progress = float(self.easing_fun(progress))
        
        # Scale from 1 down to 0
        current_scale = 1.0 - progress
        
        new_opsset = opsset.clone()
        new_opsset.scale(current_scale, current_scale)
        return new_opsset


class ScaleFromPointAnimation(AnimationEvent):
    """
    A class representing a scale from point animation event.

    This animation scales an OpsSet from zero scale at a specified point to its full size.
    The object appears to grow from that point.

    Args:
        point (tuple[float, float]): The point to scale from. If None, uses center of gravity.
        scale_factor (float): The final scale factor. Defaults to 1.0.
        start_time (float, optional): The start time of the animation. Defaults to 0.
        duration (float, optional): The duration of the animation. Defaults to 0.
        easing_fun (callable, optional): An optional easing function to modify animation progress. Defaults to None.
        data (dict, optional): Additional data associated with the animation. Defaults to None.
    """

    def __init__(
        self,
        point: tuple[float, float] | None = None,
        scale_factor: float = 1.0,
        start_time: float = 0.0,
        duration: float = 0.0,
        easing_fun: Callable[[float], float] | None = None,
        data: dict | None = None,
    ) -> None:
        super().__init__(AnimationEventType.CREATION, start_time, duration, easing_fun, data)
        self.point = point
        self.scale_factor = scale_factor

    def apply(self, opsset: OpsSet, progress: float) -> OpsSet:
        if self.easing_fun is not None:
            progress = float(self.easing_fun(progress))
        
        current_scale = self.scale_factor * progress
        
        new_opsset = opsset.clone()
        new_opsset.scale(current_scale, current_scale)
        return new_opsset


__all__ = ["GrowFromCenterAnimation", "ShrinkToPointAnimation", "ScaleFromPointAnimation"]
