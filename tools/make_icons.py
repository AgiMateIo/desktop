#!/usr/bin/env python3
"""Generate packaging icons from the brand connector tile.

    uv run python tools/make_icons.py

Writes into `assets/`:
    icon.png    512 px, for Linux desktop entries and the AppImage
    icon.icns   macOS bundle icon
    icon.ico    Windows executable icon, seven sizes

The source is `assets/brand/connector-tile.svg`, rendered through the same
`ui.branding` code the running app uses, so a change to the identity reaches
the packaged icons by re-running this — nothing is redrawn by hand.

The dark tile is what gets baked: the tile carries both themes in a media
query, and a file on disk is asked for its icon long before anyone knows what
theme the machine is in. Dark is the identity's default, and the identity says
so — anything ignoring prefers-color-scheme falls back to it.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# A GUI-less renderer still needs a platform plugin; offscreen is the one that
# never asks for a display.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QGuiApplication  # noqa: E402

from ui import branding  # noqa: E402

ASSETS = ROOT / "assets"

# macOS iconset names, as `iconutil` expects them.
ICNS_SIZES = [
    ("icon_16x16.png", 16),
    ("icon_16x16@2x.png", 32),
    ("icon_32x32.png", 32),
    ("icon_32x32@2x.png", 64),
    ("icon_128x128.png", 128),
    ("icon_128x128@2x.png", 256),
    ("icon_256x256.png", 256),
    ("icon_256x256@2x.png", 512),
    ("icon_512x512.png", 512),
    ("icon_512x512@2x.png", 1024),
]


def make_png() -> None:
    path = ASSETS / "icon.png"
    branding.app_tile(512, branding.DARK).save(str(path))
    print(f"wrote {path.relative_to(ROOT)}")


def make_ico() -> None:
    path = ASSETS / "icon.ico"
    branding.write_ico(path, branding.DARK)
    print(f"wrote {path.relative_to(ROOT)}")


def make_icns() -> None:
    """Build the .icns via iconutil, which only exists on macOS."""
    if sys.platform != "darwin":
        print("skipping icon.icns — iconutil is macOS only")
        return

    iconset = ASSETS / "AgimateDesktop.iconset"
    if iconset.exists():
        shutil.rmtree(iconset)
    iconset.mkdir(parents=True)

    # Rounded on macOS only: the identity draws a full square tile, and every
    # other icon in the Dock is a rounded rect. The tile's corners are bare
    # plate, so the mark loses nothing to the mask.
    for name, size in ICNS_SIZES:
        branding.app_tile(size, branding.DARK, rounded=True).save(str(iconset / name))

    path = ASSETS / "icon.icns"
    result = subprocess.run(
        ["iconutil", "-c", "icns", str(iconset), "-o", str(path)],
        capture_output=True,
        text=True,
    )
    shutil.rmtree(iconset)

    if result.returncode != 0:
        print(f"iconutil failed: {result.stderr.strip()}")
        sys.exit(1)

    print(f"wrote {path.relative_to(ROOT)}")


def main() -> None:
    QGuiApplication([])
    ASSETS.mkdir(exist_ok=True)
    make_png()
    make_ico()
    make_icns()


if __name__ == "__main__":
    main()
