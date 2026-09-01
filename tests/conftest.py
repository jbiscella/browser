"""Point the store at a throwaway docs dir before webresearch is imported.

Without this, running the test suite scatters synthetic-*.md fixtures through the
user's real documents/ directory. config.Settings reads the env at import time,
so this has to happen before any webresearch module is loaded.
"""

from __future__ import annotations

import os
import tempfile

os.environ.setdefault(
    "WEBRESEARCH_DOCS_DIR",
    tempfile.mkdtemp(prefix="webresearch-tests-"),
)
