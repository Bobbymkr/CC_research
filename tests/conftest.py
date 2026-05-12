from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path


_RUNTIME_TEMP_DIR = Path("tests/.tmp_runtime").resolve()


def pytest_configure() -> None:
    if _RUNTIME_TEMP_DIR.exists():
        shutil.rmtree(_RUNTIME_TEMP_DIR, ignore_errors=True)
    _RUNTIME_TEMP_DIR.mkdir(parents=True, exist_ok=True)
    os.environ["TMP"] = str(_RUNTIME_TEMP_DIR)
    os.environ["TEMP"] = str(_RUNTIME_TEMP_DIR)
    os.environ["TMPDIR"] = str(_RUNTIME_TEMP_DIR)
    tempfile.tempdir = str(_RUNTIME_TEMP_DIR)
