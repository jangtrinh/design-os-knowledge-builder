"""Video Processor: FFmpeg audio demux, keyframe sampling, and timestamped structuring."""

from pathlib import Path
import hashlib
import subprocess
from typing import Dict, Any, List


def process_video(video_path: Path, output_dir: Path = None) -> Dict[str, Any]:
    """Process video file: extract audio track, sample keyframes at scene changes."""
    video_path = Path(video_path).resolve()
    if not video_path.exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")

    sha256 = hashlib.sha256(video_path.read_bytes()).hexdigest()

    if output_dir is None:
        output_dir = video_path.parent / f"extracted_{video_path.stem}"
    output_dir.mkdir(parents=True, exist_ok=True)

    audio_path = output_dir / "audio.mp3"
    frames_dir = output_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    # 1. Demux audio track using ffmpeg
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(video_path), "-vn", "-acodec", "libmp3lame", "-q:a", "4", str(audio_path)],
            capture_output=True,
            check=True
        )
        audio_extracted = True
    except Exception:
        audio_extracted = False

    # 2. Extract scene-change keyframes (1 frame per major transition)
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(video_path), "-vf", "select=gt(scene\\,0.3)", "-vsync", "vfr", str(frames_dir / "frame_%04d.png")],
            capture_output=True,
            check=True
        )
        keyframe_count = len(list(frames_dir.glob("*.png")))
    except Exception:
        keyframe_count = 0

    return {
        "modality": "video",
        "sha256": sha256,
        "uri": f"file://{video_path}",
        "audio_path": str(audio_path) if audio_extracted else None,
        "frames_dir": str(frames_dir),
        "keyframe_count": keyframe_count,
        "markdown_template": f"## [00:00] Overview\n<!-- Video source: {video_path.name} (SHA256: {sha256[:12]}) -->\n",
    }
