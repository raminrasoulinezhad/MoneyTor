# Copyright (c) 2026 Seyedramin Rasoulinezhad
# SPDX-License-Identifier: Apache-2.0
# Licensed under the Apache License, Version 2.0; you may not use this file
# except in compliance with the License. A copy ships in LICENSE, or see
# http://www.apache.org/licenses/LICENSE-2.0. Provided "as is", without warranty.

"""Start MoneyTor automatically when the user logs in.

One backend per desktop OS, each writing the entry that platform's session
manager already looks for — no daemon, no third-party dependency:

    Linux    XDG autostart  ``~/.config/autostart/moneytor.desktop``
    macOS    LaunchAgent    ``~/Library/LaunchAgents/io.moneytor.app.plist``
    Windows  Registry       ``HKCU\\...\\CurrentVersion\\Run`` value ``MoneyTor``

The OS is the single source of truth: :meth:`Autostart.is_enabled` reads the
real entry rather than a preference file, so the setting stays honest when the
user removes it through their desktop's own startup-applications UI.

Every backend launches the app with the project root as the working directory,
because ``.env`` and ``.cache/`` are resolved relative to the CWD (see
``scripts/moneytor.sh``, which a login session does not go through).
"""

from __future__ import annotations

import plistlib
import subprocess
import sys
from pathlib import Path

APP_NAME = "MoneyTor"
# Basename of the Linux .desktop entry and the Windows registry value.
ENTRY_NAME = "moneytor"
# Reverse-DNS label required by launchd for a LaunchAgent.
MAC_LABEL = "io.moneytor.app"

_UNSUPPORTED = "Launch at login is not available on this platform."


class AutostartError(RuntimeError):
    """Raised when an autostart entry could not be written or removed."""


def project_root() -> Path:
    """The repo root — ``src/moneytor/autostart.py`` is three levels down."""
    return Path(__file__).resolve().parents[2]


def _gui_python() -> str:
    """The interpreter to launch with, preferring a console-less one on Windows.

    ``pythonw.exe`` sits beside ``python.exe`` in a venv and runs a GUI app with
    no console window flashing up at login.
    """
    executable = Path(sys.executable)
    if sys.platform != "win32":
        return str(executable)
    windowless = executable.with_name("pythonw.exe")
    return str(windowless if windowless.exists() else executable)


class Autostart:
    """Base backend. Used as-is on platforms we cannot configure."""

    #: False when this platform has no backend; the UI disables the toggle.
    supported: bool = False
    #: Why the toggle is unavailable (shown beside a disabled checkbox).
    reason: str = _UNSUPPORTED

    def is_enabled(self) -> bool:
        """Whether MoneyTor is currently registered to start at login."""
        return False

    def enable(self) -> None:
        """Register MoneyTor to start at login (idempotent)."""
        raise AutostartError(self.reason)

    def disable(self) -> None:
        """Remove the login entry (idempotent — a no-op when already absent)."""
        raise AutostartError(self.reason)

    def set_enabled(self, enabled: bool) -> None:
        """Enable or disable, whichever ``enabled`` asks for."""
        self.enable() if enabled else self.disable()


class LinuxAutostart(Autostart):
    """XDG autostart: a ``.desktop`` file the session manager runs at login."""

    supported = True

    def __init__(self, autostart_dir: Path, root: Path | None = None) -> None:
        self._path = Path(autostart_dir) / f"{ENTRY_NAME}.desktop"
        self._root = Path(root) if root is not None else project_root()

    @property
    def path(self) -> Path:
        return self._path

    def is_enabled(self) -> bool:
        try:
            content = self._path.read_text(encoding="utf-8")
        except OSError:
            return False
        # Desktop environments honour these two keys as "installed but off",
        # which is how some startup-application UIs disable an entry in place.
        disabled = ("Hidden=true", "X-GNOME-Autostart-enabled=false")
        return not any(line.strip() in disabled for line in content.splitlines())

    def enable(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(self._desktop_entry(), encoding="utf-8")
            self._path.chmod(0o755)
        except OSError as exc:
            raise AutostartError(f"Could not write {self._path}: {exc}") from exc

    def disable(self) -> None:
        try:
            self._path.unlink(missing_ok=True)
        except OSError as exc:
            raise AutostartError(f"Could not remove {self._path}: {exc}") from exc

    def _desktop_entry(self) -> str:
        launcher = self._root / "scripts" / "moneytor.sh"
        # The shell wrapper already cds to the project root and picks the venv
        # interpreter; fall back to the interpreter directly if it is missing.
        exec_line = (
            str(launcher)
            if launcher.exists()
            else subprocess.list2cmdline([_gui_python(), str(self._root / "src" / "main.py")])
        )
        return "\n".join(
            (
                "[Desktop Entry]",
                "Type=Application",
                "Version=1.0",
                f"Name={APP_NAME}",
                "Comment=Start MoneyTor when you log in",
                f"Exec={exec_line}",
                f"Icon={self._root / 'packaging' / 'moneytor.png'}",
                f"Path={self._root}",
                "Terminal=false",
                "X-GNOME-Autostart-enabled=true",
                "",
            )
        )


class MacAutostart(Autostart):
    """launchd LaunchAgent with ``RunAtLoad``, picked up at the next login."""

    supported = True

    def __init__(self, agents_dir: Path, root: Path | None = None) -> None:
        self._path = Path(agents_dir) / f"{MAC_LABEL}.plist"
        self._root = Path(root) if root is not None else project_root()

    @property
    def path(self) -> Path:
        return self._path

    def is_enabled(self) -> bool:
        return self._path.is_file()

    def enable(self) -> None:
        plist = {
            "Label": MAC_LABEL,
            "ProgramArguments": list(self._program_arguments()),
            "WorkingDirectory": str(self._root),
            "RunAtLoad": True,
        }
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_bytes(plistlib.dumps(plist))
        except OSError as exc:
            raise AutostartError(f"Could not write {self._path}: {exc}") from exc

    def disable(self) -> None:
        try:
            self._path.unlink(missing_ok=True)
        except OSError as exc:
            raise AutostartError(f"Could not remove {self._path}: {exc}") from exc

    def _program_arguments(self) -> tuple[str, ...]:
        launcher = self._root / "scripts" / "moneytor.sh"
        if launcher.exists():
            return (str(launcher),)
        return (_gui_python(), str(self._root / "src" / "main.py"))


# Chdir before running the entrypoint: launching from the registry gives the
# process the system32 working directory, where .env and .cache/ do not exist.
_WIN_BOOTSTRAP = "import os, runpy; os.chdir({root}); runpy.run_path({entry}, run_name='__main__')"

_WIN_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


class _WinRegistry:
    """Thin ``winreg`` wrapper over the per-user Run key (injectable in tests)."""

    def read(self, name: str) -> str | None:
        import winreg

        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _WIN_RUN_KEY) as key:
                value, _ = winreg.QueryValueEx(key, name)
        except OSError:
            return None
        return str(value)

    def write(self, name: str, command: str) -> None:
        import winreg

        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, _WIN_RUN_KEY) as key:
            winreg.SetValueEx(key, name, 0, winreg.REG_SZ, command)

    def delete(self, name: str) -> None:
        import winreg

        root = winreg.HKEY_CURRENT_USER
        try:
            with winreg.OpenKey(root, _WIN_RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
                winreg.DeleteValue(key, name)
        except FileNotFoundError:
            pass  # already absent — disable() is idempotent


class WindowsAutostart(Autostart):
    """A per-user ``Run`` registry value, which Windows executes at sign-in."""

    supported = True

    def __init__(self, registry: _WinRegistry | None = None, root: Path | None = None) -> None:
        self._registry = registry if registry is not None else _WinRegistry()
        self._root = Path(root) if root is not None else project_root()

    def is_enabled(self) -> bool:
        return self._registry.read(APP_NAME) is not None

    def enable(self) -> None:
        try:
            self._registry.write(APP_NAME, self.command())
        except OSError as exc:
            raise AutostartError(f"Could not write the {APP_NAME} startup entry: {exc}") from exc

    def disable(self) -> None:
        try:
            self._registry.delete(APP_NAME)
        except OSError as exc:
            raise AutostartError(f"Could not remove the {APP_NAME} startup entry: {exc}") from exc

    def command(self) -> str:
        """The command line Windows runs at sign-in."""
        bootstrap = _WIN_BOOTSTRAP.format(
            root=repr(str(self._root)),
            entry=repr(str(self._root / "src" / "main.py")),
        )
        return subprocess.list2cmdline([_gui_python(), "-c", bootstrap])


def autostart_for(
    platform: str | None = None,
    home: Path | None = None,
    root: Path | None = None,
) -> Autostart:
    """Build the backend for ``platform`` (defaults to the running one).

    ``home`` and ``root`` exist for tests; in production both are discovered.
    Unknown platforms get the unsupported base backend, so the caller can always
    construct one and simply render the toggle disabled.
    """
    system = platform if platform is not None else sys.platform
    base = Path(home) if home is not None else Path.home()
    if system.startswith("linux"):
        return LinuxAutostart(base / ".config" / "autostart", root=root)
    if system == "darwin":
        return MacAutostart(base / "Library" / "LaunchAgents", root=root)
    if system == "win32":
        return WindowsAutostart(root=root)
    return Autostart()
