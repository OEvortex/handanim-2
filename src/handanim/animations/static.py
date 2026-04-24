from handanim.core.animation import AnimationEvent, AnimationEventType
from handanim.core.draw_ops import OpsSet


class StaticAnimation(AnimationEvent):
    """
    A static animation that keeps a drawable visible without any changes.
    
    This is useful for holding a drawable in place while audio continues playing.
    The drawable remains in its final state from previous animations.
    
    Args:
        start_time (float): The starting time point of the static hold in seconds.
        duration (float): The duration of the static hold in seconds.
    """
    
    def __init__(
        self,
        start_time: float = 0.0,
        duration: float = 0.0,
    ) -> None:
        super().__init__(
            type=AnimationEventType.MUTATION,
            start_time=start_time,
            duration=duration,
            data={"keep_final_state": True}
        )
    
    def apply(self, opsset: OpsSet, progress: float) -> OpsSet:
        """
        No-op - keeps the drawable in its current state.
        """
        return opsset
