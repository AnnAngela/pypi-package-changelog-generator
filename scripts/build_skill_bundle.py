#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import packaging


def build_skill_bundle(output_dir: Path) -> Path:
    repo_root = Path(__file__).resolve().parent.parent
    skill_dir = repo_root / "skills" / "pypi-package-changelog"
    runtime_src_dir = repo_root / "src" / "pypi_package_changelog_generator"
    packaging_dir = Path(packaging.__file__).resolve().parent

    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)

    _copy_tree(skill_dir, output_dir)
    _copy_tree(runtime_src_dir, output_dir / "src" / runtime_src_dir.name)
    _copy_tree(packaging_dir, output_dir / "vendor" / packaging_dir.name)
    return output_dir


def _copy_tree(source: Path, destination: Path) -> None:
    shutil.copytree(
        source,
        destination,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a self-contained ClawHub skill bundle for publication."
    )
    parser.add_argument(
        "--output", required=True, help="Directory to write the bundle into."
    )
    args = parser.parse_args()

    bundle_dir = build_skill_bundle(Path(args.output).resolve())
    print(bundle_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
