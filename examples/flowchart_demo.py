import os

from handanim.animations import FadeInAnimation, SketchAnimation
from handanim.core import FillStyle, Scene, SketchStyle, StrokeStyle
from handanim.primitives import (
    FlowchartDecision,
    FlowchartInputOutput,
    FlowchartProcess,
    FlowchartTerminator,
    Text,
)
from handanim.stylings.color import BLACK, BLUE, ORANGE, PASTEL_BLUE, PASTEL_GREEN, WHITE


def build_scene() -> Scene:
    scene = Scene(width=1920, height=1080, fps=24, background_color=WHITE)
    stroke = StrokeStyle(color=BLACK, width=2.6)
    sketch = SketchStyle(roughness=1.2, bowing=1.1, disable_font_mixture=True)

    title = Text(
        text="Flowchart Example",
        position=(888, 90),
        font_size=84,
        stroke_style=StrokeStyle(color=BLUE, width=2.5),
        sketch_style=sketch,
    )

    start = FlowchartTerminator(
        text="Start",
        top_left=(760, 150),
        width=250,
        height=110,
        font_size=42,
        stroke_style=stroke,
        sketch_style=sketch,
        fill_style=FillStyle(color=PASTEL_GREEN, hachure_gap=10),
    )
    collect = FlowchartProcess(
        text="Collect Prompt",
        top_left=(695, 320),
        width=380,
        height=120,
        font_size=38,
        stroke_style=stroke,
        sketch_style=sketch,
        fill_style=FillStyle(color=PASTEL_BLUE, hachure_gap=10),
    )
    decision = FlowchartDecision(
        text="Valid Input?",
        top_left=(745, 510),
        width=280,
        height=180,
        font_size=34,
        stroke_style=stroke,
        sketch_style=sketch,
        fill_style=FillStyle(color=ORANGE, hachure_gap=11, opacity=0.55),
    )
    revise = FlowchartInputOutput(
        text="Ask For Fixes",
        top_left=(1220, 530),
        width=300,
        height=110,
        font_size=34,
        stroke_style=stroke,
        sketch_style=sketch,
        fill_style=FillStyle(color=PASTEL_BLUE, hachure_gap=10),
    )
    render = FlowchartProcess(
        text="Render Scene",
        top_left=(700, 770),
        width=370,
        height=120,
        font_size=38,
        stroke_style=stroke,
        sketch_style=sketch,
        fill_style=FillStyle(color=PASTEL_GREEN, hachure_gap=10),
    )
    finish = FlowchartTerminator(
        text="Finish",
        top_left=(760, 930),
        width=250,
        height=110,
        font_size=42,
        stroke_style=stroke,
        sketch_style=sketch,
        fill_style=FillStyle(color=PASTEL_GREEN, hachure_gap=10),
    )

    connectors = [
        start.connect_to(collect, stroke_style=stroke, sketch_style=sketch),
        collect.connect_to(decision, stroke_style=stroke, sketch_style=sketch),
        decision.connect_to(
            render,
            start_side="bottom",
            end_side="top",
            stroke_style=stroke,
            sketch_style=sketch,
        ),
        decision.connect_to(
            revise,
            start_side="right",
            end_side="left",
            stroke_style=stroke,
            sketch_style=sketch,
        ),
        revise.connect_to(
            collect,
            start_side="top",
            end_side="right",
            waypoints=[(1370, 340), (1075, 340)],
            stroke_style=stroke,
            sketch_style=sketch,
        ),
        render.connect_to(finish, stroke_style=stroke, sketch_style=sketch),
    ]

    yes_label = Text(
        text="yes",
        position=(1080, 705),
        font_size=28,
        stroke_style=stroke,
        sketch_style=sketch,
    )
    no_label = Text(
        text="no",
        position=(1110, 560),
        font_size=28,
        stroke_style=stroke,
        sketch_style=sketch,
    )

    scene.add(event=FadeInAnimation(start_time=0, duration=0.6), drawable=title)
    scene.add(event=SketchAnimation(start_time=0.4, duration=1.0), drawable=start)
    scene.add(event=SketchAnimation(start_time=1.2, duration=1.0), drawable=collect)
    scene.add(event=SketchAnimation(start_time=2.0, duration=1.0), drawable=decision)
    scene.add(event=SketchAnimation(start_time=2.8, duration=1.0), drawable=connectors[0])
    scene.add(event=SketchAnimation(start_time=3.3, duration=1.0), drawable=connectors[1])
    scene.add(event=SketchAnimation(start_time=4.0, duration=1.0), drawable=render)
    scene.add(event=SketchAnimation(start_time=4.8, duration=1.0), drawable=connectors[2])
    scene.add(event=FadeInAnimation(start_time=5.0, duration=0.5), drawable=yes_label)
    scene.add(event=SketchAnimation(start_time=5.4, duration=1.0), drawable=revise)
    scene.add(event=SketchAnimation(start_time=6.2, duration=1.0), drawable=connectors[3])
    scene.add(event=FadeInAnimation(start_time=6.4, duration=0.5), drawable=no_label)
    scene.add(event=SketchAnimation(start_time=7.0, duration=1.1), drawable=connectors[4])
    scene.add(event=SketchAnimation(start_time=8.0, duration=1.0), drawable=finish)
    scene.add(event=SketchAnimation(start_time=8.6, duration=0.9), drawable=connectors[5])
    return scene


def main() -> None:
    output_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "output")
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "flowchart_demo.mp4")
    print(f"Rendering flowchart demo to {output_path}...")
    build_scene().render(output_path, max_length=10)


if __name__ == "__main__":
    main()