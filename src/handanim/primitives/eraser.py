from handanim.core.draw_ops import Ops, OpsSet, OpsType
from handanim.core.drawable import Drawable, DrawableCache


class Eraser(Drawable):
    """A drawable that covers the requested objects with the scene background color."""

    def __init__(
        self,
        objects_to_erase: list[Drawable],
        drawable_cache: DrawableCache,
        *args,
        erase_color: tuple[float, float, float] = (1.0, 1.0, 1.0),
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.objects_to_erase = objects_to_erase
        self.drawable_cache = drawable_cache
        self.erase_color = erase_color

    def _get_object_bbox(self, drawable: Drawable) -> tuple[float, float, float, float]:
        if self.drawable_cache.exists_in_cache(drawable.id):
            opsset = self.drawable_cache.get_drawable_opsset(drawable.id)
        else:
            opsset = drawable.draw()
        return opsset.get_bbox()

    @staticmethod
    def _expand_bbox(
        bbox: tuple[float, float, float, float],
        stroke_width: float,
    ) -> tuple[float, float, float, float]:
        min_x, min_y, max_x, max_y = bbox
        width = max_x - min_x
        height = max_y - min_y
        padding = max(width, height) * 0.08
        padding = max(padding, stroke_width * 4.0, 12.0)
        return (
            min_x - padding,
            min_y - padding,
            max_x + padding,
            max_y + padding,
        )

    def _add_cover_rect(
        self,
        opsset: OpsSet,
        bbox: tuple[float, float, float, float],
    ) -> None:
        min_x, min_y, max_x, max_y = bbox
        opsset.add(
            Ops(
                OpsType.SET_PEN,
                {
                    "color": self.erase_color,
                    "width": 0.0,
                    "opacity": 1.0,
                    "mode": "fill",
                },
            )
        )
        opsset.add(Ops(OpsType.MOVE_TO, [(min_x, min_y)]))
        opsset.add(Ops(OpsType.LINE_TO, [(max_x, min_y)]))
        opsset.add(Ops(OpsType.LINE_TO, [(max_x, max_y)]))
        opsset.add(Ops(OpsType.LINE_TO, [(min_x, max_y)]))
        opsset.add(Ops(OpsType.CLOSE_PATH, []))

    def draw(self) -> OpsSet:
        """Return filled cover paths for every drawable being erased."""
        opsset = OpsSet(initial_set=[])

        for drawable in self.objects_to_erase:
            bbox = self._get_object_bbox(drawable)
            if bbox == (0, 0, 0, 0):
                continue
            stroke_width = getattr(drawable.stroke_style, "width", 0.0) or 0.0
            expanded_bbox = self._expand_bbox(bbox, float(stroke_width))
            self._add_cover_rect(opsset, expanded_bbox)

        return opsset
