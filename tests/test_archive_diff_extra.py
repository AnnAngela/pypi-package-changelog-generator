from __future__ import annotations

import tarfile
import tempfile
from io import BytesIO
from pathlib import Path

import pytest

from pypi_package_changelog_generator.archive_diff import (
    ArchiveComparison,
    ArchiveDiffError,
    ExtractedArchive,
    _decode_lines,
    _is_safe_tar_member,
    _should_skip,
    build_file_changes,
    compare_release_archives,
    extract_archive,
)
from pypi_package_changelog_generator.pypi_client import PypiClientError


def _tar_bytes(files: dict[str, bytes]) -> bytes:
    buffer = BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        for name, content in files.items():
            info = tarfile.TarInfo(name)
            if name.endswith("/"):
                info.type = tarfile.DIRTYPE
                archive.addfile(info)
                continue
            info.size = len(content)
            archive.addfile(info, BytesIO(content))
    return buffer.getvalue()


def test_extract_archive_returns_temp_root_when_multiple_top_level_entries() -> None:
    extracted = extract_archive(
        _tar_bytes({"package/module.py": b"print('ok')\n", "README.md": b"# demo\n"})
    )
    try:
        assert extracted.root.name.startswith("pypi-changelog-")
        assert (extracted.root / "README.md").exists()
    finally:
        extracted.cleanup()


def test_compare_release_archives_success_and_cleanup() -> None:
    class FakeClient:
        def find_sdist_url(self, payload: dict[str, object]) -> str | None:
            return payload["sdist"]  # type: ignore[index]

        def download_bytes(self, url: str) -> bytes:
            if url.endswith("from.tar.gz"):
                return _tar_bytes({"pkg/module.py": b"before\n", "pkg/old.txt": b"same\n"})
            return _tar_bytes({"pkg/module.py": b"after\n", "pkg/new.txt": b"same\n"})

    comparison = compare_release_archives(
        FakeClient(),
        {"sdist": "https://files/from.tar.gz"},
        {"sdist": "https://files/to.tar.gz"},
    )
    try:
        statuses = {change["status"] for change in comparison.file_changes}
        assert statuses == {"modified", "renamed"}
    finally:
        comparison.cleanup()


def test_compare_release_archives_reports_missing_sdist_and_wrapped_download_errors() -> None:
    class MissingClient:
        def find_sdist_url(self, payload: dict[str, object]) -> str | None:
            return None

    with pytest.raises(ArchiveDiffError, match="source distribution is required"):
        compare_release_archives(MissingClient(), {}, {})

    class BrokenClient:
        def find_sdist_url(self, payload: dict[str, object]) -> str | None:
            return "https://files/demo.tar.gz"

        def download_bytes(self, url: str) -> bytes:
            raise PypiClientError("download", "failed", retryable=True)

    with pytest.raises(ArchiveDiffError) as exc_info:
        compare_release_archives(BrokenClient(), {}, {})
    assert exc_info.value.code == "download"
    assert exc_info.value.retryable is True


def test_build_file_changes_covers_added_removed_modified_binary_and_skipped_files(tmp_path: Path) -> None:
    from_root = tmp_path / "from"
    to_root = tmp_path / "to"
    from_root.mkdir()
    to_root.mkdir()
    (from_root / "pkg").mkdir()
    (to_root / "pkg").mkdir()
    (from_root / "pkg" / "same.py").write_text("value = 1\n", encoding="utf-8")
    (to_root / "pkg" / "same.py").write_text("value = 2\n", encoding="utf-8")
    (from_root / "pkg" / "old.txt").write_text("rename me\n", encoding="utf-8")
    (to_root / "pkg" / "new.txt").write_text("rename me\n", encoding="utf-8")
    (to_root / "pkg" / "added.txt").write_text("one\ntwo\n", encoding="utf-8")
    (from_root / "pkg" / "removed.txt").write_text("gone\n", encoding="utf-8")
    (from_root / "pkg" / "unchanged.txt").write_text("same\n", encoding="utf-8")
    (to_root / "pkg" / "unchanged.txt").write_text("same\n", encoding="utf-8")
    (from_root / "pkg" / "image.bin").write_bytes(b"\0before")
    (to_root / "pkg" / "image.bin").write_bytes(b"\0after")
    (from_root / ".git").mkdir()
    (from_root / ".git" / "ignored.txt").write_text("ignore\n", encoding="utf-8")
    (to_root / "pkg" / "compiled.pyc").write_bytes(b"compiled")

    changes = build_file_changes(from_root, to_root)
    by_path = {change["path"]: change for change in changes}

    assert by_path["pkg/new.txt"]["status"] == "renamed"
    assert by_path["pkg/added.txt"]["additions"] == 2
    assert by_path["pkg/removed.txt"]["deletions"] == 1
    assert by_path["pkg/same.py"]["status"] == "modified"
    assert by_path["pkg/same.py"]["patch"].startswith("--- a/pkg/same.py")
    assert by_path["pkg/image.bin"]["patch"] is None
    assert _decode_lines(b"line1\nline2\n") == ["line1\n", "line2\n"]
    assert _should_skip(Path(".git/ignored.txt")) is True
    assert _should_skip(Path("pkg/compiled.pyc")) is True
    assert _should_skip(Path("pkg/module.py")) is False


def test_is_safe_tar_member_rejects_symlink_escape(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (root / "linked").symlink_to(outside, target_is_directory=True)

    member = tarfile.TarInfo("linked/escape.txt")
    member.size = 1

    assert _is_safe_tar_member(root.resolve(), member) is False


def test_archive_cleanup_helpers_remove_temporary_directories() -> None:
    temp_a = tempfile.TemporaryDirectory()
    temp_b = tempfile.TemporaryDirectory()
    archive_a = ExtractedArchive(root=Path(temp_a.name), temp_dir=temp_a)
    archive_b = ExtractedArchive(root=Path(temp_b.name), temp_dir=temp_b)
    comparison = ArchiveComparison(
        from_archive=archive_a,
        to_archive=archive_b,
        file_changes=[],
    )

    comparison.cleanup()

    assert not Path(temp_a.name).exists()
    assert not Path(temp_b.name).exists()
