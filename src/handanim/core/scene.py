from collections.abc import Generator, Iterable
from contextlib import contextmanager
import functools
import hashlib
import importlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import sys
from typing import TYPE_CHECKING, Any, Callable

import cairo
import imageio.v2 as imageio
import numpy as np
from tqdm.auto import tqdm

if TYPE_CHECKING:
    from .animation import AnimationEvent
    from .drawable import Drawable

from .audio import AudioTrack, VoiceoverTracker, attach_audio_to_video
from .animation import AnimationEvent, AnimationEventType, CompositeAnimationEvent
from .draw_ops import OpsSet
from .drawable import Drawable, DrawableCache, DrawableGroup, EmptyDrawable, FrozenDrawable
from .utils import cairo_surface_to_numpy
from .viewport import Viewport


def tts_speech(func: Callable) -> Callable:
    """
    Decorator for TTS speech synthesis methods.
    
    Wraps the provider's speech synthesis with caching and retry logic.
    The decorated method should take (speech: str, output_path: str, **kwargs) 
    and return the output path or None.
    
    Usage:
        @tts_speech
        def synthesize(self, speech: str, output_path: str, **kwargs) -> str | None:
            # Your TTS implementation
            return output_path
    """
    @functools.wraps(func)
    def wrapper(self, speech: str, output_path: str, **kwargs) -> str | None:
        # Check cache first
        if Path(output_path).exists():
            return output_path
        
        # Retry logic
        max_retries = 3
        for attempt in range(max_retries):
            try:
                result = func(self, speech, output_path, **kwargs)
                return result
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                import time
                time.sleep(2 ** attempt)
    
    return wrapper


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
        render_device: str = "cpu",
    ) -> None:
        """
        Initialize a Scene for animation rendering.

        Args:
            width: Width of the rendering surface in pixels.
            height: Height of the rendering surface in pixels.
            fps: Frames per second for video rendering.
            background_color: RGB color for scene background (values 0-1).
            viewport: Defines coordinate mapping between world and screen space.
            render_quality: Quality preset for rendering. One of "fast", "medium", "high".
            render_device: Device to use for video encoding. One of "cpu", "gpu", "cuda", "auto".
                - "cpu": Use CPU-based encoding (libx264)
                - "gpu": Use GPU-accelerated encoding (h264_nvenc for NVIDIA)
                - "cuda": Alias for "gpu"
                - "auto": Automatically detect and use GPU if available, fallback to CPU
        """
        self.width = width
        self.height = height
        self.fps = fps
        self.background_color = background_color
        self.render_quality = render_quality
        self.render_device = self._resolve_render_device(render_device)
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
        # Group tracking: stores duration and time sample for each scene group
        self._group_info: dict[str, dict[str, float]] = {}
        # Shared TTS progress bar for all speech synthesis
        self._tts_pbar: tqdm | None = None
        self._pending_tts_count = 0

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

    def _resolve_render_device(self, device: str) -> str:
        """
        Resolve the rendering device to use for video encoding.

        Args:
            device: Device specification string ("cpu", "gpu", "cuda", "auto")

        Returns:
            Resolved device type ("cpu" or "gpu")
        """
        if device in ("gpu", "cuda"):
            return "gpu"
        elif device == "cpu":
            return "cpu"
        elif device == "auto":
            # Auto-detect GPU availability
            if self._check_gpu_available():
                return "gpu"
            return "cpu"
        else:
            # Default to CPU for unknown values
            return "cpu"

    def _check_gpu_available(self) -> bool:
        """
        Check if GPU encoding is available (NVIDIA GPU with NVENC support).

        Returns:
            True if NVIDIA GPU is available for hardware-accelerated encoding
        """
        try:
            # Check for NVIDIA GPU via nvidia-smi
            result = subprocess.run(
                ["nvidia-smi"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            # nvidia-smi not found or failed
            return False

    def _ensure_ffmpeg_available(self) -> str | None:
        """
        Ensure an ffmpeg executable is available for rendering.

        Returns:
            Path to a usable ffmpeg executable, or None if one could not be resolved.
        """
        ffmpeg_path = shutil.which("ffmpeg")
        if ffmpeg_path:
            return ffmpeg_path

        try:
            imageio_ffmpeg = importlib.import_module("imageio_ffmpeg")
        except ImportError:
            try:
                subprocess.run(
                    [sys.executable, "-m", "pip", "install", "--quiet", "imageio-ffmpeg"],
                    check=True,
                    capture_output=True,
                    text=True,
                )
            except (OSError, subprocess.CalledProcessError):
                return None

            try:
                imageio_ffmpeg = importlib.import_module("imageio_ffmpeg")
            except ImportError:
                return None

        ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
        if ffmpeg_path:
            os.environ.setdefault("IMAGEIO_FFMPEG_EXE", ffmpeg_path)
            return ffmpeg_path
        return None

    def _gpu_encoder_is_available(self) -> bool:
        """
        Check whether NVENC encoding can actually be used.

        A CUDA/NVIDIA device alone is not enough; ffmpeg also needs to expose
        the h264_nvenc encoder.
        """
        if not self._check_gpu_available():
            return False

        ffmpeg_path = self._ensure_ffmpeg_available()
        if ffmpeg_path is None:
            return False

        probe_path = ""
        try:
            with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as probe_file:
                probe_path = probe_file.name

            result = subprocess.run(
                [
                    ffmpeg_path,
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-f",
                    "lavfi",
                    "-i",
                    "color=c=black:s=16x16:d=0.1",
                    "-frames:v",
                    "1",
                    "-c:v",
                    "h264_nvenc",
                    "-pix_fmt",
                    "yuv420p",
                    probe_path,
                ],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return False
        finally:
            try:
                Path(probe_path).unlink(missing_ok=True)
            except Exception:
                pass

        return result.returncode == 0

    def _tqdm_bar(self, iterable, *, desc: str, total: int | None = None):
        """Return a modern tqdm iterator with a compact, responsive bar."""
        return tqdm(
            iterable,
            desc=desc,
            total=total,
            dynamic_ncols=True,
            colour="cyan",
            smoothing=0.15,
            mininterval=0.2,
            bar_format="{l_bar}{bar:24}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]",
            unit="f",
            unit_scale=True,
        )

    def _init_tts_pbar(self, total: int):
        """Initialize the shared TTS progress bar."""
        if self._tts_pbar is None:
            self._tts_pbar = tqdm(
                total=total,
                desc="Synthesizing speech",
                dynamic_ncols=True,
                colour="magenta",
                bar_format="{l_bar}{bar:24}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]",
            )
            self._pending_tts_count = total
        else:
            # If bar already exists, just increment the pending count
            self._pending_tts_count += 1
            self._tts_pbar.total = self._pending_tts_count

    def _update_tts_pbar(self):
        """Update the shared TTS progress bar."""
        if self._tts_pbar is not None:
            self._tts_pbar.update(1)
            self._pending_tts_count -= 1
            if self._pending_tts_count <= 0:
                self._tts_pbar.close()
                self._tts_pbar = None

    def _close_tts_pbar(self):
        """Close the shared TTS progress bar."""
        if self._tts_pbar is not None:
            self._tts_pbar.close()
            self._tts_pbar = None
            self._pending_tts_count = 0

    @contextmanager
    def _tqdm_step(self, desc: str, *, colour: str = "green"):
        """Show progress for a single blocking step such as TTS or muxing."""
        with tqdm(
            desc=desc,
            total=1,
            dynamic_ncols=True,
            colour=colour,
            bar_format="{l_bar}{bar:24}| {n_fmt}/{total_fmt} [{elapsed}]",
        ) as pbar:
            try:
                yield
            finally:
                pbar.update(1)

    def _get_encoder_codec_and_params(self) -> tuple[str, list[str]]:
        """
        Get the appropriate encoder codec and FFmpeg parameters based on render_device.

        Returns:
            Tuple of (codec_name, ffmpeg_params_list)
        """
        if self.render_device == "gpu":
            # Use NVIDIA NVENC hardware encoder
            codec = "h264_nvenc"
            ffmpeg_params = [
                "-preset",
                "p1",  # Fastest NVENC preset
                "-tune",
                "ll",  # Low-latency / speed-oriented tuning
                "-threads",
                "0",  # Let encoder decide (GPU doesn't use CPU threads the same way)
            ]
            # Add quality-specific params for NVENC
            if self.render_quality == "fast":
                ffmpeg_params.extend(["-rc", "vbr", "-cq", "35"])
            elif self.render_quality == "medium":
                ffmpeg_params.extend(["-rc", "vbr", "-cq", "28"])
            else:  # high
                ffmpeg_params.extend(["-rc", "vbr", "-cq", "20"])
        else:
            # Use CPU-based libx264 encoder
            codec = "libx264"
            ffmpeg_params = [
                "-preset",
                "ultrafast",
                "-tune",
                "animation",
                "-threads",
                "0",  # Will be overridden in render() if specified
            ]
            if self.render_quality == "fast":
                ffmpeg_params.extend(["-crf", "28"])
            elif self.render_quality == "medium":
                ffmpeg_params.extend(["-crf", "23"])
            else:  # high
                ffmpeg_params.extend(["-crf", "18"])

        return codec, ffmpeg_params

    def _iter_event_timeline(self, max_length: float | None = None):
        """Yield combined frame OpsSet objects one at a time to avoid holding the full timeline in memory."""
        for static_frame_opsset, dynamic_frame_opsset in self._iter_frame_layers(max_length):
            if dynamic_frame_opsset is None:
                yield static_frame_opsset
                continue

            frame_opsset = static_frame_opsset.clone()
            frame_opsset.extend(dynamic_frame_opsset)
            yield frame_opsset

    def _iter_frame_layers(self, max_length: float | None = None):
        """Yield static and dynamic frame layers separately so rendering can reuse the static layer."""
        key_frames, drawable_events_mapping = self.find_key_frames()
        if max_length is None:
            max_length = self._infer_default_length()
        if not key_frames:
            key_frames = [0.0, max_length]
        else:
            key_frames.append(max_length)
        key_frame_indices = np.round(np.array(key_frames) * self.fps).astype(int).tolist()
        key_frame_index_set = set(key_frame_indices)
        current_active_objects: list[str] = []
        current_dynamic_objects: list[str] = []
        current_static_frame_opsset = OpsSet(initial_set=[])

        # OPTIMIZATION: Clear caches once before the loop instead of per-frame
        # Cache key: (drawable_id, event_idx, frame) -> OpsSet
        self._animation_state_cache = {}

        frame_count = int(np.round(max_length * self.fps))
        for t in range(frame_count + 1):
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

            if not current_dynamic_objects:
                yield current_static_frame_opsset, None
                continue

            dynamic_frame_opsset = OpsSet(initial_set=[])

            # for each of these active objects, calculate what all events need to apply upto which progress
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
                dynamic_frame_opsset.extend(animated_opsset)
            yield current_static_frame_opsset, dynamic_frame_opsset

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

    @contextmanager
    def group(
        self,
        tts_provider: Any | None = None,
        speech: str | None = None,
        audio_path: str | None = None,
        **tts_kwargs,
    ) -> Generator[AudioTrack | None, None, None]:
        """
        Context manager for grouping multiple animations with a single audio track.

        All animations added within this context will share the same audio.
        The timeline won't auto-advance until the group exits.

        Args:
            tts_provider: TTS provider instance with a decorated speech synthesis method.
            speech: Text to synthesize when using tts_provider.
            audio_path: Path to existing audio file (alternative to tts_provider + speech).
            **tts_kwargs: Additional keyword arguments passed to the TTS provider.

        Yields:
            AudioTrack if audio was added, None otherwise.

        Example:
            >>> # Client decorates their provider's method with @tts_speech
            >>> class MyTTS:
            ...     @tts_speech
            ...     def synthesize(self, speech: str, output_path: str, **kwargs) -> str:
            ...         # Implementation
            ...         return output_path
            >>> 
            >>> with scene.group(tts_provider=MyTTS(), speech="Welcome to the demo"):
            ...     scene.add(SketchAnimation(start_time=0.0, duration=1.0), title)
        """
        group_start_cursor = self.timeline_cursor
        self._in_group = True
        added_track = None
        group_events_before = len(self.events)
        group_audio_tracks_before = len(self.audio_tracks)
        group_id = f"group_{len(self._group_info)}"

        # Handle audio synthesis at group start
        if audio_path is not None or (tts_provider is not None and speech is not None):
            resolved_audio_path = audio_path

            if resolved_audio_path is None and tts_provider is not None and speech is not None:
                # Synthesize audio using TTS provider's decorated method
                if not hasattr(self, '_audio_temp_dir'):
                    self._audio_temp_dir = Path(tempfile.gettempdir()) / f"handanim_scene_{id(self)}"
                self._audio_temp_dir.mkdir(parents=True, exist_ok=True)

                speech_hash = hashlib.md5(speech.encode()).hexdigest()[:8]
                time_marker = f"{group_start_cursor:.2f}"
                audio_filename = f"group_{time_marker}_{speech_hash}.mp3"
                resolved_audio_path = str(self._audio_temp_dir / audio_filename)

                # Use shared TTS progress bar
                self._init_tts_pbar(1)
                # Call the provider's decorated speech synthesis method
                if hasattr(tts_provider, 'synthesize'):
                    synthesized_path = tts_provider.synthesize(speech, resolved_audio_path, **tts_kwargs)
                    if synthesized_path:
                        resolved_audio_path = synthesized_path
                else:
                    msg = f"TTS provider must have a 'synthesize' method decorated with @tts_speech"
                    raise AttributeError(msg)
                self._update_tts_pbar()

            # Add audio track at group start
            track = AudioTrack(
                path=resolved_audio_path,
                start_time=group_start_cursor,
                volume=tts_kwargs.get('volume', 1.0),
            )
            self.audio_tracks.append(track)
            added_track = track

        try:
            yield added_track
        finally:
            self._in_group = False
            
            # Get events added during this group
            group_events = self.events[group_events_before:]
            group_audio_tracks = self.audio_tracks[group_audio_tracks_before:]
            group_end_times: list[float] = []
            if group_events:
                group_visual_end = max(event[0].end_time for event in group_events)
                group_end_times.append(group_visual_end)
            if group_audio_tracks:
                group_audio_end = max(track.end_time for track in group_audio_tracks)
                group_end_times.append(group_audio_end)
                if group_events and group_audio_end > group_visual_end:
                    self._hold_group_visuals_until_audio_end(group_events, group_audio_end)
            
            # Calculate group duration and time sample
            group_duration = 0.0
            if group_end_times:
                group_end = max(group_end_times)
                group_duration = group_end - group_start_cursor
                self.timeline_cursor = max(self.timeline_cursor, group_end)
            
            # Store group information
            self._group_info[group_id] = {
                "start_time": group_start_cursor,
                "end_time": group_end if group_end_times else group_start_cursor,
                "duration": group_duration,
                "time_sample": group_start_cursor,
                "has_audio": added_track is not None,
            }

    def _hold_group_visuals_until_audio_end(
        self,
        group_events: list[tuple[AnimationEvent, str]],
        group_audio_end: float,
    ) -> None:
        """Keep every drawable touched by the group visible until its audio ends."""
        tolerance = max(1.0 / max(self.fps, 1), 1e-6)
        # Cache the ORIGINAL end_time per event.id so that when a single event
        # is shared across multiple drawables (e.g. a FadeOutAnimation applied
        # to a parallel DrawableGroup), subsequent iterations can still locate
        # the stale entry in each element's object_timelines after the event
        # itself has already been shifted.
        original_end_times: dict[str, float] = {}

        for event, drawable_id in group_events:
            if event.type is not AnimationEventType.DELETION:
                continue

            if event.id in original_end_times:
                old_end_time = original_end_times[event.id]
            else:
                old_end_time = event.end_time
                if old_end_time >= group_audio_end - tolerance:
                    continue
                original_end_times[event.id] = old_end_time
                duration = max(event.duration, 0.0)
                event.start_time = max(group_audio_end - duration, 0.0)
                event.end_time = group_audio_end
                event.duration = event.end_time - event.start_time

            timeline = self.object_timelines.get(drawable_id)
            if timeline is None:
                continue
            for index, time in enumerate(timeline):
                if abs(time - old_end_time) <= tolerance:
                    timeline[index] = group_audio_end
                    break
            timeline.sort()

    def add(
        self,
        event: AnimationEvent | None = None,
        drawable: Drawable | None = None,
        tts_provider: Any | None = None,
        speech: str | None = None,
        audio_path: str | None = None,
        **tts_kwargs,
    ) -> None:
        """
        Adds an animation event to a drawable primitive in the scene, and optionally adds TTS audio.

        Handles different scenarios including:
        - Composite animation events (recursively adding sub-events)
        - Drawable groups with parallel or sequential event distribution
        - Single event and drawable cases
        - TTS audio synthesis and addition (if tts_provider and speech provided)

        Manages event tracking, drawable caching, and object timelines.

        Args:
            event: The animation event to be added. If None and audio_path/tts_provider provided, only adds audio.
            drawable: The drawable primitive to apply the event to.
            tts_provider: TTS provider instance with a decorated speech synthesis method.
            speech: Text to synthesize when using tts_provider.
            audio_path: Path to an existing audio file (alternative to tts_provider + speech).
            **tts_kwargs: Additional keyword arguments passed to the TTS provider.

        Examples:
            >>> # Add animation only
            >>> scene.add(SketchAnimation(start_time=0.0, duration=1.0), my_text)

            >>> # Add TTS audio only
            >>> scene.add(tts_provider=MyTTS(), speech="Hello world")

            >>> # Add both animation and TTS
            >>> scene.add(SketchAnimation(start_time=0.0, duration=1.0), my_text, tts_provider=MyTTS(), speech="Hello")
        """
        # Handle TTS audio synthesis
        if audio_path is not None or (tts_provider is not None and speech is not None):
            resolved_audio_path = audio_path

            if resolved_audio_path is None and tts_provider is not None and speech is not None:
                # Synthesize audio using TTS provider's decorated method
                if not hasattr(self, '_audio_temp_dir'):
                    self._audio_temp_dir = Path(tempfile.gettempdir()) / f"handanim_scene_{id(self)}"
                self._audio_temp_dir.mkdir(parents=True, exist_ok=True)

                speech_hash = hashlib.md5(speech.encode()).hexdigest()[:8]
                # Use event start_time or timeline cursor for unique filename per scene position
                if event is not None:
                    time_marker = f"{event.start_time:.2f}"
                else:
                    time_marker = f"{self.timeline_cursor:.2f}"
                audio_filename = f"tts_{time_marker}_{speech_hash}.mp3"
                resolved_audio_path = str(self._audio_temp_dir / audio_filename)

                # Use shared TTS progress bar
                self._init_tts_pbar(1)
                # Call the provider's decorated speech synthesis method
                if hasattr(tts_provider, 'synthesize'):
                    synthesized_path = tts_provider.synthesize(speech, resolved_audio_path, **tts_kwargs)
                    if synthesized_path:
                        resolved_audio_path = synthesized_path
                else:
                    msg = f"TTS provider must have a 'synthesize' method decorated with @tts_speech"
                    raise AttributeError(msg)
                self._update_tts_pbar()

            # Add audio track to scene
            if event is not None:
                start_time = event.start_time
            else:
                start_time = self.timeline_cursor

            track = AudioTrack(
                path=resolved_audio_path,
                start_time=start_time,
                volume=tts_kwargs.get('volume', 1.0),
            )
            self.audio_tracks.append(track)

            # Auto-advance timeline to wait for audio to finish (prevents overlapping)
            # Only advance if we're not in a grouped context
            if not getattr(self, '_in_group', False):
                self.timeline_cursor = max(self.timeline_cursor, track.end_time)

        # If no event provided, just return after handling audio
        if event is None:
            return

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

    def get_group_info(self) -> dict[str, dict[str, float]]:
        """
        Get information about all scene groups including duration and time samples.

        Returns:
            Dictionary mapping group_id to group information containing:
            - start_time: When the group starts
            - end_time: When the group ends
            - duration: Length of the group in seconds
            - time_sample: The time sample (start time) of the group
            - has_audio: Whether the group has audio
        """
        return self._group_info.copy()

    def get_total_duration(self) -> float:
        """
        Auto-calculate the total duration of the video based on groups and events.

        Returns:
            Total duration in seconds
        """
        if self._group_info:
            # Use group end times if groups exist
            group_end_times = [info["end_time"] for info in self._group_info.values()]
            return max(group_end_times) if group_end_times else self._infer_default_length()
        return self._infer_default_length()

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
        return list(
            self._tqdm_bar(
                self._iter_event_timeline(max_length),
                desc="Calculating animation frames...",
                total=int(np.round((self.get_total_duration() if max_length is None else float(max_length)) * self.fps)) + 1,
            )
        )

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

    def render(
        self,
        output_path: str,
        max_length: float | None = None,
        threads: int = 0,
    ) -> None:
        """
        Render the animation as a video file.

        This method generates a video by creating a timeline of animation events
        and rendering each frame using Cairo graphics. The video is saved to the
        specified output path with the configured frame rate.

        Args:
            output_path (str): Path to save the output video file.
            max_length (Optional[float], optional): Maximum duration of the animation. Defaults to None.
            threads (int, optional): Number of threads for ffmpeg encoding. Use 0 for all cores. Defaults to 0.
        """
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        # Close any remaining TTS progress bar before rendering
        self._close_tts_pbar()
        # calculate the events
        resolved_max_length = (
            self.get_total_duration() if max_length is None else float(max_length)
        )
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

        with self._tqdm_step("Preparing render...", colour="blue"):
            if output_file_ext.lower() == "gif":
                tqdm_desc = "Rendering GIF..."
                frame_duration_ms = 1000 / self.fps  # duration per frame in milliseconds
                write_obj = imageio.get_writer(render_target, mode="I", duration=frame_duration_ms)
            else:
                effective_render_device = self.render_device
                tqdm_desc = "Rendering video..."
                if effective_render_device == "gpu" and self._gpu_encoder_is_available():
                    tqdm_desc += " (GPU accelerated)"
                elif effective_render_device == "gpu":
                    effective_render_device = "cpu"
                    tqdm_desc += " (GPU unavailable, falling back to CPU)"

                # Get encoder codec and params based on render_device
                original_render_device = self.render_device
                self.render_device = effective_render_device
                codec, ffmpeg_params = self._get_encoder_codec_and_params()
                self.render_device = original_render_device

                # Override threads parameter if not using GPU (GPU doesn't use CPU threads the same way)
                if effective_render_device == "gpu":
                    # Find and replace the threads value in ffmpeg_params
                    for i, param in enumerate(ffmpeg_params):
                        if param == "-threads" and i + 1 < len(ffmpeg_params):
                            ffmpeg_params[i + 1] = "0"  # Let GPU encoder decide
                            break
                elif threads > 0:
                    # Override threads for CPU encoding
                    for i, param in enumerate(ffmpeg_params):
                        if param == "-threads" and i + 1 < len(ffmpeg_params):
                            ffmpeg_params[i + 1] = str(threads)
                            break

                write_obj = imageio.get_writer(
                    render_target,
                    fps=self.fps,
                    codec=codec,
                    macro_block_size=1,
                    ffmpeg_params=ffmpeg_params,
                )

        try:
            with write_obj as writer:
                static_surface: cairo.ImageSurface | None = None
                static_surface_np = None
                last_static_opsset: OpsSet | None = None
                frame_total = int(np.round(resolved_max_length * self.fps)) + 1
                frame_iter = self._iter_frame_layers(resolved_max_length)
                for frame_index, (static_frame_ops, dynamic_frame_ops) in enumerate(
                    self._tqdm_bar(frame_iter, desc=tqdm_desc, total=frame_total)
                ):
                    if frame_index == 0:
                        tqdm.write("Rendering first frame...")
                    if static_surface is None or static_frame_ops is not last_static_opsset:
                        static_surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, self.width, self.height)
                        static_ctx = cairo.Context(static_surface)

                        if self.background_color is not None:
                            static_ctx.set_source_rgb(*self.background_color)
                        static_ctx.paint()

                        self.viewport.apply_to_context(static_ctx)
                        static_frame_ops.render(
                            static_ctx,
                            render_context={
                                "scene_time": frame_index / self.fps,
                                "frame_index": frame_index,
                                "fps": self.fps,
                            },
                        )
                        static_surface_np = cairo_surface_to_numpy(static_surface)
                        last_static_opsset = static_frame_ops

                    if dynamic_frame_ops is None:
                        writer.append_data(static_surface_np)  # type: ignore[attr-defined]
                        continue

                    frame_surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, self.width, self.height)
                    frame_ctx = cairo.Context(frame_surface)
                    frame_ctx.set_source_surface(static_surface, 0, 0)
                    frame_ctx.paint()

                    self.viewport.apply_to_context(frame_ctx)
                    dynamic_frame_ops.render(
                        frame_ctx,
                        render_context={
                            "scene_time": frame_index / self.fps,
                            "frame_index": frame_index,
                            "fps": self.fps,
                        },
                    )

                    frame_np = cairo_surface_to_numpy(frame_surface)
                    writer.append_data(frame_np)  # type: ignore[attr-defined]

            if temp_output_path is not None:
                # Show progress for audio attachment
                with tqdm(
                    desc="Attaching audio...",
                    total=2,
                    dynamic_ncols=True,
                    colour="yellow",
                    bar_format="{l_bar}{bar:24}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]",
                ) as pbar:
                    pbar.set_postfix_str("starting ffmpeg")
                    pbar.update(1)
                    attach_audio_to_video(
                        video_path=str(temp_output_path),
                        output_path=output_path,
                        audio_tracks=self.audio_tracks,
                        duration=resolved_max_length,
                        fps=self.fps,
                        threads=threads,
                    )
                    pbar.set_postfix_str("done")
                    pbar.update(1)
        finally:
            if temp_output_path is not None and temp_output_path.exists():
                temp_output_path.unlink()
