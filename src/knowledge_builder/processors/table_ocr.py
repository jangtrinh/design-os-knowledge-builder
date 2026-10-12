"""Table OCR extractor. The core install does not import or run it.

Calling this raises. It never fills in a table.
"""


def process_table_ocr(image_path):
    """Refuse until the optional ocr extra and tesseract binary are present."""
    raise RuntimeError("missing optional extra 'ocr' (binary 'tesseract')")
