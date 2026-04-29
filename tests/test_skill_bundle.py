from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest


def _get_target_python() -> str:
    if sys.version_info >= (3, 14):
        return sys.executable

    python_314 = shutil.which("python3.14")
    if python_314:
        return python_314

    pytest.skip("Python 3.14 is required to validate the self-contained skill bundle.")


def test_self_contained_skill_bundle_runs_in_isolated_mode(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parent.parent
    bundle_dir = tmp_path / "bundle"
    target_python = _get_target_python()

    build = subprocess.run(
        [
            sys.executable,
            str(repo_root / "scripts" / "build_skill_bundle.py"),
            "--output",
            str(bundle_dir),
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert build.returncode == 0, build.stderr

    result = subprocess.run(
        [target_python, "-S", str(bundle_dir / "scripts" / "invoke.py"), "--help"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "pypi-package-changelog" in result.stdout
