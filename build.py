#!/usr/bin/env python3
"""Build script for System Agent."""

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


def build():
    """Build the application using PyInstaller."""
    root = Path(__file__).parent
    spec_file = root / 'system_agent.spec'

    if not spec_file.exists():
        print(f"Error: {spec_file} not found")
        sys.exit(1)

    print("Building System Agent...")

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


def main():
    if len(sys.argv) < 2:
        print("Usage: python build.py [clean|build|all]")
        sys.exit(1)

    command = sys.argv[1]

    if command == 'clean':
        clean()
    elif command == 'build':
        build()
    elif command == 'all':
        clean()
        build()
    else:
        print(f"Unknown command: {command}")
        print("Available commands: clean, build, all")
        sys.exit(1)


if __name__ == '__main__':
    main()
