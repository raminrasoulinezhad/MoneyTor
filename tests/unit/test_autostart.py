# Copyright (c) 2026 Seyedramin Rasoulinezhad
# SPDX-License-Identifier: Apache-2.0
# Licensed under the Apache License, Version 2.0; you may not use this file
# except in compliance with the License. A copy ships in LICENSE, or see
# http://www.apache.org/licenses/LICENSE-2.0. Provided "as is", without warranty.

"""Launch-at-login backends.

Every backend is driven against a temporary directory (or a fake registry), so
these run identically on any host and never touch the real login session.
"""

from __future__ import annotations

import plistlib

import pytest

from moneytor.autostart import (
    APP_NAME,
    MAC_LABEL,
    Autostart,
    AutostartError,
    LinuxAutostart,
    MacAutostart,
    WindowsAutostart,
    autostart_for,
    project_root,
)


def _repo(tmp_path, *, with_launcher: bool = True):
    """A stand-in project root, optionally holding the shell launcher."""
    root = tmp_path / "moneytor"
    (root / "scripts").mkdir(parents=True)
    (root / "src").mkdir()
    (root / "src" / "main.py").write_text("", encoding="utf-8")
    if with_launcher:
        (root / "scripts" / "moneytor.sh").write_text("#!/bin/sh\n", encoding="utf-8")
    return root


# --------------------------------------------------------------------------- #
# Linux — XDG autostart
# --------------------------------------------------------------------------- #


def test_linux_enable_writes_desktop_entry(tmp_path) -> None:
    root = _repo(tmp_path)
    backend = LinuxAutostart(tmp_path / "autostart", root=root)
    assert backend.is_enabled() is False

    backend.enable()

    assert backend.is_enabled() is True
    content = backend.path.read_text(encoding="utf-8")
    assert content.startswith("[Desktop Entry]\n")
    assert f"Name={APP_NAME}" in content
    assert f"Exec={root / 'scripts' / 'moneytor.sh'}" in content
    # Path= gives the session manager the cwd .env and .cache/ are resolved from.
    assert f"Path={root}" in content
    assert "X-GNOME-Autostart-enabled=true" in content


def test_linux_enable_falls_back_to_interpreter_without_launcher(tmp_path) -> None:
    root = _repo(tmp_path, with_launcher=False)
    backend = LinuxAutostart(tmp_path / "autostart", root=root)
    backend.enable()

    exec_line = next(
        line
        for line in backend.path.read_text(encoding="utf-8").splitlines()
        if line.startswith("Exec=")
    )
    assert str(root / "src" / "main.py") in exec_line


def test_linux_enable_is_idempotent(tmp_path) -> None:
    backend = LinuxAutostart(tmp_path / "autostart", root=_repo(tmp_path))
    backend.enable()
    first = backend.path.read_text(encoding="utf-8")
    backend.enable()
    assert backend.path.read_text(encoding="utf-8") == first


def test_linux_disable_removes_entry_and_tolerates_absence(tmp_path) -> None:
    backend = LinuxAutostart(tmp_path / "autostart", root=_repo(tmp_path))
    backend.enable()
    backend.disable()
    assert backend.is_enabled() is False
    assert not backend.path.exists()
    backend.disable()  # already gone — no error


@pytest.mark.parametrize("marker", ["Hidden=true", "X-GNOME-Autostart-enabled=false"])
def test_linux_honours_desktop_environment_disable_markers(tmp_path, marker: str) -> None:
    # Some startup-application UIs disable an entry in place rather than
    # deleting it; the checkbox must follow.
    backend = LinuxAutostart(tmp_path / "autostart", root=_repo(tmp_path))
    backend.enable()
    backend.path.write_text(f"[Desktop Entry]\nType=Application\n{marker}\n", encoding="utf-8")
    assert backend.is_enabled() is False


def test_linux_enable_error_is_wrapped(tmp_path) -> None:
    # A file where the autostart directory should be makes mkdir fail.
    blocker = tmp_path / "autostart"
    blocker.write_text("not a directory", encoding="utf-8")
    backend = LinuxAutostart(blocker, root=_repo(tmp_path))
    with pytest.raises(AutostartError):
        backend.enable()


# --------------------------------------------------------------------------- #
# macOS — LaunchAgent
# --------------------------------------------------------------------------- #


def test_mac_enable_writes_run_at_load_plist(tmp_path) -> None:
    root = _repo(tmp_path)
    backend = MacAutostart(tmp_path / "LaunchAgents", root=root)
    assert backend.is_enabled() is False

    backend.enable()

    assert backend.is_enabled() is True
    assert backend.path.name == f"{MAC_LABEL}.plist"
    plist = plistlib.loads(backend.path.read_bytes())
    assert plist["Label"] == MAC_LABEL
    assert plist["RunAtLoad"] is True
    assert plist["WorkingDirectory"] == str(root)
    assert plist["ProgramArguments"] == [str(root / "scripts" / "moneytor.sh")]


def test_mac_enable_falls_back_to_interpreter_without_launcher(tmp_path) -> None:
    root = _repo(tmp_path, with_launcher=False)
    backend = MacAutostart(tmp_path / "LaunchAgents", root=root)
    backend.enable()
    plist = plistlib.loads(backend.path.read_bytes())
    assert plist["ProgramArguments"][-1] == str(root / "src" / "main.py")


def test_mac_disable_removes_plist_and_tolerates_absence(tmp_path) -> None:
    backend = MacAutostart(tmp_path / "LaunchAgents", root=_repo(tmp_path))
    backend.enable()
    backend.disable()
    assert backend.is_enabled() is False
    backend.disable()  # already gone — no error


# --------------------------------------------------------------------------- #
# Windows — HKCU Run key
# --------------------------------------------------------------------------- #


class _FakeRegistry:
    """Stands in for the per-user Run key so this runs off Windows too."""

    def __init__(self, fail: bool = False) -> None:
        self.values: dict[str, str] = {}
        self._fail = fail

    def read(self, name: str) -> str | None:
        return self.values.get(name)

    def write(self, name: str, command: str) -> None:
        if self._fail:
            raise OSError("access denied")
        self.values[name] = command

    def delete(self, name: str) -> None:
        if self._fail:
            raise OSError("access denied")
        self.values.pop(name, None)


def test_windows_enable_registers_run_value(tmp_path) -> None:
    root = _repo(tmp_path)
    registry = _FakeRegistry()
    backend = WindowsAutostart(registry=registry, root=root)
    assert backend.is_enabled() is False

    backend.enable()

    assert backend.is_enabled() is True
    command = registry.values[APP_NAME]
    # The bootstrap chdirs before running the entrypoint, because a Run-key
    # launch would otherwise start in system32 where .env does not exist.
    assert "os.chdir" in command
    assert str(root) in command
    assert str(root / "src" / "main.py") in command


def test_windows_bootstrap_survives_backslash_paths() -> None:
    # The paths are injected with repr(), so a Windows path's backslashes must
    # not turn into escape sequences inside the -c payload.
    registry = _FakeRegistry()
    backend = WindowsAutostart(registry=registry, root=r"C:\Users\ramin\moneytor")
    backend.enable()

    command = registry.values[APP_NAME]
    assert r"C:\\Users\\ramin\\moneytor" in command  # repr() doubled each backslash
    # list2cmdline wraps the payload in quotes and escapes nothing else here.
    payload = command.split(" -c ", 1)[1].strip('"')
    compile(payload, "<bootstrap>", "exec")  # raises SyntaxError if malformed


def test_windows_disable_clears_value_and_tolerates_absence() -> None:
    registry = _FakeRegistry()
    backend = WindowsAutostart(registry=registry, root=None)
    backend.enable()
    backend.disable()
    assert registry.values == {}
    backend.disable()  # already gone — no error


def test_windows_registry_error_is_wrapped() -> None:
    backend = WindowsAutostart(registry=_FakeRegistry(fail=True), root=None)
    with pytest.raises(AutostartError):
        backend.enable()
    with pytest.raises(AutostartError):
        backend.disable()


# --------------------------------------------------------------------------- #
# Factory + unsupported fallback
# --------------------------------------------------------------------------- #


def test_autostart_for_picks_the_platform_backend(tmp_path) -> None:
    home = tmp_path / "home"
    assert isinstance(autostart_for("linux", home=home), LinuxAutostart)
    assert isinstance(autostart_for("darwin", home=home), MacAutostart)
    assert isinstance(autostart_for("win32", home=home), WindowsAutostart)


def test_autostart_for_uses_xdg_and_launchagent_locations(tmp_path) -> None:
    home = tmp_path / "home"
    assert autostart_for("linux", home=home).path.parent == home / ".config" / "autostart"
    assert autostart_for("darwin", home=home).path.parent == home / "Library" / "LaunchAgents"


def test_unknown_platform_degrades_to_a_disabled_toggle(tmp_path) -> None:
    backend = autostart_for("sunos5", home=tmp_path)
    assert type(backend) is Autostart
    assert backend.supported is False
    assert backend.is_enabled() is False
    # enable/disable stay callable but explain why nothing happened.
    with pytest.raises(AutostartError, match="not available"):
        backend.enable()
    with pytest.raises(AutostartError, match="not available"):
        backend.disable()


def test_set_enabled_dispatches_both_ways(tmp_path) -> None:
    backend = LinuxAutostart(tmp_path / "autostart", root=_repo(tmp_path))
    backend.set_enabled(True)
    assert backend.is_enabled() is True
    backend.set_enabled(False)
    assert backend.is_enabled() is False


def test_project_root_is_the_repo_checkout() -> None:
    # Guards the parents[2] hop: the launcher and entrypoint must resolve.
    root = project_root()
    assert (root / "src" / "main.py").is_file()
    assert (root / "pyproject.toml").is_file()
