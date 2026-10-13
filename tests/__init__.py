"""Make `src/` importable so `python3 -m unittest discover -s tests -t .` needs no PYTHONPATH.

The test entry point works without an environment prefix on the command,
such as `PYTHONPATH=src python3 ...`.
"""

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
