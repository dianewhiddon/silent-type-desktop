"""Start with Windows: a shortcut in the current user's Startup folder.

Nothing else is touched: no registry entry, no scheduled task, no administrator
access. Removing the shortcut (here, in the tray menu, or by hand) turns it off.
"""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LINK_NAME = "Silent Type Desktop.lnk"
FOLDER = Path(os.environ.get("APPDATA", Path.home())) / "Microsoft/Windows/Start Menu/Programs/Startup"

# Values travel in the environment so no path is ever parsed as PowerShell code.
SCRIPT = (
    "$s=(New-Object -ComObject WScript.Shell).CreateShortcut($env:ST_LINK);"
    "$s.TargetPath=$env:ST_TARGET;$s.Arguments='-m silent_type';"
    "$s.WorkingDirectory=$env:ST_DIR;$s.IconLocation=$env:ST_ICON;"
    "$s.Description='Camera-only silent typing';$s.Save()"
)


def link(folder=None):
    return Path(folder or FOLDER) / LINK_NAME


def enabled(folder=None):
    return link(folder).exists()


def interpreter():
    """The windowless interpreter of this installation, so no console flashes at login."""
    python = Path(sys.executable)
    windowless = python.with_name("pythonw.exe")
    return windowless if windowless.exists() else python


def enable(folder=None):
    path = link(folder)
    path.parent.mkdir(parents=True, exist_ok=True)
    env = dict(
        os.environ,
        ST_LINK=str(path),
        ST_TARGET=str(interpreter()),
        ST_DIR=str(ROOT),
        ST_ICON=str(ROOT / "silent_type" / "silent-type.ico") + ",0",
    )
    subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden", "-Command", SCRIPT],
        env=env,
        check=True,
        timeout=30,
        creationflags=0x08000000,  # CREATE_NO_WINDOW
    )


def disable(folder=None):
    link(folder).unlink(missing_ok=True)


def toggle(folder=None):
    """Flip the setting and return whether Silent Type now starts with Windows."""
    if enabled(folder):
        disable(folder)
        return False
    enable(folder)
    return True
