#!/usr/bin/env python3
"""Build script for Agimate Desktop."""

import subprocess
import sys
import shutil
from pathlib import Path


def clean():
    """Remove build artifacts."""
    root = Path(__file__).parent
    dirs_to_remove = ['build', 'dist']

    for dir_name in dirs_to_remove:
        dir_path = root / dir_name
        if dir_path.exists():
            print(f"Removing {dir_path}...")
            shutil.rmtree(dir_path)

    print("Clean complete.")


def icons():
    """Generate the packaging icons from the brand tile."""
    root = Path(__file__).parent
    script = root / 'tools' / 'make_icons.py'

    print("Generating icons from assets/brand/connector-tile.svg...")
    result = subprocess.run([sys.executable, str(script)], cwd=str(root))
    if result.returncode != 0:
        print("\nIcon generation failed!")
        sys.exit(1)


def build():
    """Build the application using PyInstaller."""
    root = Path(__file__).parent
    spec_file = root / 'agimate_desktop.spec'

    if not spec_file.exists():
        print(f"Error: {spec_file} not found")
        sys.exit(1)

    icons()

    print("Building Agimate Desktop...")

    result = subprocess.run(
        [sys.executable, '-m', 'PyInstaller', str(spec_file), '--noconfirm'],
        cwd=str(root)
    )

    if result.returncode == 0:
        print("\nBuild successful!")
        print(f"Output: {root / 'dist'}")
    else:
        print("\nBuild failed!")
        sys.exit(1)


def build_dmg():
    """Build macOS DMG installer."""
    if sys.platform != 'darwin':
        print("DMG build is only supported on macOS.")
        sys.exit(1)

    root = Path(__file__).parent
    script = root / 'build_dmg.sh'

    if not script.exists():
        print(f"Error: {script} not found")
        sys.exit(1)

    result = subprocess.run(['bash', str(script)], cwd=str(root))
    if result.returncode != 0:
        print("\nDMG build failed!")
        sys.exit(1)


def main():
    if len(sys.argv) < 2:
        print("Usage: python build.py [clean|icons|build|dmg|all]")
        sys.exit(1)

    command = sys.argv[1]

    if command == 'clean':
        clean()
    elif command == 'icons':
        icons()
    elif command == 'build':
        build()
    elif command == 'dmg':
        build_dmg()
    elif command == 'all':
        clean()
        build()
        if sys.platform == 'darwin':
            build_dmg()
    else:
        print(f"Unknown command: {command}")
        print("Available commands: clean, icons, build, dmg, all")
        sys.exit(1)


if __name__ == '__main__':
    main()
