"""
Example: Importing images and videos into a scene.

This script demonstrates how to use the Image and Video primitives
to embed raster media into your hand-drawn animations.
"""

import os

from handanim.core import Scene, StrokeStyle, SketchStyle, FillStyle
from handanim.animations import (
    FadeInAnimation, 
    SketchAnimation, 
    TranslateToPersistAnimation
)
from handanim.primitives import (
    Image, 
    Text, 
    Arrow, 
    Math, 
    Rectangle, 
    VectorSVG
)
from handanim.stylings.color import BLUE, RED, BLACK, ORANGE, LIGHT_GRAY


def main():
    # Create a scene - 16:9 aspect ratio (1920x1080)
    scene = Scene(width=1920, height=1080, fps=24)

    # Get the assets directory path
    assets_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "assets")

    # --- Narrator: The Professor ---
    svg_path = os.path.join(assets_dir, "professor.svg")
    professor = VectorSVG.from_svg_file(
        svg_path,
        position=(1600, 800),
        glow_dot_hint={"color": BLUE, "radius": 5},
    )
    professor.scale(0.5, 0.5)
    scene.add(
        event=SketchAnimation(start_time=0.5, duration=2),
        drawable=professor,
    )

    # Add title text explaining the heart
    title = Text(
        text="The Human Heart",
        position=(960, 80),
        font_size=120,
        font_name="permanent_marker",
        stroke_style=StrokeStyle(width=5, color=BLUE),
    )
    scene.add(SketchAnimation(start_time=0, duration=2), drawable=title)

    # Add the heart image - larger and centered
    image_path = os.path.join(assets_dir, "heart.png")
    
    if os.path.exists(image_path):
        # Frame for the heart image
        heart_frame = Rectangle(
            top_left=(650, 170),
            width=620,
            height=520,
            stroke_style=StrokeStyle(color=BLACK, width=2),
            fill_style=FillStyle(color=LIGHT_GRAY, opacity=0.1, hachure_gap=20),
            sketch_style=SketchStyle(roughness=2),
        )
        scene.add(SketchAnimation(start_time=1, duration=1.5), drawable=heart_frame)

        # Display the heart image
        heart = Image(
            path=image_path,
            top_left=(660, 180),
            width=600,
        )
        scene.add(
            FadeInAnimation(start_time=1.5, duration=2),
            drawable=heart,
        )

        # Move professor to point at the heart
        scene.add(
            event=TranslateToPersistAnimation(
                start_time=3.5, duration=1, data={"point": (1400, 450)}
            ),
            drawable=professor,
        )

        # Labels for heart chambers
        labels = [
            ("Right Atrium", (400, 300), (780, 350)),
            ("Left Atrium", (1520, 300), (1140, 350)),
            ("Right Ventricle", (400, 600), (850, 550)),
            ("Left Ventricle", (1520, 600), (1070, 550)),
        ]

        for i, (label_text, pos, arrow_end) in enumerate(labels):
            # Label text
            label = Text(
                text=label_text,
                position=pos,
                font_size=48,
                font_name="headstay",
                stroke_style=StrokeStyle(width=3),
                sketch_style=SketchStyle(roughness=3),
            )
            scene.add(SketchAnimation(start_time=4.5 + i * 1, duration=1.5), drawable=label)

            # Arrow pointing to the chamber
            arrow = Arrow(
                start_point=pos,
                end_point=arrow_end,
                stroke_style=StrokeStyle(color=RED, width=4),
            )
            scene.add(SketchAnimation(start_time=5 + i * 1, duration=1), drawable=arrow)

    else:
        # Placeholder text if image doesn't exist
        placeholder = Text(
            text="(heart.png not found in examples/assets/)",
            position=(960, 500),
            font_size=48,
            stroke_style=StrokeStyle(width=3),
        )
        scene.add(SketchAnimation(start_time=0, duration=1), drawable=placeholder)

    # Add description text about the heart
    description = Text(
        text="A muscular organ that pumps blood throughout the body.",
        position=(960, 800),
        font_size=56,
        font_name="caveat",
        stroke_style=StrokeStyle(width=3, color=BLACK),
    )
    scene.add(SketchAnimation(start_time=10, duration=2), drawable=description)

    # Key facts about the heart
    facts_left = [
        "Beats about 100,000",
        "times per day",
    ]
    facts_right = [
        "Pumps about 2,000",
        "gallons of blood daily",
    ]

    for i, fact in enumerate(facts_left):
        fact_text = Text(
            text=fact,
            position=(400, 860 + i * 40),
            font_size=40,
            font_name="feasibly",
            stroke_style=StrokeStyle(width=2),
        )
        scene.add(SketchAnimation(start_time=12 + i * 0.5, duration=1), drawable=fact_text)

    for i, fact in enumerate(facts_right):
        fact_text = Text(
            text=fact,
            position=(1520, 860 + i * 40),
            font_size=40,
            font_name="feasibly",
            stroke_style=StrokeStyle(width=2),
        )
        scene.add(SketchAnimation(start_time=12.5 + i * 0.5, duration=1), drawable=fact_text)

    # Add a math formula for heart rate
    hr_formula = Math(
        tex_expression=r"$\text{Heart Rate} = \frac{60}{\text{Time per beat}}$",
        position=(960, 720),
        font_size=64,
        stroke_style=StrokeStyle(color=BLUE, width=2),
    )
    scene.add(SketchAnimation(start_time=14, duration=3), drawable=hr_formula)

    # Move professor back to corner
    scene.add(
        event=TranslateToPersistAnimation(
            start_time=17, duration=1, data={"point": (1600, 800)}
        ),
        drawable=professor,
    )

    # Create output directory if it doesn't exist
    output_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "output")
    os.makedirs(output_dir, exist_ok=True)

    # Render the animation
    scene.render(os.path.join(output_dir, "media_demo.mp4"), max_length=20)
    print("Animation saved to examples/output/media_demo.mp4")


if __name__ == "__main__":
    main()
