from __future__ import annotations

import shutil
import tarfile
from collections.abc import Callable
from io import BytesIO
from pathlib import Path

import pytest

from pypi_package_changelog_generator import archive_diff
from pypi_package_changelog_generator.archive_diff import ArchiveDiffError, extract_archive


def _build_tar_archive(
    configure: Callable[[tarfile.TarFile], None],
) -> bytes:
    buffer = BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        configure(archive)
    return buffer.getvalue()


def _add_file(archive: tarfile.TarFile, name: str, content: bytes) -> None:
    info = tarfile.TarInfo(name)
    info.size = len(content)
    archive.addfile(info, BytesIO(content))


def test_extract_archive_extracts_regular_files() -> None:
    def configure(archive: tarfile.TarFile) -> None:
        directory = tarfile.TarInfo("package/")
        directory.type = tarfile.DIRTYPE
        archive.addfile(directory)
        _add_file(archive, "package/module.py", b"print('ok')\n")

    content = _build_tar_archive(configure)

    extracted = extract_archive(content)
    try:
        assert extracted.root.name == "package"
        assert (extracted.root / "module.py").read_text(encoding="utf-8") == "print('ok')\n"
    finally:
        extracted.cleanup()


@pytest.mark.parametrize(
    ("name", "entry_type"),
    [
        ("../escape.txt", tarfile.REGTYPE),
        ("/absolute.txt", tarfile.REGTYPE),
        ("C:drive-relative.txt", tarfile.REGTYPE),
        ("//server/share.txt", tarfile.REGTYPE),
        ("package/link", tarfile.SYMTYPE),
        ("package/hardlink", tarfile.LNKTYPE),
        ("package/fifo", tarfile.FIFOTYPE),
    ],
)
def test_extract_archive_rejects_unsafe_entries(name: str, entry_type: bytes) -> None:
    def configure(archive: tarfile.TarFile) -> None:
        info = tarfile.TarInfo(name)
        info.type = entry_type
        if entry_type == tarfile.REGTYPE:
            payload = b"blocked\n"
            info.size = len(payload)
            archive.addfile(info, BytesIO(payload))
            return
        if entry_type in {tarfile.SYMTYPE, tarfile.LNKTYPE}:
            info.linkname = "target"
        archive.addfile(info)

    with pytest.raises(ArchiveDiffError, match="unsafe entry"):
        extract_archive(_build_tar_archive(configure))


def test_extract_archive_cleans_up_tempdir_on_unsafe_entry(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    class TrackingTemporaryDirectory:
        instances: list[TrackingTemporaryDirectory] = []

        def __init__(self, prefix: str) -> None:
            self.name = str(tmp_path / f"{prefix}{len(self.instances)}")
            Path(self.name).mkdir()
            self.cleaned = False
            self.instances.append(self)

        def cleanup(self) -> None:
            self.cleaned = True
            shutil.rmtree(self.name, ignore_errors=True)

    monkeypatch.setattr(
        archive_diff.tempfile, "TemporaryDirectory", TrackingTemporaryDirectory
    )

    content = _build_tar_archive(
        lambda archive: _add_file(archive, "../escape.txt", b"blocked\n")
    )

    with pytest.raises(ArchiveDiffError):
        extract_archive(content)

    assert TrackingTemporaryDirectory.instances
    temp_dir = TrackingTemporaryDirectory.instances[0]
    assert temp_dir.cleaned is True
    assert not Path(temp_dir.name).exists()
