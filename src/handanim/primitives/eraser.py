
from handanim.core.draw_ops import Ops, OpsSet, OpsType
from handanim.core.drawable import Drawable, DrawableCache


class Eraser(Drawable):
    """
    A Drawable representing an eraser that can remove specified drawable objects.

    Attributes:
        objects_to_erase (List[Drawable]): The list of drawable objects to be erased.
        drawable_cache (DrawableCache): Cache used for calculating bounding box of objects to erase.

    The draw method generates a zigzag motion over the bounding box of the objects to be erased,
    using an expanded pen width to create a pastel blend erasing effect.
    """

    def __init__(
        self,
        objects_to_erase: list[Drawable],
        drawable_cache: DrawableCache,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.objects_to_erase = objects_to_erase
        self.drawable_cache = drawable_cache

    def draw(self) -> OpsSet:
        """
        Calculates the zigzag motion of the eraser
        
        The eraser generates a dense raster-scan pattern that fully covers
        the bounding box of objects to erase. The spacing between lines is
        set to half the pen width to ensure complete coverage with overlap.
        """
        opsset = OpsSet(initial_set=[])
        
        # Calculate bounding box with a small margin to ensure edges are fully erased
        min_x, min_y, max_x, max_y = self.drawable_cache.calculate_bounding_box(self.objects_to_erase)
        
        # Add a small margin (10% of dimensions) to ensure complete coverage at edges
        margin_x = (max_x - min_x) * 0.1
        margin_y = (max_y - min_y) * 0.1
        min_x -= margin_x
        min_y -= margin_y
        max_x += margin_x
        max_y += margin_y
        
        pen_width = self.stroke_style.width * 10  # make it like pastel blend
        
        opsset.add(
            Ops(
                OpsType.SET_PEN,
                {
                    "color": self.stroke_style.options.get("color", (1, 1, 1)),
                    "width": pen_width,
                    "opacity": self.stroke_style.opacity,
                },
            )
        )

        # Use spacing smaller than pen width to ensure overlap and complete coverage
        # Using 50% of pen width ensures good coverage without gaps
        spacing = pen_width * 0.5
        y = min_y
        
        opsset.add(Ops(OpsType.MOVE_TO, [(min_x, min_y)]))  # move to top left corner
        going_right = True
        
        while y <= max_y:
            # Draw horizontal line across the bounding box
            if going_right:
                opsset.add(Ops(OpsType.LINE_TO, [(max_x, y)]))
            else:
                opsset.add(Ops(OpsType.LINE_TO, [(min_x, y)]))
            
            y += spacing
            
            # Add vertical segment to next line (if there's more area to cover)
            if y <= max_y:
                if going_right:
                    opsset.add(Ops(OpsType.LINE_TO, [(max_x, y)]))
                else:
                    opsset.add(Ops(OpsType.LINE_TO, [(min_x, y)]))
                going_right = not going_right  # flip direction for next line
        
        # Add a final pass with vertical strokes for any remaining gaps
        # This ensures complete coverage, especially for tall narrow objects
        x_spacing = pen_width * 0.5
        x = min_x + (max_x - min_x) / 2  # Start from middle
        
        opsset.add(Ops(OpsType.MOVE_TO, [(x, min_y)]))
        going_down = True
        
        while x <= max_x:
            # Draw vertical line
            if going_down:
                opsset.add(Ops(OpsType.LINE_TO, [(x, max_y)]))
            else:
                opsset.add(Ops(OpsType.LINE_TO, [(x, min_y)]))
            
            x += x_spacing
            
            # Add horizontal segment to next line
            if x <= max_x:
                if going_down:
                    opsset.add(Ops(OpsType.LINE_TO, [(x, max_y)]))
                else:
                    opsset.add(Ops(OpsType.LINE_TO, [(x, min_y)]))
                going_down = not going_down

        return opsset
