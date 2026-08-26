"""Stream rendered Isaac camera frames into a local H.264 recording."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil
import subprocess
from typing import BinaryIO


@dataclass(frozen=True)
class VideoRecording:
    path: str
    fps: int
    width: int
    height: int
    frame_count: int
    first_sim_time_ns: int | None
    last_sim_time_ns: int | None
    duration_s: float
    file_bytes: int
    codec: str = "h264"
    source: str = "rendered_overhead_rgb"

    def to_dict(self) -> dict[str, object]:
        return {
            "path": self.path,
            "fps": self.fps,
            "width": self.width,
            "height": self.height,
            "frame_count": self.frame_count,
            "first_sim_time_ns": self.first_sim_time_ns,
            "last_sim_time_ns": self.last_sim_time_ns,
            "duration_s": self.duration_s,
            "file_bytes": self.file_bytes,
            "codec": self.codec,
            "source": self.source,
        }


class RawVideoRecorder:
    """Write RGB24 frames to ffmpeg without retaining them in memory."""

    def __init__(self, output_path: Path, *, fps: int, width: int, height: int) -> None:
        if fps <= 0 or width <= 0 or height <= 0:
            raise ValueError("Video dimensions and frame rate must be positive")
        ffmpeg = shutil.which("ffmpeg")
        if ffmpeg is None:
            raise RuntimeError("ffmpeg is required to record the Isaac demonstration")
        self.output_path = output_path.resolve()
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self.fps = fps
        self.width = width
        self.height = height
        self.frame_count = 0
        self.first_sim_time_ns: int | None = None
        self.last_sim_time_ns: int | None = None
        self._closed = False
        self._process = subprocess.Popen(
            [
                ffmpeg,
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-f",
                "rawvideo",
                "-pixel_format",
                "rgb24",
                "-video_size",
                f"{width}x{height}",
                "-framerate",
                str(fps),
                "-i",
                "-",
                "-an",
                "-c:v",
                "libx264",
                "-preset",
                "medium",
                "-crf",
                "19",
                "-pix_fmt",
                "yuv420p",
                "-movflags",
                "+faststart",
                str(self.output_path),
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )

    @property
    def _stdin(self) -> BinaryIO:
        if self._process.stdin is None:
            raise RuntimeError("Video encoder input is unavailable")
        return self._process.stdin

    def write_frame(self, rgb24: bytes, sim_time_ns: int) -> None:
        if self._closed:
            raise RuntimeError("Video recorder is already closed")
        expected = self.width * self.height * 3
        if len(rgb24) != expected:
            raise ValueError(f"Expected {expected} RGB bytes, received {len(rgb24)}")
        try:
            self._stdin.write(rgb24)
        except BrokenPipeError as exc:
            stderr = self._process.stderr.read().decode("utf-8", errors="replace") if self._process.stderr else ""
            raise RuntimeError(f"ffmpeg stopped while recording: {stderr.strip()}") from exc
        self.frame_count += 1
        self.first_sim_time_ns = sim_time_ns if self.first_sim_time_ns is None else self.first_sim_time_ns
        self.last_sim_time_ns = sim_time_ns

    def close(self) -> VideoRecording:
        if self._closed:
            raise RuntimeError("Video recorder was closed more than once")
        self._closed = True
        self._stdin.close()
        try:
            return_code = self._process.wait(timeout=60.0)
        except subprocess.TimeoutExpired as exc:
            self._process.kill()
            self._process.wait(timeout=10.0)
            raise RuntimeError("ffmpeg did not finish the recording within 60 seconds") from exc
        stderr = self._process.stderr.read().decode("utf-8", errors="replace") if self._process.stderr else ""
        if return_code != 0:
            raise RuntimeError(f"ffmpeg failed with exit code {return_code}: {stderr.strip()}")
        if self.frame_count == 0 or not self.output_path.is_file():
            raise RuntimeError("Video recording contains no rendered frames")
        duration_s = self.frame_count / self.fps
        return VideoRecording(
            str(self.output_path),
            self.fps,
            self.width,
            self.height,
            self.frame_count,
            self.first_sim_time_ns,
            self.last_sim_time_ns,
            duration_s,
            self.output_path.stat().st_size,
        )
