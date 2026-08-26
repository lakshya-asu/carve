from __future__ import annotations

from pathlib import Path
import shutil

import pytest

from isaac_sim.video_recorder import RawVideoRecorder


def test_video_recorder_rejects_invalid_dimensions(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="positive"):
        RawVideoRecorder(tmp_path / "invalid.mp4", fps=0, width=16, height=16)


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg is not installed")
def test_video_recorder_writes_h264_container(tmp_path: Path) -> None:
    target = tmp_path / "smoke.mp4"
    recorder = RawVideoRecorder(target, fps=12, width=16, height=16)
    for index in range(12):
        pixel = bytes((index * 10, 40, 90))
        recorder.write_frame(pixel * (16 * 16), index * 83_333_333)

    result = recorder.close()

    assert result.path == str(target.resolve())
    assert result.frame_count == 12
    assert result.duration_s == 1.0
    assert result.first_sim_time_ns == 0
    assert result.last_sim_time_ns == 916_666_663
    assert result.file_bytes > 0
    assert target.read_bytes()[4:8] == b"ftyp"
