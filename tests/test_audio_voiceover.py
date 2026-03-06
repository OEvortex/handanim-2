import wave
from pathlib import Path

import pytest

import handanim.core.scene as scene_module
from handanim.core import AudioTrack, Scene


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

    def fake_attach_audio_to_video(video_path, output_path, audio_tracks, duration, fps):
        captured["video_path"] = video_path
        captured["output_path"] = output_path
        captured["audio_track_count"] = len(audio_tracks)
        captured["duration"] = duration
        captured["fps"] = fps

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
