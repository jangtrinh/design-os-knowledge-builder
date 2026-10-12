"""Audio extractor. The core install does not import or run it.

Calling this raises. It never fills in a transcript.
"""


def process_audio(audio_path):
    """Refuse until the optional audio extra and whisper binary are present."""
    raise RuntimeError("missing optional extra 'audio' (binary 'whisper')")
