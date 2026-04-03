from handanim.animations import SketchAnimation
from handanim.core.draw_ops import Ops, OpsSet, OpsType


def _setup_only_opsset() -> OpsSet:
    return OpsSet(
        initial_set=[
            Ops(OpsType.SET_PEN, {"color": (0, 0, 0), "opacity": 1.0, "width": 1.0}),
            Ops(OpsType.MOVE_TO, [(0, 0)]),
            Ops(OpsType.METADATA, {"drawing_mode": "draw"}),
        ]
    )


def _single_line_opsset() -> OpsSet:
    return OpsSet(
        initial_set=[
            Ops(OpsType.SET_PEN, {"color": (0, 0, 0), "opacity": 1.0, "width": 1.0}),
            Ops(OpsType.MOVE_TO, [(0, 0)]),
            Ops(OpsType.LINE_TO, [(10, 0)]),
        ]
    )


def test_sketch_animation_ignores_setup_only_opsset() -> None:
    animation = SketchAnimation(
        start_time=0.0,
        duration=1.0,
        data={"glowing_dot": {"radius": 3}},
    )

    result = animation.apply(_setup_only_opsset(), 0.5)

    assert result.opsset == []


def test_sketch_animation_zero_duration_completes_immediately() -> None:
    animation = SketchAnimation(
        start_time=0.0,
        duration=0.0,
        data={"glowing_dot": {"radius": 3}},
    )
    opsset = _single_line_opsset()

    result = animation.apply(opsset, 1.0)

    assert [op.type for op in result.opsset] == [op.type for op in opsset.opsset]
