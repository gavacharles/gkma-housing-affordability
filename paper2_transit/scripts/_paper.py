"""Paper 2 set-up: import this first in every paper-2 script.

Puts the shared pipeline (src/ and the shared scripts/ helpers) on the path, and
makes this paper's outputs/ the default output folder for stages and maps.
"""
import os
import sys
from pathlib import Path

PAPER = Path(__file__).resolve().parents[1]           # paper2_transit/
ROOT = PAPER.parent                                     # project root (shared pipeline)
sys.path.insert(0, str(ROOT / "scripts"))
os.environ.setdefault("GKMA_OUT", str(PAPER.relative_to(ROOT) / "outputs"))

import _common  # noqa: E402,F401  (adds src/ to the path)
from gkma.viz import pubmaps  # noqa: E402

pubmaps.OUT_DIR = os.path.join(os.environ["GKMA_OUT"], "maps")
OUT = PAPER / "outputs"
DOCS = PAPER / "docs"
