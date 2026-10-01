"""Specialized Multimodal Processors (PDF, Video, Image, Web)."""

from .pdf import process_pdf
from .video import process_video
from .image import process_image
from .web import process_web

__all__ = ["process_pdf", "process_video", "process_image", "process_web"]
