#!/usr/bin/env bash
# Copyright (c) 2026 Seyedramin Rasoulinezhad
# SPDX-License-Identifier: Apache-2.0
# Licensed under the Apache License, Version 2.0; you may not use this file
# except in compliance with the License. A copy ships in LICENSE, or see
# http://www.apache.org/licenses/LICENSE-2.0. Provided "as is", without warranty.

# Install (or remove) the MoneyTor desktop launcher on Linux.
#
#   ./scripts/install-desktop.sh                  # install: app grid + desktop icon
#   ./scripts/install-desktop.sh --uninstall      # remove them (asks first)
#   ./scripts/install-desktop.sh --uninstall -y   # remove them without asking
#
# Idempotent: re-running re-points the launchers at the current repo location.
#
# --uninstall lists what it is about to delete and waits for confirmation.
# Without a terminal to ask on (a script, a CI job, output piped elsewhere) it
# refuses instead of assuming yes, so an unattended run cannot quietly remove
# launchers someone is relying on. Pass -y to mean it.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

APPS_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
DESKTOP_DIR="$(xdg-user-dir DESKTOP 2>/dev/null || echo "$HOME/Desktop")"
TARGET_NAME="moneytor.desktop"

assume_yes=false
mode=install
for arg in "$@"; do
    case "$arg" in
        --uninstall) mode=uninstall ;;
        -y | --yes) assume_yes=true ;;
        -h | --help)
            sed -n '8,19p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
            exit 0
            ;;
        *)
            echo "Unknown option: $arg" >&2
            echo "Usage: $0 [--uninstall] [-y|--yes]" >&2
            exit 2
            ;;
    esac
done

uninstall() {
    local targets=()
    [[ -e "$APPS_DIR/$TARGET_NAME" ]] && targets+=("$APPS_DIR/$TARGET_NAME")
    [[ -e "$DESKTOP_DIR/$TARGET_NAME" ]] && targets+=("$DESKTOP_DIR/$TARGET_NAME")

    if [[ ${#targets[@]} -eq 0 ]]; then
        echo "No MoneyTor launchers installed — nothing to remove."
        return 0
    fi

    echo "This will delete:"
    printf '  %s\n' "${targets[@]}"
    echo
    echo "MoneyTor itself, your .env, and your cached data are not affected."
    echo "Reinstall any time with: $0"
    echo

    if [[ "$assume_yes" != true ]]; then
        if [[ ! -t 0 ]]; then
            echo "Refusing to remove launchers without confirmation." >&2
            echo "No terminal to ask on — re-run with -y if you are sure." >&2
            return 1
        fi
        read -r -p "Remove them? [y/N] " reply
        if [[ ! "$reply" =~ ^[Yy]$ ]]; then
            echo "Cancelled — nothing was removed."
            return 0
        fi
    fi

    rm -f "${targets[@]}"
    command -v update-desktop-database >/dev/null && update-desktop-database "$APPS_DIR" 2>/dev/null || true
    echo "Removed MoneyTor launchers."
}

if [[ "$mode" == uninstall ]]; then
    uninstall
    exit $?
fi

# 1. Make the launcher executable.
chmod +x "$PROJECT_ROOT/scripts/moneytor.sh"

# 2. Render the .desktop with this repo's absolute path baked in.
rendered="$(sed "s#__PROJECT_ROOT__#$PROJECT_ROOT#g" "$PROJECT_ROOT/packaging/$TARGET_NAME")"

# 3a. App-grid / search entry.
mkdir -p "$APPS_DIR"
printf '%s\n' "$rendered" > "$APPS_DIR/$TARGET_NAME"
chmod +x "$APPS_DIR/$TARGET_NAME"

# 3b. Desktop double-click icon (marked trusted so GNOME launches it).
if [[ -d "$DESKTOP_DIR" ]]; then
    printf '%s\n' "$rendered" > "$DESKTOP_DIR/$TARGET_NAME"
    chmod +x "$DESKTOP_DIR/$TARGET_NAME"
    gio set "$DESKTOP_DIR/$TARGET_NAME" "metadata::trusted" true 2>/dev/null || true
fi

# 4. Refresh the desktop database so it shows up immediately.
command -v update-desktop-database >/dev/null && update-desktop-database "$APPS_DIR" 2>/dev/null || true

echo "Installed MoneyTor:"
echo "  app grid : $APPS_DIR/$TARGET_NAME"
[[ -d "$DESKTOP_DIR" ]] && echo "  desktop  : $DESKTOP_DIR/$TARGET_NAME"
echo
echo "Press Super and type 'MoneyTor', or double-click the desktop icon."
echo "On the desktop icon's first run you may need: right-click -> Allow Launching."
