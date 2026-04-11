"""
Example demonstrating the improved eraser tool and GPU rendering support.

This example shows:
1. The enhanced eraser tool that completely erases objects
2. GPU-accelerated rendering for faster video generation
"""

from handanim import Scene, StrokeStyle, FillStyle
from handanim.animations import SketchAnimation
from handanim.primitives import Text, Polygon, Eraser
from handanim.stylings.color import BLUE, BLACK, ERASER_HINT_COLOR

# Create scene with GPU rendering (will auto-fallback to CPU if no GPU)
scene = Scene(
    width=1280,
    height=720,
    fps=24,
    render_device="auto",  # Auto-detect GPU
)

print(f"Using render device: {scene.render_device}")

# Create a title text
title = Text(
    text="Enhanced Eraser Demo",
    position=(200, 500),
    font_size=96,
    stroke_style=StrokeStyle(color=BLUE, width=2),
)

# Animate title appearing
scene.add(SketchAnimation(start_time=0, duration=2.0), drawable=title)

# Wait for 1 second
scene.wait(1.0)

# Create eraser to completely erase the title
eraser = Eraser(
    objects_to_erase=[title],
    drawable_cache=scene.drawable_cache,
    stroke_style=StrokeStyle(color=ERASER_HINT_COLOR, width=1),
)

# Animate eraser (now completely erases without leaving artifacts!)
scene.add(SketchAnimation(start_time=3.0, duration=2.0), drawable=eraser)

# Draw a new shape after erasing
triangle = Polygon(
    points=[
        (400, 400),
        (400, 600),
        (800, 600),
    ],
    stroke_style=StrokeStyle(color=BLACK, width=2),
    fill_style=FillStyle(color=BLUE, hachure_gap=10),
)

# Animate triangle appearing on the clean canvas
scene.add(SketchAnimation(start_time=5.5, duration=1.5), drawable=triangle)

# Render the animation
output_file = "eraser_gpu_demo.mp4"
print(f"\nRendering to {output_file}...")
scene.render(output_file, max_length=8.0)
print(f"✓ Done! Check {output_file}")

# Note: If you have an NVIDIA GPU, you should see significantly faster
# rendering speeds compared to CPU-only mode!
