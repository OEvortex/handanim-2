# handanim - Educational Animation Guide

**Goal**: Create 60-180 second whiteboard-style animations for educational videos.

**Philosophy**: Hand-drawn animations with sketch aesthetics, built-in audio sync, and programmatic Python API.

---

## handanim Architecture

handanim uses a different paradigm from Manim. Instead of `self.play()` with run_time, it uses:
- **Event-based timeline**: Add animations with `start_time` and `duration`
- **Drawable objects**: All visual elements are Drawables that get added to a Scene
- **Rendering**: Call `scene.render()` at the end to export video

### Basic Scene Template

```python
import os
from handanim.core import Scene, FillStyle, StrokeStyle, SketchStyle
from handanim.animations import SketchAnimation, FadeInAnimation
from handanim.primitives import Text, Math, Polygon, Rectangle
from handanim.stylings.color import BLACK, BLUE, RED, WHITE

def build_scene() -> Scene:
    # Create scene with dimensions
    scene = Scene(width=1920, height=1080, fps=24, background_color=WHITE)
    
    # Create drawable elements
    title = Text(
        text="Your Title",
        position=(960, 500),  # pixel coordinates
        font_size=72,
        stroke_style=StrokeStyle(color=BLUE, width=2),
    )
    
    # Add animations with start_time and duration
    scene.add(SketchAnimation(start_time=0, duration=3), drawable=title)
    
    # Render when done
    return scene

# Save and render
output_path = os.path.join(os.path.dirname(__file__), "output", "my_scene.mp4")
build_scene().render(output_path, max_length=15)
```

---

## Import Structure

```python
# Core scene and styling
from handanim.core import Scene, FillStyle, StrokeStyle, SketchStyle, DrawableGroup

# Animations
from handanim.animations import (
    SketchAnimation, FadeInAnimation, FadeOutAnimation,
    Transform, ReplacementTransform, MorphAnimation,
    TranslateFromAnimation, TranslateToAnimation,
    Rotate3DAnimation, Translate3DAnimation,
    ZoomInAnimation, ZoomOutAnimation,
)

# Primitives
from handanim.primitives import (
    Text, MathTex, Math,  # Text variants
    Circle, Ellipse, Polygon, Rectangle, Square, NGon, RoundedRectangle,
    Line, Arrow, CurvedArrow,
    Image, Video,
    Table, FlowchartProcess, FlowchartDecision, FlowchartTerminator,
    Cone, Cube, Cylinder, Sphere, Prism,
)

# Colors
from handanim.stylings.color import BLACK, WHITE, BLUE, RED, GREEN, ORANGE
```

---

## Coordinate System

handanim uses **pixel coordinates** (origin at top-left):

```python
# Position: (x, y) - y increases downward
position=(960, 540)      # Center of 1920x1080 canvas
position=(960, 100)      # Near top
position=(960, 980)      # Near bottom

# Alternatively use top_left, bottom_right for bounding boxes
rectangle = Rectangle(top_left=(100, 100), width=500, height=300)
```

### Canvas Dimensions
- **Landscape (16:9)**: 1920x1080 (viewport ~1777x1000)
- **Portrait (9:16)**: 1080x1920
- **Custom**: Any resolution supported

---

## Creating Drawables

### Text

```python
from handanim.primitives import Text, MathTex
from handanim.core import StrokeStyle

# Regular text
title = Text(
    text="Pythagoras' Theorem",
    position=(960, 500),
    font_size=72,
    stroke_style=StrokeStyle(color=BLUE, width=2),
)

# Math equations
formula = MathTex(
    tex_expression=r"$a^2 + b^2 = c^2$",
    position=(960, 300),
    font_size=48,
    stroke_style=StrokeStyle(color=BLUE, width=2),
    font_name="feasibly",  # custom hand-drawn font
)
```

### Shapes

```python
from handanim.primitives import Polygon, Circle, Rectangle, NGon
from handanim.core import FillStyle, StrokeStyle, SketchStyle

# Triangle/Polygon
triangle = Polygon(
    points=[(500, 500), (500, 700), (900, 700)],
    stroke_style=StrokeStyle(color=BLACK, width=2),
    sketch_style=SketchStyle(roughness=5),
    fill_style=FillStyle(color=RED, hachure_gap=10),
)

# Circle
circle = Circle(
    center=(960, 540),
    radius=100,
    stroke_style=StrokeStyle(color=BLUE, width=2),
    fill_style=FillStyle(color=RED, opacity=0.5),
)

# Rectangle
rect = Rectangle(
    top_left=(100, 100),
    width=500,
    height=300,
    stroke_style=StrokeStyle(color=BLACK, width=2),
    fill_style=FillStyle(color=BLUE, opacity=0.3),
)
```

### Groups

```python
from handanim.core import DrawableGroup

# Group multiple drawables
label_group = DrawableGroup(
    elements=[
        Text(text="a", position=(450, 600), font_size=36),
        Text(text="b", position=(700, 800), font_size=36),
    ]
)
```

---

## Styling

### StrokeStyle

```python
from handanim.core import StrokeStyle

stroke = StrokeStyle(
    color=BLACK,           # color name or (r, g, b) tuple
    width=2,               # line thickness
    opacity=1.0,          # transparency
)
```

### FillStyle

```python
from handanim.core import FillStyle

fill = FillStyle(
    color=RED,            # fill color
    opacity=0.5,           # transparency
    hachure_gap=10,       # hatching gap for sketch style
)
```

### SketchStyle

```python
from handanim.core import SketchStyle

sketch = SketchStyle(
    roughness=5,          # hand-drawn roughness
    bowing=1.0,           # line bowing amount
    disable_font_mixture=True,  # uniform sketch style
)
```

### Available Colors

```python
from handanim.stylings.color import (
    BLACK, WHITE, BLUE, RED, GREEN, YELLOW, ORANGE, PURPLE,
    PASTEL_BLUE, PASTEL_GREEN, PASTEL_ORANGE,
    ERASER_HINT_COLOR,
)
```

---

## Animations

### SketchAnimation (Hand-drawn effect)

```python
from handanim.animations import SketchAnimation

# Draw an object with hand-drawn animation
scene.add(
    SketchAnimation(start_time=0, duration=3),  # start at 0s, draw for 3s
    drawable=my_shape
)
```

### Fade Animations

```python
from handanim.animations import FadeInAnimation, FadeOutAnimation

scene.add(FadeInAnimation(start_time=0, duration=0.5), drawable=obj)
scene.add(FadeOutAnimation(start_time=3, duration=0.5), drawable=obj)
```

### Transform Animations

```python
from handanim.animations import Transform, ReplacementTransform

# Transform between objects (at same position)
scene.add(Transform(start_time=2, duration=1), old_obj, new_obj)

# Replace with new object
scene.add(ReplacementTransform(start_time=2, duration=1), old_obj, new_obj)
```

### 3D Animations

```python
from handanim.animations import (
    Rotate3DAnimation, Translate3DAnimation, ZoomInAnimation, ZoomOutAnimation
)

# Rotate in 3D
scene.add(
    Rotate3DAnimation(angle=360, axis=(0, 1, 0), start_time=0, duration=2),
    drawable=obj
)

# Move in 3D space
scene.add(
    Translate3DAnimation(offset=(100, 0, 0), start_time=0, duration=2),
    drawable=obj
)
```

### Zoom Animations

```python
scene.add(ZoomInAnimation(start_time=0, duration=1), drawable=obj)
scene.add(ZoomOutAnimation(start_time=2, duration=1), drawable=obj)
```

---

## Special Objects

### Eraser

```python
from handanim.primitives import Eraser
from handanim.stylings.color import ERASER_HINT_COLOR

eraser = Eraser(
    objects_to_erase=[title_text],
    drawable_cache=scene.drawable_cache,
    glow_dot_hint={"color": ERASER_HINT_COLOR, "radius": 10},
)
scene.add(SketchAnimation(start_time=3.5, duration=1.5), drawable=eraser)
```

### Flowchart Nodes

```python
from handanim.primitives import (
    FlowchartProcess, FlowchartDecision, FlowchartTerminator,
    FlowchartInputOutput, FlowchartConnector,
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

process = FlowchartProcess(
    text="Process",
    top_left=(695, 320),
    width=380,
    height=120,
    font_size=38,
    stroke_style=stroke,
    sketch_style=sketch,
    fill_style=FillStyle(color=PASTEL_BLUE, hachure_gap=10),
)

decision = FlowchartDecision(
    text="Yes/No?",
    top_left=(745, 510),
    width=280,
    height=180,
    font_size=34,
    stroke_style=stroke,
    sketch_style=sketch,
    fill_style=FillStyle(color=ORANGE, hachure_gap=11, opacity=0.55),
)
```

### Tables

```python
from handanim.primitives import Table

table = Table(
    top_left=(100, 100),
    data=[
        ["Header1", "Header2", "Header3"],
        ["Row1Col1", "Row1Col2", "Row1Col3"],
        ["Row2Col1", "Row2Col2", "Row2Col3"],
    ],
    stroke_style=StrokeStyle(color=BLACK, width=2),
    fill_style=FillStyle(color=WHITE),
)
```

### Images and Video

```python
from handanim.primitives import Image, Video

# Image
img = Image(
    top_left=(100, 100),
    width=400,
    path="path/to/image.png",
)

# Video
vid = Video(
    top_left=(100, 100),
    width=800,
    path="path/to/video.mp4",
)
```

---

## 3D Scenes

### SpecialThreeDScene

```python
from handanim.core import SpecialThreeDScene, FillStyle, StrokeStyle
from handanim.primitives import Prism, Sphere, Cylinder
from handanim.animations import FadeInAnimation, Translate3DAnimation, Rotate3DAnimation

def build_scene() -> SpecialThreeDScene:
    scene = SpecialThreeDScene(
        width=1280, height=720, fps=24, 
        background_color=(0.95, 0.97, 1.0)
    )
    
    # Set camera angle
    scene.set_to_default_angled_camera_orientation(
        phi=74, theta=-112, zoom=1.16, 
        frame_center=(0.0, 0.0, 0.6)
    )
    
    # Add objects
    obj = Prism(dimensions=(4.6, 2.0, 0.48), center=(0, 0, 0), ...)
    scene.add(FadeInAnimation(start_time=0, duration=1), obj)
    
    # Animate in 3D
    scene.add(Translate3DAnimation(offset=(10, 0, 0), start_time=1, duration=3), obj)
    scene.add(Rotate3DAnimation(angle=360, axis=(0, 1, 0), start_time=1, duration=3), obj)
    
    # Move camera
    scene.move_camera(theta=-104, phi=68, zoom=1.18, 
                      frame_center=(-1.0, 0.0, 0.62), 
                      start_time=0, duration=2.6)
    
    return scene
```

---

## Audio Sync

### Voiceover with Bookmarks

```python
import edge_tts
import re
from handanim.animations import FadeInAnimation
from handanim.core import Scene
from handanim.primitives import Text, Rectangle

# Script with bookmarks
SCRIPTS = {
    "intro": "<bookmark mark='title'/> Your title here. "
             "<bookmark mark='panel'/> Panel appears as narration continues.",
}

# Generate audio with bookmarks
async def synthesize():
    communicate = edge_tts.Communicate(script, "en-US-JennyNeural")
    await communicate.save("output.mp3")

# Create scene with audio track
scene = Scene(width=1280, height=720, fps=24, background_color=WHITE)
scene.set_viewport_to_identity()

# Add audio (requires audio_path in render)
# scene.render(output_path, max_length=15, audio_path="output.mp3")
```

---

## Rendering

### Render to Video

```python
scene = Scene(width=1920, height=1080, fps=24, background_color=WHITE)
# ... add drawables and animations ...

# Render video
scene.render("output/my_video.mp4", max_length=15)

# Optional: with audio
scene.render("output/video_with_audio.mp4", max_length=15, audio_path="voiceover.mp3")
```

### Render to SVG Snapshot

```python
# Get a snapshot at specific time
scene.render_snapshot("output/snapshot.svg", frame_in_seconds=3, max_length=15)
```

---

## Complete Example

```python
import os
from handanim.animations import SketchAnimation
from handanim.core import Scene, FillStyle, StrokeStyle, SketchStyle, DrawableGroup
from handanim.primitives import Text, Math, Polygon, Eraser
from handanim.stylings.color import BLACK, BLUE, RED, ERASER_HINT_COLOR

scene = Scene(width=1920, height=1088, background_color=(1, 1, 1))
FONT_NAME = "feasibly"

# Draw title
title_text = Text(
    text="Pythagoras' Theorem",
    position=(960, 500),
    font_size=192,
    stroke_style=StrokeStyle(color=BLUE, width=2),
)
scene.add(SketchAnimation(duration=3), drawable=title_text)

# Erase title
eraser = Eraser(
    objects_to_erase=[title_text],
    drawable_cache=scene.drawable_cache,
    glow_dot_hint={"color": ERASER_HINT_COLOR, "radius": 10},
)
scene.add(SketchAnimation(start_time=3.5, duration=1.5), drawable=eraser)

# Draw triangle
right_triangle = Polygon(
    points=[(500, 500), (500, 700), (900, 700)],
    stroke_style=StrokeStyle(color=BLACK, width=2),
    sketch_style=SketchStyle(roughness=5),
    fill_style=FillStyle(color=RED, hachure_gap=10),
)
scene.add(SketchAnimation(start_time=6, duration=3), drawable=right_triangle)

# Add labels
label_group = DrawableGroup(elements=[
    Text(text="a", position=(450, 600), font_size=96),
    Text(text="b", position=(700, 800), font_size=96),
])
scene.add(SketchAnimation(start_time=8, duration=2), drawable=label_group)

# Add formula
pyth_form = Math(
    tex_expression=r"$a^2 + b^2 = c^2$",
    position=(900, 300),
    font_size=128,
    stroke_style=StrokeStyle(color=BLUE, width=2),
    font_name=FONT_NAME,
)
scene.add(SketchAnimation(start_time=10, duration=3), drawable=pyth_form)

# Render
output_path = os.path.join(os.path.dirname(__file__), "output", "pythagoras.mp4")
scene.render(output_path, max_length=15)
```

---

## Quick Checklist

Before returning:
- [ ] Used `scene.add(event, drawable=obj)` pattern, NOT `self.play()`
- [ ] All animations have `start_time` and `duration` parameters
- [ ] Used pixel coordinates `(x, y)` for positioning
- [ ] Imported from correct handanim modules
- [ ] Included all imports at top
- [ ] Called `scene.render()` at the end
- [ ] Used proper StrokeStyle/FillStyle/SketchStyle objects
- [ ] Used proper color imports from `handanim.stylings.color`
