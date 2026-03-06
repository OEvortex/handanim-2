"""Detailed whiteboard lesson: how the human heart works."""

import os

from handanim.animations import FadeInAnimation, SketchAnimation, TranslateToPersistAnimation
from handanim.core import FillStyle, Scene, StrokeStyle
from handanim.primitives import Arrow, Eraser, Image, Math, Rectangle, Text
from handanim.stylings.color import (
    BLACK,
    BLUE,
    ERASER_HINT_COLOR,
    LIGHT_GRAY,
    ORANGE,
    RED,
)


def add_bullets(
    scene: Scene,
    lines: list[str],
    start_time: float,
    x: float,
    y_start: float,
    *,
    font_size: int = 32,
    y_step: float = 60,
    font_name: str = "feasibly",
    color: tuple[float, float, float] = BLACK,
) -> list[Text]:
    """Add a staggered bullet list and return created Text objects."""
    bullets: list[Text] = []
    for i, line in enumerate(lines):
        bullet = Text(
            text=f"- {line}",
            position=(x, y_start + i * y_step),
            font_size=font_size,
            font_name=font_name,
            stroke_style=StrokeStyle(color=color, width=2.8),
        )
        scene.add(SketchAnimation(start_time=start_time + i * 0.4, duration=0.8), drawable=bullet)
        bullets.append(bullet)
    return bullets


def make_right_panel() -> Rectangle:
    """Create a reusable right-side teaching panel."""
    return Rectangle(
        top_left=(760, 170),
        width=890,
        height=800,
        stroke_style=StrokeStyle(color=BLACK, width=2),
        fill_style=FillStyle(color=LIGHT_GRAY, opacity=0.15, hachure_gap=16),
    )


def main():
    scene = Scene(width=1920, height=1080, fps=24)
    assets_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "assets")
    image_path = os.path.join(assets_dir, "heart.png")

    # Board 1: structure overview
    title1 = Text(
        text="The Human Heart",
        position=(960, 80),
        font_size=118,
        font_name="permanent_marker",
        stroke_style=StrokeStyle(color=BLUE, width=4.5),
    )
    subtitle1 = Text(
        text="4 chambers, 4 valves, 1 powerful pump",
        position=(960, 145),
        font_size=50,
        font_name="permanent_marker",
        stroke_style=StrokeStyle(color=BLACK, width=2.6),
    )
    scene.add(SketchAnimation(start_time=0.0, duration=1.8), drawable=title1)
    scene.add(SketchAnimation(start_time=1.2, duration=1.5), drawable=subtitle1)

    if not os.path.exists(image_path):
        missing = Text(
            text="(heart.png not found in examples/assets/)",
            position=(960, 520),
            font_size=56,
            stroke_style=StrokeStyle(width=3),
        )
        scene.add(SketchAnimation(start_time=0.5, duration=1.5), drawable=missing)
        output_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "output")
        os.makedirs(output_dir, exist_ok=True)
        scene.render(os.path.join(output_dir, "media_demo.mp4"), max_length=6)
        print("Animation saved to examples/output/media_demo.mp4")
        return

    heart = Image(path=image_path, top_left=(700, 250), width=520)
    scene.add(FadeInAnimation(start_time=1.5, duration=2.0), drawable=heart)

    chamber_labels: list[Text] = []
    chamber_arrows: list[Arrow] = []
    chamber_data = [
        ("Right Atrium", (370, 300), (770, 350)),
        ("Right Ventricle", (360, 610), (840, 565)),
        ("Left Atrium", (1540, 300), (1145, 350)),
        ("Left Ventricle", (1560, 610), (1060, 575)),
    ]

    for i, (name, label_pos, arrow_end) in enumerate(chamber_data):
        label = Text(
            text=name,
            position=label_pos,
            font_size=42,
            font_name="permanent_marker",
            stroke_style=StrokeStyle(color=BLACK, width=2.6),
        )
        arrow = Arrow(
            start_point=label_pos,
            end_point=arrow_end,
            stroke_style=StrokeStyle(color=RED, width=3.8),
        )
        chamber_labels.append(label)
        chamber_arrows.append(arrow)
        scene.add(SketchAnimation(start_time=3.8 + i * 0.9, duration=1.2), drawable=label)
        scene.add(SketchAnimation(start_time=4.1 + i * 0.9, duration=0.9), drawable=arrow)

    board1_note = Text(
        text="Right side sends blood to lungs; left side sends blood to body.",
        position=(960, 955),
        font_size=38,
        font_name="feasibly",
        stroke_style=StrokeStyle(color=BLACK, width=2.2),
    )
    scene.add(SketchAnimation(start_time=8.0, duration=1.6), drawable=board1_note)

    # Wipe board 1 (keep heart), then move heart to the left
    board1_eraser = Eraser(
        objects_to_erase=[title1, subtitle1, board1_note] + chamber_labels + chamber_arrows,
        drawable_cache=scene.drawable_cache,
        glow_dot_hint={"color": ERASER_HINT_COLOR, "radius": 10},
    )
    scene.add(SketchAnimation(start_time=10.0, duration=2.2), drawable=board1_eraser)
    scene.add(
        TranslateToPersistAnimation(start_time=11.0, duration=1.6, data={"point": (340, 540)}),
        drawable=heart,
    )

    # Board 2: blood flow path
    panel2 = make_right_panel()
    title2 = Text(
        text="1) Blood Flow Path",
        position=(1205, 90),
        font_size=86,
        font_name="permanent_marker",
        stroke_style=StrokeStyle(color=ORANGE, width=4.2),
    )
    scene.add(SketchAnimation(start_time=13.0, duration=1.5), drawable=panel2)
    scene.add(SketchAnimation(start_time=13.2, duration=1.6), drawable=title2)

    flow_lines = add_bullets(
        scene,
        lines=[
            "Body veins -> Right atrium (deoxygenated blood)",
            "Tricuspid valve -> Right ventricle",
            "Pulmonary valve -> Pulmonary artery -> lungs",
            "Lungs exchange gases: CO2 out, O2 in",
            "Pulmonary veins -> Left atrium",
            "Mitral valve -> Left ventricle",
            "Aortic valve -> Aorta",
            "Aorta distributes oxygen-rich blood to body",
        ],
        start_time=14.2,
        x=1205,
        y_start=250,
        font_size=30,
        y_step=72,
    )
    circulation_note_1 = Text(
        text="Pulmonary loop: heart -> lungs -> heart",
        position=(1205, 860),
        font_size=34,
        font_name="permanent_marker",
        stroke_style=StrokeStyle(color=BLUE, width=2.3),
    )
    circulation_note_2 = Text(
        text="Systemic loop: heart -> body -> heart",
        position=(1205, 920),
        font_size=34,
        font_name="permanent_marker",
        stroke_style=StrokeStyle(color=BLUE, width=2.3),
    )
    scene.add(SketchAnimation(start_time=18.2, duration=1.2), drawable=circulation_note_1)
    scene.add(SketchAnimation(start_time=18.8, duration=1.2), drawable=circulation_note_2)

    board2_eraser = Eraser(
        objects_to_erase=[title2, panel2, circulation_note_1, circulation_note_2] + flow_lines,
        drawable_cache=scene.drawable_cache,
        glow_dot_hint={"color": ERASER_HINT_COLOR, "radius": 10},
    )
    scene.add(SketchAnimation(start_time=29.0, duration=2.0), drawable=board2_eraser)

    # Board 3: cardiac cycle
    panel3 = make_right_panel()
    title3 = Text(
        text="2) Cardiac Cycle",
        position=(1205, 90),
        font_size=86,
        font_name="permanent_marker",
        stroke_style=StrokeStyle(color=ORANGE, width=4.2),
    )
    scene.add(SketchAnimation(start_time=31.2, duration=1.4), drawable=panel3)
    scene.add(SketchAnimation(start_time=31.5, duration=1.6), drawable=title3)

    cycle_lines = add_bullets(
        scene,
        lines=[
            "Diastole: ventricles relax and fill with blood",
            "Systole: ventricles contract and eject blood",
            '"Lub" sound: AV valves close',
            '"Dub" sound: semilunar valves close',
        ],
        start_time=32.8,
        x=1205,
        y_start=350,
        font_size=36,
        y_step=100,
    )

    board3_eraser = Eraser(
        objects_to_erase=[title3, panel3] + cycle_lines,
        drawable_cache=scene.drawable_cache,
        glow_dot_hint={"color": ERASER_HINT_COLOR, "radius": 10},
    )
    scene.add(SketchAnimation(start_time=40.0, duration=2.0), drawable=board3_eraser)

    # Board 4: electrical control
    panel4 = make_right_panel()
    title4 = Text(
        text="3) Electrical Control",
        position=(1205, 90),
        font_size=86,
        font_name="permanent_marker",
        stroke_style=StrokeStyle(color=ORANGE, width=4.2),
    )
    scene.add(SketchAnimation(start_time=42.2, duration=1.4), drawable=panel4)
    scene.add(SketchAnimation(start_time=42.5, duration=1.6), drawable=title4)

    electrical_lines = add_bullets(
        scene,
        lines=[
            "SA node starts each heartbeat (natural pacemaker)",
            "AV node delays the signal so ventricles can fill",
            "Bundle branches carry signal through septum",
            "Purkinje fibers create coordinated ventricular squeeze",
        ],
        start_time=43.8,
        x=1205,
        y_start=350,
        font_size=34,
        y_step=100,
    )

    co_formula = Math(
        tex_expression=r"$CO = HR \times SV$",
        position=(1205, 850),
        font_size=80,
        font_name="notosans_math",
        stroke_style=StrokeStyle(color=BLUE, width=2.5),
    )
    co_note = Text(
        text="At rest: HR 60-100 bpm, CO is about 5 L/min",
        position=(1205, 930),
        font_size=36,
        font_name="feasibly",
        stroke_style=StrokeStyle(color=BLACK, width=2.4),
    )
    scene.add(SketchAnimation(start_time=48.0, duration=1.5), drawable=co_formula)
    scene.add(SketchAnimation(start_time=49.0, duration=1.5), drawable=co_note)

    board4_eraser = Eraser(
        objects_to_erase=[title4, panel4, co_formula, co_note] + electrical_lines,
        drawable_cache=scene.drawable_cache,
        glow_dot_hint={"color": ERASER_HINT_COLOR, "radius": 10},
    )
    scene.add(SketchAnimation(start_time=55.0, duration=2.0), drawable=board4_eraser)

    # Board 5: coronary supply and heart health
    panel5 = make_right_panel()
    title5 = Text(
        text="4) Coronary Supply + Health",
        position=(1205, 90),
        font_size=72,
        font_name="permanent_marker",
        stroke_style=StrokeStyle(color=ORANGE, width=3.8),
    )
    scene.add(SketchAnimation(start_time=57.2, duration=1.4), drawable=panel5)
    scene.add(SketchAnimation(start_time=57.4, duration=1.6), drawable=title5)

    health_lines = add_bullets(
        scene,
        lines=[
            "Coronary arteries supply oxygen to heart muscle",
            "Blocked coronary flow can cause a heart attack",
            "Healthy valves keep blood moving one direction",
            "Exercise improves stroke volume and efficiency",
            "Control blood pressure, glucose, and cholesterol",
            "Avoid smoking; sleep and stress control matter",
            "Early checkups help prevent silent heart disease",
        ],
        start_time=58.4,
        x=1205,
        y_start=255,
        font_size=32,
        y_step=86,
    )
    closing_line = Text(
        text="Your heart beats around 100,000 times/day to keep every organ alive.",
        position=(1205, 920),
        font_size=32,
        font_name="permanent_marker",
        stroke_style=StrokeStyle(color=RED, width=2.2),
    )
    scene.add(SketchAnimation(start_time=65.0, duration=1.5), drawable=closing_line)

    # Final render
    output_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "output")
    os.makedirs(output_dir, exist_ok=True)
    scene.render(os.path.join(output_dir, "media_demo.mp4"), max_length=75)
    print("Animation saved to examples/output/media_demo.mp4")


if __name__ == "__main__":
    main()
