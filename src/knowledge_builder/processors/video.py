"""Video processor: ffmpeg extracts under an explicit directory. No invented media."""

from pathlib import Path
import hashlib
import subprocess
import tempfile
from typing import Dict, Any

from knowledge_builder.containment import atomic_write, reject_symlink


def _caller_uri(path) -> str:
    if isinstance(path, str):
        return path
    return str(path)


def _ffmpeg(args):
    try:
        return subprocess.run(args, capture_output=True, check=True)
    except Exception as exc:
        raise RuntimeError("ffmpeg") from exc


def _as_bytes(payload):
    if payload is None:
        return b""
    if isinstance(payload, str):
        return payload.encode("utf-8")
    return payload


def _real_dir(path):
    """Create a real directory. A symlink at path is refused."""
    path = Path(path)
    reject_symlink(path)
    path.mkdir(parents=True, exist_ok=True)
    reject_symlink(path)
    return path


def process_video(video_path: Path, output_dir: Path = None) -> Dict[str, Any]:
    """Demux audio and sample frames with ffmpeg. Writes only under output_dir.

    ffmpeg never receives the caller's output path. Bytes are published with
    atomic_write, which refuses a symlinked name on a directory fd.
    """
    source = Path(video_path)
    if not source.exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")

    sha256 = hashlib.sha256(source.read_bytes()).hexdigest()

    if output_dir is None:
        raise RuntimeError("ffmpeg output requires an explicit --out directory")

    output_dir = _real_dir(output_dir)
    frames_dir = _real_dir(output_dir / "frames")

    audio = _ffmpeg(
        [
            "ffmpeg", "-y", "-i", str(source),
            "-vn", "-acodec", "libmp3lame", "-q:a", "4",
            "-f", "mp3", "pipe:1",
        ]
    )
    atomic_write(output_dir, "audio.mp3", _as_bytes(audio.stdout))

    with tempfile.TemporaryDirectory() as scratch:
        scratch_dir = Path(scratch)
        _ffmpeg(
            [
                "ffmpeg", "-y", "-i", str(source),
                "-vf", "select=gt(scene\\,0.3)", "-vsync", "vfr",
                str(scratch_dir / "frame_%04d.png"),
            ]
        )
        for frame in sorted(scratch_dir.glob("*.png")):
            atomic_write(frames_dir, frame.name, frame.read_bytes())

    return {
        "modality": "video",
        "sha256": sha256,
        "uri": _caller_uri(video_path),
        "audio_path": str(output_dir / "audio.mp3"),
        "frames_dir": str(frames_dir),
        "keyframe_count": len(list(frames_dir.glob("*.png"))),
        "markdown_template": (
            f"## [00:00] Overview\n"
            f"<!-- Video source: {source.name} (SHA256: {sha256[:12]}) -->\n"
        ),
    }
