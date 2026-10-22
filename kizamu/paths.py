"""Where the sources and the generated data live.

The repository holds the code and the hand-written content. Everything that the
pipelines generate (audio, Anki profiles, packages, model outputs) goes to the data
folder: $KIZAMU_DATA, or data/ in the repository when it is not set.

Stdlib only, so the validators also run with the system python3.
"""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(os.environ.get("KIZAMU_DATA") or ROOT / "data").expanduser().resolve()
