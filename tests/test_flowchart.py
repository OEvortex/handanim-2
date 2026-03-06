from handanim.core.styles import SketchStyle, StrokeStyle
from handanim.primitives import FlowchartConnector, FlowchartProcess


def _deterministic_sketch_style() -> SketchStyle:
    return SketchStyle(
        roughness=0,
        bowing=0,
        max_random_offset=0,
        disable_multi_stroke=True,
        disable_font_mixture=True,
    )


def test_flowchart_process_anchor_points() -> None:
    node = FlowchartProcess(
        text="Process",
        top_left=(100, 200),
        width=240,
        height=120,
        stroke_style=StrokeStyle(),
        sketch_style=_deterministic_sketch_style(),
    )

    assert node.center == (220, 260)
    assert node.anchor_point("top") == (220, 200)
    assert node.anchor_point("right") == (340, 260)
    assert node.anchor_point("bottom") == (220, 320)
    assert node.anchor_point("left") == (100, 260)


def test_flowchart_auto_connection_uses_facing_sides() -> None:
    left = FlowchartProcess(
        text="Left",
        top_left=(100, 100),
        width=200,
        height=100,
        stroke_style=StrokeStyle(),
        sketch_style=_deterministic_sketch_style(),
    )
    right = FlowchartProcess(
        text="Right",
        top_left=(500, 100),
        width=200,
        height=100,
        stroke_style=StrokeStyle(),
        sketch_style=_deterministic_sketch_style(),
    )

    connector = left.connect_to(
        right,
        stroke_style=StrokeStyle(),
        sketch_style=_deterministic_sketch_style(),
    )

    assert connector.points == [(300, 150), (500, 150)]


def test_flowchart_connector_keeps_elbow_waypoints() -> None:
    connector = FlowchartConnector(
        start=(100, 100),
        end=(300, 260),
        waypoints=[(100, 220), (300, 220)],
        stroke_style=StrokeStyle(),
        sketch_style=_deterministic_sketch_style(),
    )

    assert connector.points == [(100, 100), (100, 220), (300, 220), (300, 260)]
    assert len(connector.draw().opsset) > 0