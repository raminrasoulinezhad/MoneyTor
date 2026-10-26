# Copyright (c) 2026 Seyedramin Rasoulinezhad
# SPDX-License-Identifier: Apache-2.0
# Licensed under the Apache License, Version 2.0; you may not use this file
# except in compliance with the License. A copy ships in LICENSE, or see
# http://www.apache.org/licenses/LICENSE-2.0. Provided "as is", without warranty.


"""The owner-only, atomic writer behind the token store and snapshot cache."""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

from moneytor.persistence import _private_file
from moneytor.persistence._private_file import write_private


def _mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def test_writes_the_text(tmp_path: Path) -> None:
    path = tmp_path / "tokens.json"
    write_private(path, '{"a": 1}')
    assert path.read_text(encoding="utf-8") == '{"a": 1}'


def test_file_and_directory_are_owner_only(tmp_path: Path) -> None:
    path = tmp_path / "private" / "tokens.json"
    write_private(path, "secret")
    assert _mode(path) == 0o600
    assert _mode(path.parent) == 0o700


def test_an_existing_shared_directory_is_tightened(tmp_path: Path) -> None:
    folder = tmp_path / ".cache"
    folder.mkdir(mode=0o775)
    folder.chmod(0o775)
    write_private(folder / "snapshot.json", "{}")
    assert _mode(folder) == 0o700


def test_file_is_never_world_readable_even_mid_write(tmp_path: Path, monkeypatch) -> None:
    # Capture the temp file's mode at the moment the text is written: the old
    # write-then-chmod left a world-readable window there.
    seen: list[int] = []
    real_fdopen = os.fdopen

    def spying_fdopen(fd, *args, **kwargs):
        seen.append(stat.S_IMODE(os.fstat(fd).st_mode))
        return real_fdopen(fd, *args, **kwargs)

    monkeypatch.setattr(_private_file.os, "fdopen", spying_fdopen)
    write_private(tmp_path / "tokens.json", "secret")
    assert seen == [0o600]


def test_a_failed_write_leaves_the_previous_file_intact(tmp_path: Path, monkeypatch) -> None:
    # Questrade refresh tokens are single-use: a torn token file means making
    # a new token by hand, so a crash mid-write must not touch the old one.
    path = tmp_path / "tokens.json"
    write_private(path, "old-token")

    def crash(*_args, **_kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(_private_file.os, "replace", crash)
    with pytest.raises(OSError, match="disk full"):
        write_private(path, "new-token")

    assert path.read_text(encoding="utf-8") == "old-token"
    assert [p.name for p in tmp_path.iterdir()] == ["tokens.json"]  # no temp left behind
