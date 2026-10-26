# Copyright (c) 2026 Seyedramin Rasoulinezhad
# SPDX-License-Identifier: Apache-2.0
# Licensed under the Apache License, Version 2.0; you may not use this file
# except in compliance with the License. A copy ships in LICENSE, or see
# http://www.apache.org/licenses/LICENSE-2.0. Provided "as is", without warranty.


"""Write a file that holds secrets or portfolio data: owner-only and atomic."""

from __future__ import annotations

import os
import tempfile
from contextlib import suppress
from pathlib import Path


def write_private(path: Path, text: str) -> None:
    """Replace ``path`` with ``text``, never exposing or tearing the file.

    * **Owner-only from the first byte.** ``mkstemp`` creates the file 0600;
      writing first and ``chmod``-ing after left it world-readable meanwhile.
    * **Atomic.** The text goes to a sibling temp file, is flushed to disk, and
      is renamed over ``path`` in one step, so a crash mid-write leaves the old
      file intact. That matters most for Questrade's single-use refresh token:
      a torn token file means generating a new token by hand.

    The parent directory is created if needed and kept owner-only (0700).
    """
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.parent.chmod(0o700)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    except BaseException:
        with suppress(FileNotFoundError):
            os.unlink(tmp)
        raise
