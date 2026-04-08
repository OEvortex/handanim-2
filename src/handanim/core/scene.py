from collections.abc import Generator, Iterable
from contextlib import contextmanager
from pathlib import Path
import tempfile
from typing import TYPE_CHECKING

import cairo
import imageio.v2 as imageio
import numpy as np
from tqdm import tqdm

if TYPE_CHECKING:
    from .animation import AnimationEvent
    from .drawable import Drawable

from .audio import AudioTrack, VoiceoverTracker, attach_audio_to_video
from .animation import AnimationEvent, AnimationEventType, CompositeAnimationEvent
from .draw_ops import OpsSet
from .drawable import Drawable, DrawableCache, DrawableGroup, EmptyDrawable, FrozenDrawable
from .utils import cairo_surface_to_numpy
from .viewport import Viewport


class Scene:
    """
    A Scene represents an animation composition where drawables and events are managed.

    Handles the creation, timeline, and rendering of animated graphics with configurable
    viewport, background, and frame settings. Supports creating snapshots and full video
    renders of animated sequences.

    Attributes:
        width (int): Width of the rendering surface in pixels.
        height (int): Height of the rendering surface in pixels.
        fps (int): Frames per second for video rendering.
        background_color (tuple): RGB color for scene background.
        viewport (Viewport): Defines coordinate mapping between world and screen space.
    """

    def __init__(
        self,
        width: int = 1280,
        height: int = 720,
        fps: int = 24,
        background_color: tuple[float, float, float] = (1, 1, 1),
        viewport: Viewport | None = None,
        render_quality: str = "fast",
    ) -> None:
        self.width = width
        self.height = height
        self.fps = fps
        self.background_color = background_color
        self.render_quality = render_quality
        self.drawable_cache = DrawableCache()
        self.events: list[tuple[AnimationEvent, str]] = []
        self.object_timelines: dict[str, list[float]] = {}
        self.audio_tracks: list[AudioTrack] = []
        self.timeline_cursor = 0.0
        self.drawable_groups: dict[
            str, DrawableGroup
        ] = {}  # stores drawable groups present in the scene
        self.drawablegroup_frame_cache: dict[
            str, OpsSet
        ] = {}  # a temporary frame specific cache that resets for each frame
        self.drawablegroup_transformed_frame_cache: dict[
            str, OpsSet
        ] = {}  # temporary cache for group event.apply() results within a frame
        # NEW: Cache for intermediate animation states to avoid O(N²) recursive computation
        # Key: (drawable_id, event_index, frame_index) -> OpsSet
        self._animation_state_cache: dict[tuple[str, int, int], OpsSet] = {}
        # NEW: Cache for event_and_progress results
        # Key: (drawable_id, frame_index) -> list[tuple[AnimationEvent, float]]
        self._event_progress_cache: dict[tuple[str, int], list[tuple[AnimationEvent, float]]] = {}
        # NEW: Cache for fully composed frame opssets (drawable_id, frame_index) -> OpsSet
        self._frame_opsset_cache: dict[tuple[str, int], OpsSet] = {}

        if viewport is not None:
            self.viewport = viewport
        else:
            self.viewport = Viewport(
                world_xrange=(
                    0,
                    1000 * (width / height),
                ),  # adjusted to match aspect ratio
                world_yrange=(0, 1000),
                screen_width=width,
                screen_height=height,
                margin=20,
            )

    def set_viewport_to_identity(self) -> None:
        """
        Resets the viewport to an identity transformation, mapping world coordinates directly to screen coordinates.
        """
        self.viewport = Viewport(
            world_xrange=(0, self.width),
            world_yrange=(0, self.height),
            screen_width=self.width,
            screen_height=self.height,
            margin=0,
        )

    def get_viewport_bounds(self) -> tuple[float, float, float, float]:
        """
        Retrieves the viewport's boundaries in world coordinates.

        Returns:
            Tuple[float, float, float, float]: A tuple containing (x_min, x_max, y_min, y_max)
            representing the viewport's world coordinate boundaries.
        """
        return (
            self.viewport.world_xrange[0],
            self.viewport.world_xrange[1],
            self.viewport.world_yrange[0],
            self.viewport.world_yrange[1],
        )

    def set_timeline_cursor(self, scene_time: float) -> None:
        self.timeline_cursor = max(float(scene_time), 0.0)

    def advance_timeline(self, duration: float) -> float:
        self.timeline_cursor = max(self.timeline_cursor + float(duration), 0.0)
        return self.timeline_cursor

    def add_audio(
        self,
        path: str,
        start_time: float | None = None,
        volume: float = 1.0,
        clip_start: float = 0.0,
        clip_end: float | None = None,
    ) -> AudioTrack:
        resolved_start_time = self.timeline_cursor if start_time is None else float(start_time)
        track = AudioTrack(
            path=path,
            start_time=resolved_start_time,
            volume=volume,
            clip_start=clip_start,
            clip_end=clip_end,
        )
        self.audio_tracks.append(track)
        self.timeline_cursor = max(self.timeline_cursor, track.end_time)
        return track

    def add_voiceover(
        self,
        path: str,
        text: str | None = None,
        start_time: float | None = None,
        volume: float = 1.0,
        clip_start: float = 0.0,
        clip_end: float | None = None,
    ) -> VoiceoverTracker:
        track = self.add_audio(
            path=path,
            start_time=start_time,
            volume=volume,
            clip_start=clip_start,
            clip_end=clip_end,
        )
        return VoiceoverTracker(track, text=text)

    @contextmanager
    def voiceover(
        self,
        path: str,
        text: str | None = None,
        start_time: float | None = None,
        volume: float = 1.0,
        clip_start: float = 0.0,
        clip_end: float | None = None,
    ) -> Generator[VoiceoverTracker, None, None]:
        tracker = self.add_voiceover(
            path=path,
            text=text,
            start_time=start_time,
            volume=volume,
            clip_start=clip_start,
            clip_end=clip_end,
        )
        try:
            yield tracker
        finally:
            self.timeline_cursor = max(self.timeline_cursor, tracker.end_time)

    def add(
        self,
        event: AnimationEvent,
        drawable: Drawable | None = None,
    ) -> None:
        """
        Adds an animation event to a drawable primitive in the scene.

        Handles different scenarios including:
        - Composite animation events (recursively adding sub-events)
        - Drawable groups with parallel or sequential event distribution
        - Single event and drawable cases

        Manages event tracking, drawable caching, and object timelines.

        Args:
            event (AnimationEvent): The animation event to be added.
            drawable (Drawable): The drawable primitive to apply the event to.
        """
        # handle the case for composite events if any
        if isinstance(event, CompositeAnimationEvent):
            for sub_event in event.events:
                self.add(sub_event, drawable)  # recursively call add() for the subevents
            return

        if drawable is None:
            drawable = getattr(event, "source_drawable", None)
        if drawable is None:
            msg = "Scene.add() requires a drawable unless the event provides source_drawable"
            raise ValueError(msg)

        expand_for_scene = getattr(event, "expand_for_scene", None)
        if callable(expand_for_scene):
            expanded_result = expand_for_scene(scene=self, drawable=drawable)
            if expanded_result is not None:
                expanded_events: Iterable[tuple[AnimationEvent, Drawable]] = expanded_result  # type: ignore[assignment]
                for expanded_event, expanded_drawable in expanded_events:
                    self.add(expanded_event, expanded_drawable)
                return

        resolve_target_drawable = getattr(event, "resolve_target_drawable", None)
        if callable(resolve_target_drawable) and getattr(event, "target_drawable", None) is None:
            setattr(
                event, "target_drawable", resolve_target_drawable(drawable=drawable, scene=self)
            )

        if isinstance(drawable, DrawableGroup):
            target_drawable = getattr(event, "target_drawable", None)
            if target_drawable is not None:
                if not isinstance(target_drawable, DrawableGroup):
                    msg = "TransformAnimation between DrawableGroup and non-group drawables is not supported"
                    raise NotImplementedError(msg)
                if (
                    drawable.grouping_method != "parallel"
                    or target_drawable.grouping_method != "parallel"
                ):
                    msg = (
                        "TransformAnimation currently supports only parallel DrawableGroup morphing"
                    )
                    raise NotImplementedError(msg)

                pair_drawables = getattr(event, "pair_drawables", None)
                clone_for_target = getattr(event, "clone_for_target", None)
                if not callable(pair_drawables) or not callable(clone_for_target):
                    msg = "This event does not support DrawableGroup morphing"
                    raise NotImplementedError(msg)

                from handanim.animations.fade import FadeInAnimation

                for elem in drawable.elements:
                    self.drawable_cache.set_drawable_opsset(elem)
                    self.drawable_cache.drawables[elem.id] = elem
                for elem in target_drawable.elements:
                    self.drawable_cache.set_drawable_opsset(elem)
                    self.drawable_cache.drawables[elem.id] = elem

                element_pairs = pair_drawables(
                    drawable.elements, target_drawable.elements, self.drawable_cache
                )
                for source_elem, target_elem in element_pairs:  # type: ignore[assignment]
                    actual_source: Drawable | None = source_elem
                    actual_target: Drawable | None = target_elem
                    if actual_source is None:
                        actual_source = EmptyDrawable()
                        self.add(
                            FadeInAnimation(start_time=event.start_time, duration=0.0),
                            actual_source,
                        )
                    if actual_target is None:
                        actual_target = EmptyDrawable()
                    self.add(clone_for_target(actual_target), actual_source)  # type: ignore[arg-type]
                return

            # drawable group are usually a syntactic sugar for applying the event to its elements
            if drawable.grouping_method == "series":
                # Apply the event sequentially to each element in the group
                segmented_events = event.subdivide(len(drawable.elements))
                for sub_drawable, segment_event in zip(
                    drawable.elements, segmented_events, strict=False
                ):
                    # recursively call add(), but with the duration modified appropriately
                    self.add(event=segment_event, drawable=sub_drawable)
                return
            if drawable.grouping_method == "parallel":
                # group does not have any drawable opsset, so it is not in cache
                # but group_memberships are useful to calculate the opsset on which events get applied.
                if drawable.id not in self.drawable_groups:
                    self.drawable_groups[drawable.id] = drawable
                event.data["apply_to_group"] = (
                    drawable.id
                )  # add more context to the event with the group_id
                for elem in drawable.elements:
                    self.add(event, elem)

                return

        else:
            # single simple drawable
            self.drawable_cache.set_drawable_opsset(drawable)
            self.drawable_cache.drawables[drawable.id] = drawable

            target_drawable = getattr(event, "target_drawable", None)
            if target_drawable is not None:
                self.drawable_cache.set_drawable_opsset(target_drawable)
                self.drawable_cache.drawables[target_drawable.id] = target_drawable
                bind_target_opsset = getattr(event, "bind_target_opsset", None)
                if callable(bind_target_opsset):
                    bind_target_opsset(self.drawable_cache.get_drawable_opsset(target_drawable.id))

        # Initialize timeline for the new drawable
        if drawable.id not in self.object_timelines:
            self.object_timelines[drawable.id] = []

        target_drawable = getattr(event, "target_drawable", None)
        if target_drawable is not None and getattr(
            event, "replace_mobject_with_target_in_scene", False
        ):
            if event.end_time not in self.object_timelines[drawable.id]:
                self.object_timelines[drawable.id].append(event.end_time)
            if target_drawable.id not in self.object_timelines:
                self.object_timelines[target_drawable.id] = []
            if event.end_time not in self.object_timelines[target_drawable.id]:
                self.object_timelines[target_drawable.id].append(event.end_time)

        self.events.append((event, drawable.id))

        if event.type is AnimationEventType.CREATION:
            self.object_timelines[drawable.id].append(event.start_time)
        elif event.type is AnimationEventType.DELETION:
            # any object cannot be deleted without being created
            if len(self.object_timelines[drawable.id]) == 0:
                self.object_timelines[drawable.id].append(
                    event.start_time
                )  # assume created at the beginning of deletion event

            self.object_timelines[drawable.id].append(event.end_time)

    def get_active_objects(self, t: float):
        """
        Determines the list of object IDs that are active at a specific time point.

        Calculates object visibility by toggling their active status based on their timeline.
        An object becomes active when its timeline reaches a time point, and its status
        alternates with each subsequent time point.

        Args:
            t (float): The time point (in seconds) to check object activity.

        Returns:
            List[str]: A list of object IDs that are active at the given time point.
        """
        active_list: list[str] = []
        for object_id in self.object_timelines:
            active = False  # everything starts with blank screen
            for time in self.object_timelines[object_id]:
                if t >= time:
                    active = not active  # switch status
                else:
                    # time has increased beyond t
                    break
            if active:
                active_list.append(object_id)
        return active_list

    def get_drawable_opsset_at_scene_time(self, drawable_id: str, scene_time: float) -> OpsSet:
        """Preview the drawable's animated opsset at a specific scene time."""
        if drawable_id not in self.drawable_cache.drawables:
            return OpsSet(initial_set=[])
        _key_frames, drawable_events_mapping = self.find_key_frames()
        frame_index = int(round(scene_time * self.fps))
        event_and_progress = self.get_object_event_and_progress(
            drawable_id, frame_index, drawable_events_mapping
        )
        self.drawablegroup_frame_cache = {}
        self.drawablegroup_transformed_frame_cache = {}
        return self.get_animated_opsset_at_time(
            drawable_id=drawable_id,
            t=frame_index,
            event_and_progress=event_and_progress,
            drawable_events_mapping=drawable_events_mapping,
        )

    def snapshot_drawable_at_time(self, drawable: Drawable, scene_time: float) -> FrozenDrawable:
        """Create a frozen snapshot drawable representing a drawable at scene_time."""
        if drawable.id not in self.drawable_cache.drawables:
            return FrozenDrawable(
                drawable.draw(),
                stroke_style=drawable.stroke_style,
                sketch_style=drawable.sketch_style,
                fill_style=drawable.fill_style,
                glow_dot_hint=drawable.glow_dot_hint,
            )
        return FrozenDrawable(
            self.get_drawable_opsset_at_scene_time(drawable.id, scene_time),
            stroke_style=drawable.stroke_style,
            sketch_style=drawable.sketch_style,
            fill_style=drawable.fill_style,
            glow_dot_hint=drawable.glow_dot_hint,
        )

    def find_key_frames(self):
        """
        Find the key frames that we need to calculate for the animation
        Key frames are the frames where an object is created or deleted
        """
        event_drawable_ids = sorted(self.events, key=lambda x: x[0].start_time)
        events = [event for event, _ in event_drawable_ids]
        drawable_events_mapping: dict[
            str, list[AnimationEvent]
        ] = {}  # track for each drawable, what all events are applied
        for event, drawable_id in event_drawable_ids:
            if drawable_id not in drawable_events_mapping:
                drawable_events_mapping[drawable_id] = [event]
            else:
                drawable_events_mapping[drawable_id].append(event)
        key_frames = [event.start_time for event in events] + [event.end_time for event in events]
        key_frames = list(set(key_frames))
        key_frames.sort()
        return key_frames, drawable_events_mapping

    def _infer_default_length(self) -> float:
        event_end_times = [event.end_time for event, _drawable_id in self.events]
        audio_end_times = [track.end_time for track in self.audio_tracks]
        candidates = event_end_times + audio_end_times
        return max(candidates) if candidates else 1.0 / self.fps

    def get_object_event_and_progress(
        self, object_id: str, t: int, drawable_events_mapping: dict[str, list[AnimationEvent]]
    ) -> list[tuple[AnimationEvent, float]]:
        # OPTIMIZATION: Cache event_and_progress results per drawable per frame
        cache_key = (object_id, t)
        if cache_key in self._event_progress_cache:
            return self._event_progress_cache[cache_key]
        
        object_drawable: Drawable = self.drawable_cache.get_drawable(object_id)
        event_and_progress = []
        scene_time = t / self.fps
        for event in drawable_events_mapping.get(object_id, []):
            if object_drawable.glow_dot_hint:
                event.data["glowing_dot"] = object_drawable.glow_dot_hint
            if event.end_time <= scene_time:
                event_and_progress.append((event, 1.0))  # add completed event
            elif event.start_time <= scene_time:
                # event has started, but not completed yet
                if event.duration <= 0:
                    progress = 1.0
                else:
                    progress = np.clip(
                        (scene_time - event.start_time) / event.duration,
                        0,
                        1,
                    )
                event_and_progress.append((event, progress))
        
        self._event_progress_cache[cache_key] = event_and_progress
        return event_and_progress

    def _is_object_dynamic_at_time(
        self,
        object_id: str,
        scene_time: float,
        drawable_events_mapping: dict[str, list[AnimationEvent]],
    ) -> bool:
        for event in drawable_events_mapping.get(object_id, []):
            if event.start_time <= scene_time < event.end_time:
                return True
        return False

    def _build_static_frame_opsset(
        self,
        active_objects: list[str],
        t: int,
        drawable_events_mapping: dict[str, list[AnimationEvent]],
    ) -> tuple[OpsSet, list[str]]:
        static_frame_opsset = OpsSet(initial_set=[])
        dynamic_objects: list[str] = []
        scene_time = t / self.fps

        for object_id in active_objects:
            if self._is_object_dynamic_at_time(object_id, scene_time, drawable_events_mapping):
                dynamic_objects.append(object_id)
                continue

            event_and_progress = self.get_object_event_and_progress(
                object_id, t, drawable_events_mapping
            )
            static_frame_opsset.extend(
                self.get_animated_opsset_at_time(
                    drawable_id=object_id,
                    t=t,
                    event_and_progress=event_and_progress,
                    drawable_events_mapping=drawable_events_mapping,
                )
            )

        return static_frame_opsset, dynamic_objects

    def get_animated_opsset_at_time(
        self,
        drawable_id: str,
        t: int,
        event_and_progress: list[tuple[AnimationEvent, float]],
        drawable_events_mapping: dict[str, list[AnimationEvent]],
    ) -> OpsSet:
        """Optimized version that caches intermediate states and avoids O(N²) recursion."""
        # Check cache for final state
        if len(event_and_progress) == 0:
            return self.drawable_cache.get_drawable_opsset(drawable_id)
        if event_and_progress[-1][1] == 1:
            if self.drawable_cache.exists_in_cache(drawable_id, event_and_progress[-1][0].id):
                return self.drawable_cache.get_drawable_opsset(
                    drawable_id, event_and_progress[-1][0].id
                )

        # OPTIMIZED: Iterate and apply events directly instead of recursion
        # This is O(N) instead of O(N²)
        opsset = self.drawable_cache.get_drawable_opsset(drawable_id)
        
        for event_idx, (event, progress) in enumerate(event_and_progress):
            # Check intermediate cache first
            cache_key = (drawable_id, event_idx, t)
            if cache_key in self._animation_state_cache:
                opsset = self._animation_state_cache[cache_key]
                continue
            
            group_id = event.data.get("apply_to_group", None)
            if group_id is None:
                # Simple animation - apply directly
                new_opsset = event.apply(opsset, progress)
            else:
                # Group animation
                new_opsset = self._apply_group_animation(
                    drawable_id, event, progress, t, group_id, drawable_events_mapping
                )
            
            opsset = new_opsset
            
            # Cache intermediate state (only non-final states)
            if progress != 1:
                self._animation_state_cache[cache_key] = opsset

        # Cache final state
        if event_and_progress[-1][1] == 1 and not self.drawable_cache.exists_in_cache(
            drawable_id, event_and_progress[-1][0].id
        ):
            self.drawable_cache.set_drawable_event_opsset(
                drawable_id, event_and_progress[-1][0].id, opsset
            )

        return opsset

    def _apply_group_animation(
        self,
        drawable_id: str,
        event: AnimationEvent,
        progress: float,
        t: int,
        group_id: str,
        drawable_events_mapping: dict[str, list[AnimationEvent]],
    ) -> OpsSet:
        """Apply a group-level animation efficiently."""
        cachekey = f"{group_id}_{event.id}"
        if cachekey in self.drawablegroup_frame_cache:
            group_opsset = self.drawablegroup_frame_cache[cachekey]
        else:
            # Calculate the group opsset for group level animation
            group = self.drawable_groups[group_id]
            group_opsset = OpsSet(initial_set=[])
            for elem in group.elements:
                # Get all events for this element up to (but not including) current event
                elem_event_and_progress = self.get_object_event_and_progress(
                    elem.id, t, drawable_events_mapping
                )
                filtered_elem_events = []
                for elem_event, elem_progress in elem_event_and_progress:
                    if elem_event.id == event.id:
                        break
                    filtered_elem_events.append((elem_event, elem_progress))

                elem_opsset = self.get_animated_opsset_at_time(
                    elem.id, t, filtered_elem_events, drawable_events_mapping
                )
                elem_opsset.add_meta({"drawable_element_id": elem.id})
                group_opsset.extend(elem_opsset)

            self.drawablegroup_frame_cache[cachekey] = group_opsset

        transformed_cachekey = f"{cachekey}_{progress}"
        if transformed_cachekey not in self.drawablegroup_transformed_frame_cache:
            self.drawablegroup_transformed_frame_cache[transformed_cachekey] = event.apply(
                group_opsset, progress
            )
        group_opsset = self.drawablegroup_transformed_frame_cache[transformed_cachekey]

        # Filter for current drawable's opsset only
        return group_opsset.filter_by_meta_query("drawable_element_id", drawable_id)

    def create_event_timeline(self, max_length: float | None = None):
        """
        Creates a timeline of animation events and calculates the OpsSet for each frame.

        This method processes all drawable events, determines active objects at each frame,
        and generates a list of OpsSet operations representing the animation progression.

        Args:
            fps (int, optional): Frames per second for the animation. Defaults to 30.
            max_length (Optional[float], optional): Maximum duration of the animation. Defaults to None.
            verbose (bool, optional): If True, provides detailed logging during animation calculation. Defaults to False.

        Returns:
            List[OpsSet]: A list of OpsSet operations for each frame in the animation.
        """
        key_frames, drawable_events_mapping = self.find_key_frames()
        if max_length is None:
            max_length = self._infer_default_length()
        if not key_frames:
            key_frames = [0.0, max_length]
        else:
            key_frames.append(max_length)
        key_frame_indices = np.round(np.array(key_frames) * self.fps).astype(int).tolist()
        key_frame_index_set = set(key_frame_indices)
        scene_opsset_list: list[OpsSet] = []
        current_active_objects: list[str] = []
        current_dynamic_objects: list[str] = []
        current_static_frame_opsset = OpsSet(initial_set=[])

        # start calculating with a progress bar
        frame_count = int(np.round(max_length * self.fps))
        
        # OPTIMIZATION: Clear caches once before the loop instead of per-frame
        # Cache key: (drawable_id, event_idx, frame) -> OpsSet
        self._animation_state_cache = {}
        
        for t in tqdm(range(frame_count + 1), desc="Calculating animation frames..."):
            frame_opsset = OpsSet(initial_set=[])  # initialize with blank opsset, will add more

            # for each frame, update the current active objects if it is a keyframe
            if t in key_frame_index_set:
                current_active_objects = self.get_active_objects(t / self.fps)
                # Only clear caches at keyframes, not every frame
                self.drawablegroup_frame_cache = {}
                self.drawablegroup_transformed_frame_cache = {}
                self._animation_state_cache = {}  # Clear animation state cache at keyframes
                self._event_progress_cache = {}  # Clear event progress cache at keyframes
                self._frame_opsset_cache = {}  # Clear frame opsset cache at keyframes
                current_static_frame_opsset, current_dynamic_objects = (
                    self._build_static_frame_opsset(
                        current_active_objects,
                        t,
                        drawable_events_mapping,
                    )
                )

            # for each of these active objects, calculate what all events need to apply upto which progress
            frame_opsset.extend(current_static_frame_opsset)
            # OPTIMIZATION: Don't clear caches every frame - only at keyframes!
            # self.drawablegroup_frame_cache = {}
            # self.drawablegroup_transformed_frame_cache = {}
            for object_id in current_dynamic_objects:
                event_and_progress = self.get_object_event_and_progress(
                    object_id, t, drawable_events_mapping
                )

                # now we have all the events, so get the animated opsset
                animated_opsset = self.get_animated_opsset_at_time(
                    drawable_id=object_id,
                    t=t,
                    event_and_progress=event_and_progress,
                    drawable_events_mapping=drawable_events_mapping,
                )
                frame_opsset.extend(animated_opsset)
            scene_opsset_list.append(frame_opsset)  # create the list of ops at scene
        return scene_opsset_list

    def render_snapshot(
        self,
        output_path: str,  # must be an svg file path
        frame_in_seconds: float,  # the precise second index for the frame to render
        max_length: float | None = None,  # number of seconds to create the video for
    ) -> None:
        """
        Render a snapshot of the animation at a specific time point as an SVG file.

        This method is useful for debugging and inspecting the state of an animation
        at a precise moment. It generates a single frame from the animation timeline
        and saves it as an SVG image.

        Args:
            output_path (str): Path to the output SVG file.
            frame_in_seconds (float): The exact time point (in seconds) to render.
            max_length (Optional[float], optional): Total duration of the animation. Defaults to None.
        """
        opsset_list = self.create_event_timeline(max_length)  # create the animated video
        frame_index = int(
            np.clip(np.round(frame_in_seconds * self.fps), 0, len(opsset_list) - 1)
        )  # get the frame index
        frame_ops: OpsSet = opsset_list[frame_index]
        with cairo.SVGSurface(output_path, self.width, self.height) as surface:
            ctx = cairo.Context(surface)  # create cairo context

            # set the background color
            if self.background_color is not None:
                ctx.set_source_rgb(*self.background_color)
            ctx.paint()

            self.viewport.apply_to_context(ctx)
            frame_ops.render(
                ctx,
                render_context={
                    "scene_time": frame_index / self.fps,
                    "frame_index": frame_index,
                    "fps": self.fps,
                },
            )
            surface.finish()

    def render(self, output_path: str, max_length: float | None = None) -> None:
        """
        Render the animation as a video file.

        This method generates a video by creating a timeline of animation events
        and rendering each frame using Cairo graphics. The video is saved to the
        specified output path with the configured frame rate.

        Args:
            output_path (str): Path to save the output video file.
            max_length (Optional[float], optional): Maximum duration of the animation. Defaults to None.
        """
        # calculate the events
        resolved_max_length = (
            self._infer_default_length() if max_length is None else float(max_length)
        )
        opsset_list = self.create_event_timeline(resolved_max_length)
        output_file_ext = Path(output_path).suffix.lower().lstrip(".")
        if output_file_ext.lower() == "gif" and self.audio_tracks:
            msg = "Audio tracks are not supported when rendering GIF output"
            raise ValueError(msg)

        render_target = output_path
        temp_output_path: Path | None = None
        if output_file_ext.lower() != "gif" and self.audio_tracks:
            suffix = Path(output_path).suffix or ".mp4"
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as temp_file:
                temp_output_path = Path(temp_file.name)
            render_target = str(temp_output_path)

        if output_file_ext.lower() == "gif":
            tqdm_desc = "Rendering GIF..."
            frame_duration_ms = 1000 / self.fps  # duration per frame in milliseconds
            write_obj = imageio.get_writer(render_target, mode="I", duration=frame_duration_ms)
        else:
            tqdm_desc = "Rendering video..."
            ffmpeg_params = [
                "-preset",
                "ultrafast",
                "-tune",
                "animation",
            ]
            if self.render_quality == "fast":
                ffmpeg_params.extend(["-crf", "28"])
            elif self.render_quality == "medium":
                ffmpeg_params.extend(["-crf", "23"])
            else:  # high
                ffmpeg_params.extend(["-crf", "18"])
            write_obj = imageio.get_writer(
                render_target,
                fps=self.fps,
                codec="libx264",
                macro_block_size=1,
                ffmpeg_params=ffmpeg_params,
            )

        try:
            with write_obj as writer:
                surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, self.width, self.height)
                for frame_index, frame_ops in enumerate(tqdm(opsset_list, desc=tqdm_desc)):
                    ctx = cairo.Context(surface)  # create cairo context

                    # optional background
                    if self.background_color is not None:
                        ctx.set_source_rgb(*self.background_color)
                    ctx.paint()

                    self.viewport.apply_to_context(ctx)
                    frame_ops.render(
                        ctx,
                        render_context={
                            "scene_time": frame_index / self.fps,
                            "frame_index": frame_index,
                            "fps": self.fps,
                        },
                    )  # applies the operations to cairo context

                    frame_np = cairo_surface_to_numpy(surface)
                    writer.append_data(frame_np)  # type: ignore[attr-defined]  # type: ignore[attr-defined]

            if temp_output_path is not None:
                attach_audio_to_video(
                    video_path=str(temp_output_path),
                    output_path=output_path,
                    audio_tracks=self.audio_tracks,
                    duration=resolved_max_length,
                    fps=self.fps,
                )
        finally:
            if temp_output_path is not None and temp_output_path.exists():
                temp_output_path.unlink()
