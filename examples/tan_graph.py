import os
import numpy as np
from handanim.core import Scene, StrokeStyle, SketchStyle
from handanim.animations import SketchAnimation
from handanim.primitives import Arrow, Curve, Math, Line
from handanim.stylings.color import BLACK, BLUE, RED, GRAY

def main():
    # Scene setup
    # Default viewport maps (0, 1777) x (0, 1000) for 1920x1088
    scene = Scene(width=1920, height=1088)
    
    center_x, center_y = 888, 500
    x_min, x_max = 200, 1577
    y_min, y_max = 100, 900

    # Axes
    x_axis = Arrow(
        start_point=(x_min, center_y),
        end_point=(x_max, center_y),
        # stroke_style=StrokeStyle(color=BLACK, width=3)
    )
    y_axis = Arrow(
        start_point=(center_x, y_max),
        end_point=(center_x, y_min),
        # stroke_style=StrokeStyle(color=BLACK, width=3)
    )

    scene.add(SketchAnimation(duration=2), drawable=x_axis)
    scene.add(SketchAnimation(duration=2), drawable=y_axis)

    # Tan graph scaling
    scale_x = 200  # 1 unit = 200 pixels
    scale_y = 100  # 1 unit = 100 pixels

    def to_screen(x, y):
        return (center_x + x * scale_x, center_y - y * scale_y)

    # Plotting range: -1.5*pi to 1.5*pi
    # We use a small epsilon to avoid the exact asymptotes
    eps = 0.15
    branches = [
        (-1.5 * np.pi + eps, -0.5 * np.pi - eps),
        (-0.5 * np.pi + eps, 0.5 * np.pi - eps),
        (0.5 * np.pi + eps, 1.5 * np.pi - eps)
    ]

    for i, (start, end) in enumerate(branches):
        x_vals = np.linspace(start, end, 100)
        y_vals = np.tan(x_vals)
        
        # Clip y_vals to keep them within reasonable screen bounds
        # Viewport y is 0 to 1000. center_y is 500.
        # y_vals * scale_y should be within [-400, 400] roughly
        mask = (y_vals > -4) & (y_vals < 4)
        x_vals = x_vals[mask]
        y_vals = y_vals[mask]
        
        if len(x_vals) < 2:
            continue
            
        points = [to_screen(x, y) for x, y in zip(x_vals, y_vals)]
        tan_curve = Curve(
            points=points,
            stroke_style=StrokeStyle(color=BLUE, width=4),
            sketch_style=SketchStyle(roughness=2)
        )
        # Stagger the drawing of each branch
        scene.add(SketchAnimation(start_time=2 + i*1.0, duration=1.5), drawable=tan_curve)

    # Asymptotes (dashed-like vertical lines)
    asymptotes = [-1.5*np.pi, -0.5*np.pi, 0.5*np.pi, 1.5*np.pi]
    for x_val in asymptotes:
        p1 = to_screen(x_val, -4.5)
        p2 = to_screen(x_val, 4.5)
        asymp_line = Line(
            start=p1,
            end=p2,
            stroke_style=StrokeStyle(color=GRAY, width=1, opacity=0.5)
        )
        scene.add(SketchAnimation(start_time=1.5, duration=1), drawable=asymp_line)

    # Labels
    title = Math(
        tex_expression=r"$y = \tan(\theta)$",
        position=(700, 150),
        font_size=128,
        stroke_style=StrokeStyle(color=RED),
        sketch_style=sketch
    )
    scene.add(SketchAnimation(start_time=0, duration=2), drawable=title)

    # Axis labels
    theta_label = Math(tex_expression=r"$\theta$", position=(x_max + 20, center_y), font_size=64, sketch_style=sketch)
    y_label = Math(tex_expression=r"$y$", position=(center_x, y_min - 40), font_size=64, sketch_style=sketch)
    scene.add(SketchAnimation(start_time=2, duration=1), drawable=theta_label)
    scene.add(SketchAnimation(start_time=2, duration=1), drawable=y_label)

    # Ticks and values on X axis
    ticks = [
        (-np.pi, r"$-\pi$"),
        (-0.5*np.pi, r"$-\frac{\pi}{2}$"),
        (0.5*np.pi, r"$\frac{\pi}{2}$"),
        (np.pi, r"$\pi$")
    ]

    for x_val, tex in ticks:
        pos = to_screen(x_val, 0)
        tick_line = Line(
            start=(pos[0], pos[1] - 10),
            end=(pos[0], pos[1] + 10),
            stroke_style=StrokeStyle(color=BLACK, width=2)
        )
        label = Math(tex_expression=tex, position=(pos[0] - 40, pos[1] + 60), font_size=48, sketch_style=sketch)
        scene.add(SketchAnimation(start_time=2.5, duration=0.5), drawable=tick_line)
        scene.add(SketchAnimation(start_time=2.5, duration=1), drawable=label)

    # Save the scene
    output_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "output")
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    output_path = os.path.join(output_dir, "tan_graph.mp4")
    
    print(f"Rendering scene to {output_path}...")
    scene.render(output_path, max_length=8)
    print("Done!")

if __name__ == "__main__":
    main()
