"""Persistent store for rotating OAuth refresh tokens.

Questrade refresh tokens are single-use: each login returns a *new* refresh
token that must replace the old one. The ``.env`` value is only a seed; the
live token lives here in a gitignored JSON cache so re-runs keep working.
"""

from __future__ import annotations

import json
from pathlib import Path

DEFAULT_TOKEN_PATH = Path(".cache") / "tokens.json"


class TokenStore:
    """A tiny JSON-file store keyed by ``(institution, person_id)``."""

    def __init__(self, path: str | Path = DEFAULT_TOKEN_PATH) -> None:
        self._path = Path(path)

    def _load(self) -> dict[str, dict[str, str]]:
        if not self._path.exists():
            return {}
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        if not isinstance(data, dict):
            return {}
        return data

    def get(self, institution: str, person_id: str) -> str | None:
        """Return the stored refresh token, or ``None`` if absent."""
        return self._load().get(institution, {}).get(person_id)

    def save(self, institution: str, person_id: str, token: str) -> None:
        """Persist ``token`` for ``(institution, person_id)``, creating dirs.

        Refresh tokens grant full account access, so the file is written
        owner-only (0600) inside an owner-only directory (0700).
        """
        data = self._load()
        data.setdefault(institution, {})[person_id] = token
        self._path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self._path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        self._path.chmod(0o600)
