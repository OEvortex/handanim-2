from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
import subprocess
import shutil
import importlib
from typing import Any

from moviepy import AudioFileClip

_BOOKMARK_PATTERN = re.compile(
    r"<bookmark\s+(?:mark|name)\s*=\s*['\"](?P<mark>[^'\"]+)['\"]\s*/>"
)
_AUDIO_DURATION_CACHE: dict[str, float] = {}


def _ensure_ffmpeg_available() -> str | None:
    """
    Ensure an ffmpeg executable is available for audio attachment.
    
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
                ["python", "-m", "pip", "install", "--quiet", "imageio-ffmpeg"],
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


def resolve_audio_path(path: str) -> str:
    resolved = Path(path).expanduser().resolve()
    if not resolved.exists():
        msg = f"Audio file does not exist: {path}"
        raise FileNotFoundError(msg)
    return str(resolved)


def remove_bookmarks(text: str) -> str:
    return _BOOKMARK_PATTERN.sub("", text)


def get_audio_duration(path: str) -> float:
    resolved_path = resolve_audio_path(path)
    if resolved_path in _AUDIO_DURATION_CACHE:
        return _AUDIO_DURATION_CACHE[resolved_path]

    clip = AudioFileClip(resolved_path)
    try:
        duration = float(clip.duration or 0.0)
    finally:
        clip.close()

    _AUDIO_DURATION_CACHE[resolved_path] = duration
    return duration


@dataclass(slots=True)
class AudioTrack:
    path: str
    start_time: float = 0.0
    volume: float = 1.0
    clip_start: float = 0.0
    clip_end: float | None = None

    def __post_init__(self) -> None:
        self.path = resolve_audio_path(self.path)
        self.start_time = float(self.start_time)
        self.volume = float(self.volume)
        self.clip_start = float(self.clip_start)
        self.clip_end = float(self.clip_end) if self.clip_end is not None else None

        if self.start_time < 0:
            msg = "Audio track start_time must be >= 0"
            raise ValueError(msg)
        if self.volume < 0:
            msg = "Audio track volume must be >= 0"
            raise ValueError(msg)
        if self.clip_start < 0:
            msg = "Audio track clip_start must be >= 0"
            raise ValueError(msg)

        source_duration = get_audio_duration(self.path)
        effective_end = source_duration if self.clip_end is None else self.clip_end
        if effective_end <= self.clip_start:
            msg = "Audio track clip_end must be greater than clip_start"
            raise ValueError(msg)
        if effective_end > source_duration:
            msg = "Audio track clip_end cannot exceed source duration"
            raise ValueError(msg)

    @property
    def duration(self) -> float:
        effective_end = get_audio_duration(self.path) if self.clip_end is None else self.clip_end
        return float(effective_end - self.clip_start)

    @property
    def end_time(self) -> float:
        return self.start_time + self.duration

    def to_moviepy_clip(self) -> Any:
        clip = AudioFileClip(self.path)
        effective_end = clip.duration if self.clip_end is None else self.clip_end
        if self.clip_start > 0 or self.clip_end is not None:
            if hasattr(clip, "subclipped"):
                clip = clip.subclipped(self.clip_start, effective_end)
            else:
                clip = clip.subclip(self.clip_start, effective_end)
        if self.volume != 1.0:
            if hasattr(clip, "with_volume_scaled"):
                clip = clip.with_volume_scaled(self.volume)
            else:
                clip = clip.volumex(self.volume)
        if hasattr(clip, "with_start"):
            clip = clip.with_start(self.start_time)
        else:
            clip = clip.set_start(self.start_time)
        return clip


class VoiceoverTracker:
    def __init__(self, audio_track: AudioTrack, text: str | None = None) -> None:
        self.audio_track = audio_track
        self.path = audio_track.path
        self.start_time = audio_track.start_time
        self.duration = audio_track.duration
        self.end_time = audio_track.end_time
        self.text = text
        self.content = remove_bookmarks(text) if text is not None else None
        self.bookmark_times = self._build_bookmark_times(text)

    def _build_bookmark_times(self, text: str | None) -> dict[str, float]:
        if not text:
            return {}

        bookmark_positions: dict[str, int] = {}
        plain_length = 0
        last_index = 0
        for match in _BOOKMARK_PATTERN.finditer(text):
            plain_length += len(text[last_index : match.start()])
            mark = match.group("mark")
            if mark in bookmark_positions:
                msg = f"Duplicate bookmark '{mark}' in voiceover text"
                raise ValueError(msg)
            bookmark_positions[mark] = plain_length
            last_index = match.end()
        plain_length += len(text[last_index:])

        if plain_length <= 0:
            return dict.fromkeys(bookmark_positions, self.start_time)

        return {
            mark: self.start_time + (position / plain_length) * self.duration
            for mark, position in bookmark_positions.items()
        }

    def bookmark_time(self, mark: str) -> float:
        if mark not in self.bookmark_times:
            msg = f"Unknown voiceover bookmark '{mark}'"
            raise KeyError(msg)
        return self.bookmark_times[mark]

    def time_until_bookmark(
        self,
        mark: str,
        from_time: float | None = None,
        limit: float | None = None,
        buff: float = 0.0,
    ) -> float:
        if from_time is None:
            from_time = self.start_time
        duration = max(self.bookmark_time(mark) - float(from_time) + float(buff), 0.0)
        if limit is not None:
            duration = min(duration, float(limit))
        return duration

    def get_remaining_duration(self, from_time: float | None = None, buff: float = 0.0) -> float:
        if from_time is None:
            from_time = self.start_time
        return max(self.end_time - float(from_time) + float(buff), 0.0)


def attach_audio_to_video(
    video_path: str,
    output_path: str,
    audio_tracks: list[AudioTrack],
    duration: float,
    fps: int,
    threads: int = 0,
) -> None:
    """Attach audio tracks to video using direct ffmpeg (fast, no video re-encoding)."""
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    if not audio_tracks:
        # No audio, just copy video
        shutil.copy(video_path, output_path)
        return

    def _format_filter_float(value: float) -> str:
        return f"{float(value):.6f}".rstrip("0").rstrip(".")

    def _build_audio_filter() -> str:
        filter_parts: list[str] = []
        audio_labels: list[str] = []

        for index, track in enumerate(audio_tracks):
            input_index = index + 1
            label = f"a{index}"
            filters = []
            trim_parts = [f"start={_format_filter_float(track.clip_start)}"]
            if track.clip_end is not None:
                trim_parts.append(f"end={_format_filter_float(track.clip_end)}")
            filters.append(f"atrim={':'.join(trim_parts)}")
            filters.append("asetpts=PTS-STARTPTS")
            if track.volume != 1.0:
                filters.append(f"volume={_format_filter_float(track.volume)}")
            delay_ms = max(int(round(track.start_time * 1000)), 0)
            if delay_ms:
                filters.append(f"adelay=delays={delay_ms}:all=1")
            filter_parts.append(f"[{input_index}:a]{','.join(filters)}[{label}]")
            audio_labels.append(f"[{label}]")

        duration_filter = f"atrim=end={_format_filter_float(duration)},asetpts=PTS-STARTPTS"
        if len(audio_labels) == 1:
            filter_parts.append(f"{audio_labels[0]}{duration_filter}[aout]")
        else:
            joined_labels = "".join(audio_labels)
            filter_parts.append(
                f"{joined_labels}amix=inputs={len(audio_labels)}:"
                f"duration=longest:normalize=0,{duration_filter}[aout]"
            )

        return ";".join(filter_parts)

    # Try to use ffmpeg for fast audio attachment (no video re-encoding)
    ffmpeg_path = _ensure_ffmpeg_available()
    
    if ffmpeg_path:
        cmd = [
            ffmpeg_path,
            "-y",
            "-i",
            video_path,
        ]
        for track in audio_tracks:
            cmd.extend(["-i", track.path])

        cmd.extend(
            [
                "-filter_complex",
                _build_audio_filter(),
                "-map",
                "0:v:0",
                "-map",
                "[aout]",
                "-c:v",
                "copy",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-movflags",
                "+faststart",
                "-t",
                _format_filter_float(duration),
            ]
        )

        if threads > 0:
            cmd.extend(["-threads", str(threads)])

        cmd.append(output_path)
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        return

    msg = "ffmpeg is required to attach audio without re-encoding the rendered video"
    raise RuntimeError(msg)
