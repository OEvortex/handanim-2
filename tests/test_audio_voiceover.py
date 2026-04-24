import wave
from pathlib import Path

import pytest

from handanim.animations import FadeOutAnimation, SketchAnimation
import handanim.core.scene as scene_module
from handanim.core import AudioTrack, Scene
from handanim.core.drawable import DrawableGroup
from handanim.primitives import Text


def _write_test_wav(path: Path, duration_seconds: float, sample_rate: int = 8_000) -> None:
    frame_count = int(duration_seconds * sample_rate)
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(b"\x00\x00" * frame_count)


def test_audio_track_duration_and_trim(tmp_path) -> None:
    audio_path = tmp_path / "voice.wav"
    _write_test_wav(audio_path, duration_seconds=2.0)

    track = AudioTrack(path=str(audio_path), start_time=1.5, clip_start=0.25, clip_end=1.25)

    assert track.duration == pytest.approx(1.0)
    assert track.end_time == pytest.approx(2.5)


def test_voiceover_tracker_interpolates_bookmarks(tmp_path) -> None:
    audio_path = tmp_path / "voice.wav"
    _write_test_wav(audio_path, duration_seconds=2.0)

    scene = Scene(fps=10)
    tracker = scene.add_voiceover(
        path=str(audio_path),
        text="aa<bookmark mark='A'/>aa<bookmark mark='B'/>aa",
        start_time=1.0,
    )

    assert tracker.start_time == pytest.approx(1.0)
    assert tracker.end_time == pytest.approx(3.0)
    assert tracker.bookmark_time("A") == pytest.approx(1.6667, abs=0.05)
    assert tracker.bookmark_time("B") == pytest.approx(2.3333, abs=0.05)
    assert tracker.time_until_bookmark("B", from_time=tracker.bookmark_time("A")) == pytest.approx(
        0.6667, abs=0.05
    )
    assert tracker.get_remaining_duration(from_time=tracker.bookmark_time("B")) == pytest.approx(
        0.6667, abs=0.05
    )


def test_voiceover_context_advances_cursor(tmp_path) -> None:
    audio_path = tmp_path / "voice.wav"
    _write_test_wav(audio_path, duration_seconds=1.25)

    scene = Scene(fps=8)
    with scene.voiceover(path=str(audio_path), text="Testing") as tracker:
        assert tracker.start_time == pytest.approx(0.0)

    assert scene.timeline_cursor == pytest.approx(1.25)
    blank_timeline = scene.create_event_timeline()
    assert len(blank_timeline) == 11


def test_group_cursor_extends_to_audio_added_inside_group(tmp_path) -> None:
    audio_path = tmp_path / "group_audio.wav"
    _write_test_wav(audio_path, duration_seconds=1.25)

    scene = Scene(fps=8)
    title = Text("Hello", position=(0, 0))

    with scene.group():
        scene.add(SketchAnimation(start_time=0.0, duration=0.5), title)
        scene.add_audio(str(audio_path))

    assert scene.timeline_cursor == pytest.approx(1.25)


def test_group_keeps_last_visual_active_until_audio_ends(tmp_path) -> None:
    audio_path = tmp_path / "group_audio.wav"
    _write_test_wav(audio_path, duration_seconds=2.0)

    scene = Scene(fps=8)
    title = Text("Hello", position=(0, 0))
    subtitle = Text("World", position=(0, 20))

    with scene.group():
        scene.add(SketchAnimation(start_time=0.0, duration=0.1), title)
        title_fade_out = FadeOutAnimation(start_time=0.5, duration=0.5)
        scene.add(title_fade_out, title)
        scene.add(SketchAnimation(start_time=1.0, duration=0.1), subtitle)
        subtitle_fade_out = FadeOutAnimation(start_time=1.2, duration=0.2)
        scene.add(subtitle_fade_out, subtitle)
        scene.add_audio(str(audio_path))

    assert title_fade_out.start_time == pytest.approx(1.5)
    assert title_fade_out.end_time == pytest.approx(2.0)
    assert subtitle_fade_out.start_time == pytest.approx(1.8)
    assert subtitle_fade_out.end_time == pytest.approx(2.0)
    assert title.id in scene.get_active_objects(0.25)
    assert title.id in scene.get_active_objects(1.25)
    assert subtitle.id in scene.get_active_objects(1.6)
    assert title.id not in scene.get_active_objects(2.0)
    assert subtitle.id not in scene.get_active_objects(2.0)


def test_group_shifts_fade_out_for_parallel_drawable_group(tmp_path) -> None:
    audio_path = tmp_path / "group_audio.wav"
    _write_test_wav(audio_path, duration_seconds=2.0)

    scene = Scene(fps=8)
    hello = Text("Hello", position=(0, 0))
    world = Text("World", position=(0, 20))
    group_drawable = DrawableGroup([hello, world])

    with scene.group():
        scene.add(SketchAnimation(start_time=0.0, duration=0.1), group_drawable)
        fade_out = FadeOutAnimation(start_time=0.5, duration=0.5)
        scene.add(fade_out, group_drawable)
        scene.add_audio(str(audio_path))

    assert fade_out.start_time == pytest.approx(1.5)
    assert fade_out.end_time == pytest.approx(2.0)
    assert scene.object_timelines[hello.id][-1] == pytest.approx(2.0)
    assert scene.object_timelines[world.id][-1] == pytest.approx(2.0)
    assert hello.id in scene.get_active_objects(1.6)
    assert world.id in scene.get_active_objects(1.6)
    assert hello.id not in scene.get_active_objects(2.0)
    assert world.id not in scene.get_active_objects(2.0)


def test_render_with_audio_uses_muxer_and_infers_length(tmp_path, monkeypatch) -> None:
    audio_path = tmp_path / "voice.wav"
    _write_test_wav(audio_path, duration_seconds=1.0)

    scene = Scene(width=8, height=8, fps=4)
    scene.add_audio(str(audio_path))

    captured = {}

    class FakeWriter:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def append_data(self, _frame):
            return None

    def fake_get_writer(path, **kwargs):
        captured["render_target"] = path
        captured["writer_kwargs"] = kwargs
        return FakeWriter()

    def fake_attach_audio_to_video(video_path, output_path, audio_tracks, duration, fps, threads=0):
        captured["video_path"] = video_path
        captured["output_path"] = output_path
        captured["audio_track_count"] = len(audio_tracks)
        captured["duration"] = duration
        captured["fps"] = fps
        captured["threads"] = threads

    monkeypatch.setattr(scene_module.imageio, "get_writer", fake_get_writer)
    monkeypatch.setattr(scene_module, "attach_audio_to_video", fake_attach_audio_to_video)

    output_path = tmp_path / "out.mp4"
    scene.render(str(output_path))

    assert captured["audio_track_count"] == 1
    assert captured["duration"] == pytest.approx(1.0)
    assert captured["fps"] == 4
    assert captured["output_path"] == str(output_path)
    assert captured["render_target"] != str(output_path)


def test_render_gif_rejects_audio_tracks(tmp_path) -> None:
    audio_path = tmp_path / "voice.wav"
    _write_test_wav(audio_path, duration_seconds=0.5)

    scene = Scene(width=8, height=8, fps=4)
    scene.add_audio(str(audio_path))

    with pytest.raises(ValueError, match="GIF"):
        scene.render(str(tmp_path / "out.gif"))
