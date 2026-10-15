"""Pytest setup for DS2: make `src.legal_retrieval` importable from anywhere."""

from __future__ import annotations

import sys
from pathlib import Path

# tests -> legal_retrieval -> src -> <repo root>
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
