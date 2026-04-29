from __future__ import annotations

from pypi_package_changelog_generator.budget import _prioritize_files, apply_budget
from pypi_package_changelog_generator.models import ChangelogResult


def test_apply_budget_truncates_patches_and_counts_omissions() -> None:
    result = ChangelogResult(
        package="demo",
        resolved_versions={"from": "1.0.0", "to": "2.0.0", "range": None},
        mode="git",
        commits=[{"sha": "1"}, {"sha": "2"}],
        reviews=[{"id": 1}],
        file_changes=[
            {"path": "pkg/module.py", "status": "modified", "changes": 2, "patch": "abcdef"},
            {"path": "pkg/readme.md", "status": "modified", "changes": 4, "patch": "ghijkl"},
            {"path": "pkg/short.txt", "status": "modified", "changes": 5, "patch": "mnopqr"},
            {"path": "README.md", "status": "modified", "changes": 1, "patch": None},
        ],
    )

    apply_budget(result, max_commits=2, max_reviews=1, max_files=3, max_patch_chars=4)

    assert result.truncation.truncated is True
    assert result.truncation.reason == "patch excerpts were shortened to fit the evidence budget"
    assert result.truncation.omitted_commits == 0
    assert result.truncation.omitted_files == 1
    assert result.file_changes[0]["patch"] == "abcdef"
    assert result.file_changes[1]["patch"] == "mnop\n...<truncated>...\n"
    assert result.file_changes[2]["patch"] == "ghijkl"


def test_apply_budget_sets_review_reason_when_only_reviews_are_truncated() -> None:
    result = ChangelogResult(
        package="demo",
        resolved_versions={"from": "1.0.0", "to": "2.0.0", "range": None},
        mode="git",
        reviews=[{"id": 1}, {"id": 2}],
    )

    apply_budget(result, max_reviews=1)

    assert result.truncation.truncated is True
    assert result.truncation.reason == "review list exceeded the evidence budget"


def test_prioritize_files_prefers_metadata_python_and_removed_files() -> None:
    ordered = _prioritize_files(
        [
            {"path": "README.md", "status": "modified", "changes": 10},
            {"path": "pkg/module.py", "status": "modified", "changes": 1},
            {"path": "setup.cfg", "status": "removed", "changes": 0},
            {"path": None, "status": "renamed", "changes": 5},
        ]
    )

    assert [change["path"] for change in ordered] == ["setup.cfg", "pkg/module.py", None, "README.md"]
