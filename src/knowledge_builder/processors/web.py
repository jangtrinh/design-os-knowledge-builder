"""Web Processor: Clean web scraping and markdown normalization."""

import hashlib
import re
import urllib.request
from typing import Dict, Any


def process_web(url: str) -> Dict[str, Any]:
    """Fetch URL and strip boilerplate HTML to extract clean markdown-like text."""
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        html = resp.read().decode("utf-8", errors="ignore")

    sha256 = hashlib.sha256(html.encode("utf-8")).hexdigest()

    # Simple clean: remove scripts, styles, tags
    cleaned = re.sub(r"<(script|style).*?</\1>", "", html, flags=re.DOTALL | re.IGNORECASE)
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    return {
        "modality": "web",
        "sha256": sha256,
        "uri": url,
        "cleaned_text": cleaned[:5000],  # preview
        "length": len(cleaned),
    }
