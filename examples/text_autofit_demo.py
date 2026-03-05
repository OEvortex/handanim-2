import os
from handanim.core import Scene, StrokeStyle
from handanim.animations import SketchAnimation
from handanim.primitives import Rectangle, Text
from handanim.stylings.color import WHITE, BLACK

def main():
    # Create a scene
    scene = Scene(width=1280, height=720, fps=30, background_color=BLACK)
    
    # Define a bounding box (x, y, width, height)
    box_rect = (440, 260, 400, 200)
    
    # 1. Draw the actual rectangle for visual reference
    rect = Rectangle(
        top_left=(box_rect[0], box_rect[1]),
        width=box_rect[2],
        height=box_rect[3],
        stroke_style=StrokeStyle(color=WHITE, width=2)
    )
    
    # 2. Create text that is naturally too large for the box
    # We use rect_box and rect_padding to make it autofit and center
    autofit_text = Text(
        text="This text is automatically scaled down and centered to fit perfectly inside the box!",
        position=(0, 0), # Position is ignored when rect_box is provided
        font_size=72,    # Large base size that will be scaled down
        rect_box=box_rect,
        rect_padding=20,
        stroke_style=StrokeStyle(color=WHITE)
    )
    
    # Add animations to the scene
    scene.add(SketchAnimation(start_time=0, duration=2), drawable=rect)
    scene.add(SketchAnimation(start_time=1, duration=3), drawable=autofit_text)
    
    # Render the result
    output_path = os.path.join("examples", "output", "text_autofit_demo.mp4")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    print(f"Rendering example to {output_path}...")
    scene.render(output_path)

if __name__ == "__main__":
    main()
