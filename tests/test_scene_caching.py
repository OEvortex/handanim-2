from handanim.animations import FadeInAnimation
from handanim.core.animation import AnimationEvent, AnimationEventType
from handanim.core.draw_ops import Ops, OpsSet, OpsType
from handanim.core.drawable import DrawableGroup
from handanim.core.scene import Scene
from handanim.primitives import Line


class CountingGroupAnimation(AnimationEvent):
    def __init__(self, start_time: float, duration: float) -> None:
        super().__init__(AnimationEventType.CREATION, start_time=start_time, duration=duration)
        self.apply_calls = 0

    def apply(self, opsset: OpsSet, progress: float) -> OpsSet:
        self.apply_calls += 1
        new_opsset = OpsSet(initial_set=opsset.opsset)
        new_opsset.translate(progress * 10, 0)
        return new_opsset


class CountingScene(Scene):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.animated_opsset_call_counts: dict[str, int] = {}

    def get_animated_opsset_at_time(self, drawable_id, t, event_and_progress, drawable_events_mapping):
        self.animated_opsset_call_counts[drawable_id] = (
            self.animated_opsset_call_counts.get(drawable_id, 0) + 1
        )
        return super().get_animated_opsset_at_time(drawable_id, t, event_and_progress, drawable_events_mapping)


def test_parallel_group_animation_apply_is_cached_once_per_frame() -> None:
    scene = Scene(fps=2)
    group = DrawableGroup(
        [
            Line(start=(0, 0), end=(10, 0)),
            Line(start=(0, 10), end=(10, 10)),
        ]
    )
    animation = CountingGroupAnimation(start_time=0.0, duration=1.0)

    scene.add(animation, group)
    timeline = scene.create_event_timeline(max_length=1.0)

    assert len(timeline) == 3
    assert animation.apply_calls == 3


def test_static_visible_object_opsset_is_reused_between_keyframes() -> None:
    scene = CountingScene(fps=10)
    line = Line(start=(0, 0), end=(40, 0))

    scene.add(FadeInAnimation(start_time=0.0, duration=1.0), line)
    timeline = scene.create_event_timeline(max_length=3.0)

    assert len(timeline) == 31
    assert scene.animated_opsset_call_counts[line.id] == 12


def test_opsset_tracks_3d_ops_without_recomputing_each_frame() -> None:
    opsset = OpsSet()
    assert opsset.has_3d_ops() is False

    opsset.add(Ops(OpsType.MOVE_TO, data=[(0.0, 0.0)]))
    assert opsset.has_3d_ops() is False

    opsset.add(
        Ops(
            OpsType.POLYGON_3D,
            data={"points": [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)]},
        )
    )
    assert opsset.has_3d_ops() is True

    cloned = opsset.clone()
    assert cloned.has_3d_ops() is True

    cloned.translate_3d(1.0, 2.0, 3.0)
    assert cloned.has_3d_ops() is True
