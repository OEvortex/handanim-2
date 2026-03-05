"""
Example: Importing images and videos into a scene.

This script demonstrates how to use the Image and Video primitives
to embed raster media into your hand-drawn animations.
"""

import os

from handanim.core import Scene
from handanim.animations import FadeInAnimation, SketchAnimation
from handanim.primitives import Image, Text
from handanim.stylings.color import BLUE


def main():
    # Create a scene - 16:8 aspect ratio (1920x960)
    scene = Scene(width=1920, height=960, fps=24)

    # Get the assets directory path
    assets_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "assets")

    # --- Example: Adding a heart image with explanation ---
    # The heart image is drawn with the top-left corner at the specified position
    
    # Add title text explaining the heart
    title = Text(
        text="The Human Heart",
        position=(960, 100),
        font_size=100,
    )
    scene.add(SketchAnimation(start_time=0, duration=2), drawable=title)

    # Add description text about the heart
    description = Text(
        text="A muscular organ that pumps blood throughout the body.",
        position=(960, 800),
        font_size=48,
    )
    scene.add(SketchAnimation(start_time=2, duration=2), drawable=description)

    # Key facts about the heart - displayed in two columns
    facts_left = [
        "Beats about 100,000",
        "times per day",
    ]
    facts_right = [
        "Pumps about 2,000",
        "gallons of blood daily",
    ]

    # Add left column facts
    for i, fact in enumerate(facts_left):
        fact_text = Text(
            text=fact,
            position=(500, 860 + i * 40),
            font_size=36,
        )
        scene.add(SketchAnimation(start_time=4 + i * 0.5, duration=1), drawable=fact_text)

    # Add right column facts
    for i, fact in enumerate(facts_right):
        fact_text = Text(
            text=fact,
            position=(1420, 860 + i * 40),
            font_size=36,
        )
        scene.add(SketchAnimation(start_time=4.5 + i * 0.5, duration=1), drawable=fact_text)

    # Add the heart image - larger and centered
    image_path = os.path.join(assets_dir, "heart.png")
    
    if os.path.exists(image_path):
        # Display the heart image - it has a white background
        heart = Image(
            path=image_path,
            top_left=(660, 180),  # Centered horizontally (1920/2 - 600/2 = 660)
            width=600,
        )
        # Add a fade-in animation for the image
        scene.add(
            FadeInAnimation(start_time=1, duration=2),
            drawable=heart,
        )
    else:
        # Placeholder text if image doesn't exist
        placeholder = Text(
            text="(heart.png not found in examples/assets/)",
            position=(960, 500),
            font_size=48,
        )
        scene.add(SketchAnimation(start_time=0, duration=1), drawable=placeholder)

    # Create output directory if it doesn't exist
    output_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "output")
    os.makedirs(output_dir, exist_ok=True)

    # Render the animation
    scene.render(os.path.join(output_dir, "media_demo.mp4"), max_length=8)
    print("Animation saved to examples/output/media_demo.mp4")


if __name__ == "__main__":
    main()
