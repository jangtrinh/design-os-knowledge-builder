"""Make `src/` importable so `python3 -m unittest discover -s tests -t .` needs no PYTHONPATH.

Headless agent runtimes (Grok Build 1.0.50) cannot pre-approve env-prefixed commands such as
`PYTHONPATH=src python3 ...`, so the test entry point must work without one.
"""

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
