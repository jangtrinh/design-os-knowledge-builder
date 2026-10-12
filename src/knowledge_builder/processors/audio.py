"""Audio extractor. Shells out to whisper or whisper-cli when one is on PATH.

The core install does not import either tool. A missing binary or a non-zero
exit raises RuntimeError. The transcript is that tool's own output.
"""

from pathlib import Path
import shutil
import subprocess
import tempfile


def process_audio(audio_path):
    """Return transcript text from `whisper` or, if absent, `whisper-cli`.

    openai-whisper writes a .txt file when asked; that file is the transcript
    when it exists. Otherwise the process stdout is the transcript, which is
    what whisper-cli prints. Never invents a paragraph.
    """
    source = str(audio_path)
    whisper = shutil.which("whisper")
    whisper_cli = shutil.which("whisper-cli")
    out_dir = None
    if whisper:
        label = "whisper"
        out_dir = Path(tempfile.mkdtemp(prefix="kb-audio-"))
        argv = [
            whisper,
            source,
            "--output_format",
            "txt",
            "--output_dir",
            str(out_dir),
        ]
    elif whisper_cli:
        label = "whisper-cli"
        argv = [whisper_cli, "-f", source, "-nt"]
    else:
        raise RuntimeError(
            "missing optional extra 'audio' (binary 'whisper' or 'whisper-cli')"
        )

    try:
        completed = _run_extractor(argv, f"audio extractor {label}")
        if out_dir is not None:
            written = sorted(path for path in out_dir.glob("*.txt") if path.is_file())
            if written:
                return written[0].read_text(encoding="utf-8")
        return completed.stdout
    finally:
        if out_dir is not None:
            shutil.rmtree(out_dir, ignore_errors=True)


def _run_extractor(argv, label):
    try:
        completed = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError as exc:
        raise RuntimeError(f"{label} failed to start: {exc}") from exc
    if completed.returncode != 0:
        raise RuntimeError(f"{label} exited {completed.returncode}")
    return completed
