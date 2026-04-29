from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def test_invoke_reads_github_token_from_env_without_putting_it_in_argv(
    tmp_path: Path,
) -> None:
    repo_root = Path(__file__).resolve().parent.parent
    skill_root = repo_root / "skills" / "pypi-package-changelog-generator"
    bundle_dir = tmp_path / "bundle"
    scripts_dir = bundle_dir / "scripts"
    package_dir = bundle_dir / "src" / "pypi_package_changelog_generator"

    scripts_dir.mkdir(parents=True)
    package_dir.mkdir(parents=True)

    (scripts_dir / "invoke.py").write_text(
        (skill_root / "scripts" / "invoke.py").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (package_dir / "__init__.py").write_text("", encoding="utf-8")
    (package_dir / "cli.py").write_text(
        "from __future__ import annotations\n"
        "\n"
        "import json\n"
        "import os\n"
        "\n"
        "def main(argv=None):\n"
        "    print(json.dumps({'argv': argv, 'token_from_env': bool(os.getenv('GITHUB_TOKEN'))}))\n"
        "    return 0\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "-S",
            str(scripts_dir / "invoke.py"),
            "--package",
            "demo",
            "--version-range",
            "latest-1",
        ],
        cwd=bundle_dir,
        capture_output=True,
        text=True,
        env={**os.environ, "GITHUB_TOKEN": "secret-token"},
        check=False,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["token_from_env"] is True
    assert payload["argv"] == [
        "--package",
        "demo",
        "--version-range",
        "latest-1",
    ]
    assert "--github-token" not in payload["argv"]
    assert "secret-token" not in payload["argv"]
