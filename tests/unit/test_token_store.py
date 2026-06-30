# Copyright (c) 2026 Seyedramin Rasoulinezhad
# SPDX-License-Identifier: PolyForm-Noncommercial-1.0.0
# Noncommercial use permitted. Commercial use requires a separate license;
# contact the author. Provided "as is", without warranty of any kind.

"""Tests for the rotating-token store (Phase 8)."""

from __future__ import annotations

from pathlib import Path

from moneytor.persistence import TokenStore


def test_returns_none_when_absent(tmp_path: Path) -> None:
    store = TokenStore(tmp_path / "tokens.json")
    assert store.get("questrade", "ramin") is None


def test_save_then_get_roundtrip(tmp_path: Path) -> None:
    store = TokenStore(tmp_path / "tokens.json")
    store.save("questrade", "ramin", "tok-1")
    assert store.get("questrade", "ramin") == "tok-1"


def test_save_creates_parent_directories(tmp_path: Path) -> None:
    store = TokenStore(tmp_path / "nested" / "dir" / "tokens.json")
    store.save("questrade", "ramin", "tok-1")
    assert (tmp_path / "nested" / "dir" / "tokens.json").exists()


def test_overwrite_and_isolation(tmp_path: Path) -> None:
    store = TokenStore(tmp_path / "tokens.json")
    store.save("questrade", "ramin", "tok-1")
    store.save("questrade", "ramin", "tok-2")
    store.save("questrade", "alex", "alex-tok")
    assert store.get("questrade", "ramin") == "tok-2"
    assert store.get("questrade", "alex") == "alex-tok"


def test_corrupt_file_is_ignored(tmp_path: Path) -> None:
    path = tmp_path / "tokens.json"
    path.write_text("{not json", encoding="utf-8")
    store = TokenStore(path)
    assert store.get("questrade", "ramin") is None


def test_saved_token_file_is_owner_only(tmp_path: Path) -> None:
    path = tmp_path / "tokens.json"
    store = TokenStore(path)
    store.save("questrade", "ramin", "secret-refresh-token")
    # Refresh tokens grant full account access -> must not be group/world readable.
    assert (path.stat().st_mode & 0o777) == 0o600
