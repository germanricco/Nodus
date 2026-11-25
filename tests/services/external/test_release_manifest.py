"""``latest.json``: written by the release workflow, read by every Nodus that checks for a
new version, so what one writes the other must read back the same."""

import hashlib
import json

import pytest

from nodus.services.external.release_manifest import (
    InstallerFile,
    ReleaseManifest,
    build_manifest,
    installer_names,
)

NOTES = "Nodus 1.12.2\n\n- Algo nuevo.\n\n---\n\n<!-- en -->\n\n- Something new."


@pytest.fixture
def release_folder(tmp_path):
    """The installers of 1.12.2 as the workflow downloads them, and something else."""
    for system, name in installer_names("1.12.2").items():
        (tmp_path / name).write_bytes(f"installer for {system}".encode())
    (tmp_path / "release-notes.md").write_text(NOTES, encoding="utf-8")
    return tmp_path


def test_it_lists_each_installer_with_its_size_and_sha256(release_folder):
    manifest = build_manifest("1.12.2", NOTES, release_folder)

    content = b"installer for win32"
    assert manifest.installers == {
        "Nodus-Setup-1.12.2.exe": InstallerFile(len(content), hashlib.sha256(content).hexdigest()),
        "Nodus-1.12.2-x86_64.AppImage": InstallerFile(
            len(b"installer for linux"), hashlib.sha256(b"installer for linux").hexdigest()
        ),
    }
    assert (manifest.version, manifest.notes) == ("1.12.2", NOTES)


def test_what_is_written_reads_back_the_same(release_folder):
    manifest = build_manifest("1.12.2", NOTES, release_folder)

    assert ReleaseManifest.from_json(manifest.to_json().encode()) == manifest


def test_the_file_says_its_format_for_a_later_nodus(release_folder):
    data = json.loads(build_manifest("1.12.2", NOTES, release_folder).to_json())

    assert data["format"] == 1


def test_a_missing_installer_stops_the_release(release_folder):
    (release_folder / "Nodus-1.12.2-x86_64.AppImage").unlink()

    with pytest.raises(FileNotFoundError, match="AppImage"):
        build_manifest("1.12.2", NOTES, release_folder)


@pytest.mark.parametrize(
    "data",
    [
        b"",
        b"not json",
        b"[]",
        b'{"format": 1}',
        b'{"format": 2, "version": "9.0.0", "notes": "", "installers": {}}',
        b'{"format": 1, "version": 9, "notes": "", "installers": {}}',
        b'{"format": 1, "version": "9.0.0", "notes": "", "installers": {"a": {"size": 1}}}',
        b'{"format": 1, "version": "9.0.0", "notes": "", "installers": []}',
    ],
)
def test_anything_else_is_not_a_manifest(data):
    with pytest.raises(ValueError):
        ReleaseManifest.from_json(data)
