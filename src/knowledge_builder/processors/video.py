"""Video processor: ffmpeg extracts under an explicit directory. No invented media."""

from pathlib import Path
import hashlib
import subprocess
from typing import Dict, Any


def _caller_uri(path) -> str:
    if isinstance(path, str):
        return path
    return str(path)


def process_video(video_path: Path, output_dir: Path = None) -> Dict[str, Any]:
    """Demux audio and sample frames with ffmpeg. Writes only under output_dir."""
    source = Path(video_path)
    if not source.exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")

    sha256 = hashlib.sha256(source.read_bytes()).hexdigest()

    if output_dir is None:
        raise RuntimeError("ffmpeg output requires an explicit --out directory")

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    audio_path = output_dir / "audio.mp3"
    frames_dir = output_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    try:
        subprocess.run(
            [
                "ffmpeg", "-y", "-i", str(source),
                "-vn", "-acodec", "libmp3lame", "-q:a", "4", str(audio_path),
            ],
            capture_output=True,
            check=True,
        )
        subprocess.run(
            [
                "ffmpeg", "-y", "-i", str(source),
                "-vf", "select=gt(scene\\,0.3)", "-vsync", "vfr",
                str(frames_dir / "frame_%04d.png"),
            ],
            capture_output=True,
            check=True,
        )
    except Exception as exc:
        raise RuntimeError("ffmpeg") from exc

    return {
        "modality": "video",
        "sha256": sha256,
        "uri": _caller_uri(video_path),
        "audio_path": str(audio_path),
        "frames_dir": str(frames_dir),
        "keyframe_count": len(list(frames_dir.glob("*.png"))),
        "markdown_template": (
            f"## [00:00] Overview\n"
            f"<!-- Video source: {source.name} (SHA256: {sha256[:12]}) -->\n"
        ),
    }
