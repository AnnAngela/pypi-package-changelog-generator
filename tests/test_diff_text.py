from __future__ import annotations

from pypi_package_changelog_generator.diff_text import (
    format_git_diff_patch,
    keeps_full_patch,
    omit_diff_body,
    truncate_patch,
)


def test_keeps_full_patch_and_omit_diff_body() -> None:
    assert keeps_full_patch("pkg/module.py") is True
    assert keeps_full_patch("README.md") is True
    assert keeps_full_patch("pkg/data.txt") is False
    assert omit_diff_body("pkg/data.txt", "added") is True
    assert omit_diff_body("pkg/data.txt", "removed") is True
    assert omit_diff_body("pkg/data.txt", "modified") is False


def test_format_git_diff_patch_wraps_modified_hunks() -> None:
    patch = format_git_diff_patch(
        path="pkg/module.py",
        status="modified",
        patch="@@ -1 +1 @@\n-old\n+new\n",
    )

    assert patch == (
        "diff --git a/pkg/module.py b/pkg/module.py\n"
        "--- a/pkg/module.py\n"
        "+++ b/pkg/module.py\n"
        "@@ -1 +1 @@\n"
        "-old\n"
        "+new\n"
    )


def test_format_git_diff_patch_hides_non_python_added_removed_content_and_formats_renames() -> None:
    added = format_git_diff_patch(
        path="pkg/data.txt",
        status="added",
        patch="@@ -0,0 +1 @@\n+value\n",
    )
    removed = format_git_diff_patch(
        path="pkg/data.txt",
        status="removed",
        patch="@@ -1 +0,0 @@\n-value\n",
    )
    renamed = format_git_diff_patch(
        path="pkg/new.txt",
        previous_path="pkg/old.txt",
        status="renamed",
    )

    assert added == "diff --git a/pkg/data.txt b/pkg/data.txt\nnew file mode 100644\n"
    assert removed == (
        "diff --git a/pkg/data.txt b/pkg/data.txt\ndeleted file mode 100644\n"
    )
    assert renamed == (
        "diff --git a/pkg/old.txt b/pkg/new.txt\n"
        "rename from pkg/old.txt\n"
        "rename to pkg/new.txt\n"
    )


def test_format_git_diff_patch_formats_binary_notes_and_truncates() -> None:
    patch = format_git_diff_patch(
        path="pkg/image.bin",
        status="removed",
        binary=True,
    )

    assert patch == (
        "diff --git a/pkg/image.bin b/pkg/image.bin\n"
        "deleted file mode 100644\n"
        "Binary files a/pkg/image.bin and /dev/null differ\n"
    )
    assert truncate_patch("abcdef", 4) == "abcd\n...<truncated>...\n"
