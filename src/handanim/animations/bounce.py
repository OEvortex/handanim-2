from __future__ import annotations

import math
from typing import Callable

import numpy as np

from handanim.core.animation import AnimationEvent, AnimationEventType
from handanim.core.draw_ops import OpsSet


def _bounce_easing(progress: float) -> float:
    """
    Bounce easing function for elastic effects.
    
    This creates a bouncing effect where the animation overshoots and settles.
    """
    if progress == 0:
        return 0.0
    if progress == 1:
        return 1.0
    
    # Bounce formula
    n1 = 7.5625
    d1 = 2.75
    
    if progress < 1 / d1:
        return n1 * progress * progress
    elif progress < 2 / d1:
        progress -= 1.5 / d1
        return n1 * progress * progress + 0.75
    elif progress < 2.5 / d1:
        progress -= 2.25 / d1
        return n1 * progress * progress + 0.9375
    else:
        progress -= 2.625 / d1
        return n1 * progress * progress + 0.984375


def _elastic_easing(progress: float) -> float:
    """
    Elastic easing function for spring-like effects.
    
    This creates an elastic spring effect with overshoot.
    """
    if progress == 0:
        return 0.0
    if progress == 1:
        return 1.0
    
    return math.sin(-13.0 * math.pi / 2 * (progress + 1)) * math.pow(2, -10 * progress) + 1


class BounceInAnimation(AnimationEvent):
    """
    A class representing a bounce-in animation event.

    This animation creates an entrance effect where the object bounces in with
    an elastic overshoot effect, starting from zero scale.

    Args:
        scale_factor (float): The final scale factor. Defaults to 1.0.
        bounce_type (str): Type of bounce - "bounce" or "elastic". Defaults to "bounce".
        start_time (float, optional): The start time of the animation. Defaults to 0.
        duration (float, optional): The duration of the animation. Defaults to 0.
        easing_fun (callable, optional): An optional custom easing function. Defaults to None.
        data (dict, optional): Additional data associated with the animation. Defaults to None.
    """

    def __init__(
        self,
        scale_factor: float = 1.0,
        bounce_type: str = "bounce",
        start_time: float = 0.0,
        duration: float = 0.0,
        easing_fun: Callable[[float], float] | None = None,
        data: dict | None = None,
    ) -> None:
        super().__init__(AnimationEventType.CREATION, start_time, duration, easing_fun, data)
        self.scale_factor = scale_factor
        self.bounce_type = bounce_type

    def apply(self, opsset: OpsSet, progress: float) -> OpsSet:
        if self.easing_fun is not None:
            eased_progress = float(self.easing_fun(progress))
        else:
            if self.bounce_type == "elastic":
                eased_progress = _elastic_easing(progress)
            else:
                eased_progress = _bounce_easing(progress)
        
        current_scale = self.scale_factor * eased_progress
        
        new_opsset = opsset.clone()
        new_opsset.scale(current_scale, current_scale)
        return new_opsset


class BounceOutAnimation(AnimationEvent):
    """
    A class representing a bounce-out animation event.

    This animation creates an exit effect where the object bounces out with
    an elastic overshoot effect, shrinking to zero scale.

    Args:
        bounce_type (str): Type of bounce - "bounce" or "elastic". Defaults to "bounce".
        start_time (float, optional): The start time of the animation. Defaults to 0.
        duration (float, optional): The duration of the animation. Defaults to 0.
        easing_fun (callable, optional): An optional custom easing function. Defaults to None.
        data (dict, optional): Additional data associated with the animation. Defaults to None.
    """

    def __init__(
        self,
        bounce_type: str = "bounce",
        start_time: float = 0.0,
        duration: float = 0.0,
        easing_fun: Callable[[float], float] | None = None,
        data: dict | None = None,
    ) -> None:
        super().__init__(AnimationEventType.DELETION, start_time, duration, easing_fun, data)
        self.bounce_type = bounce_type

    def apply(self, opsset: OpsSet, progress: float) -> OpsSet:
        if self.easing_fun is not None:
            eased_progress = float(self.easing_fun(progress))
        else:
            # Reverse the easing for bounce out
            if self.bounce_type == "elastic":
                eased_progress = 1 - _elastic_easing(1 - progress)
            else:
                eased_progress = 1 - _bounce_easing(1 - progress)
        
        current_scale = eased_progress
        
        new_opsset = opsset.clone()
        new_opsset.scale(current_scale, current_scale)
        return new_opsset


__all__ = ["BounceInAnimation", "BounceOutAnimation"]
