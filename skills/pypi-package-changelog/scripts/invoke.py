#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
from pathlib import Path


def main() -> int:
    if sys.version_info < (3, 12):
        print("Python 3.12 or newer is required.", file=sys.stderr)
        return 2

    repo_root = Path(__file__).resolve().parents[3]
    src_dir = repo_root / "src"
    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))

    from pypi_package_changelog_generator.cli import main as cli_main

    argv = sys.argv[1:]
    if "--github-token" not in argv and os.getenv("GITHUB_TOKEN"):
        argv = [*argv, "--github-token", os.environ["GITHUB_TOKEN"]]
    return cli_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
