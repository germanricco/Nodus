import hashlib
import json
import os
import sys
from datetime import datetime, timedelta

import pytest
from factories import manifest_answer

from nodus.services.errors import UpdateError
from nodus.services.external.release_manifest import InstallerFile
from nodus.services.external.update_service import (
    CHECK_EVERY,
    INSTALLER_ARGUMENTS,
    RETRY_AFTER_FAILURE,
    RETRY_MARGIN,
    Installer,
    Release,
    UpdateCheck,
    UpdateService,
    retry_delay,
)

RELEASE_PAGE = "https://github.com/germanricco/Nodus/releases/tag/v0.3.0"


# As on Windows, unless a test says otherwise with ``on_linux``.
pytestmark = pytest.mark.usefixtures("as_on_windows")


def checked(answer: bytes) -> UpdateCheck:
    return UpdateService("0.2.0", lambda _url: answer).check()


def test_newer_release_is_reported_from_the_release_page_not_the_api():
    """GitHub's API answers only 60 requests an hour to a connection without an
    account; ``latest.json`` is a plain download from the release page."""
    requested = []

    def fetch(url):
        requested.append(url)
        return manifest_answer("0.3.0")

    check = UpdateService("0.2.0", fetch).check()

    assert check == UpdateCheck(Release("0.3.0", RELEASE_PAGE))
    assert (check.failed, check.next_in) == (False, CHECK_EVERY)
    assert requested == [
        "https://github.com/germanricco/Nodus/releases/latest/download/latest.json"
    ]


@pytest.mark.parametrize("version", ["0.2.0", "0.1.1"])
def test_same_or_older_release_is_not_reported(version):
    assert checked(manifest_answer(version)) == UpdateCheck()


@pytest.mark.parametrize(
    "body",
    [
        b"not json",
        b"{}",
        b"[]",
        b"<html>Not Found</html>",  # a release published without its latest.json
        manifest_answer("beta"),
        manifest_answer("0.3.0").replace(b'"format": 1', b'"format": 2'),
        json.dumps({"format": 1, "version": "0.3.0", "notes": None, "installers": {}}).encode(),
    ],
)
def test_unexpected_answer_finds_nothing_and_tries_again_later(body):
    check = checked(body)

    assert check == UpdateCheck(retry_in=RETRY_AFTER_FAILURE)
    assert check.failed and check.next_in == RETRY_AFTER_FAILURE


def test_network_error_finds_nothing_and_tries_again_later():
    def fetch(_url):
        raise OSError("sin conexión")

    assert UpdateService("0.2.0", fetch).check() == UpdateCheck(retry_in=RETRY_AFTER_FAILURE)


class RateLimitError(OSError):
    """As urllib's HTTPError when GitHub limits a connection: it carries the headers."""

    def __init__(self, headers: dict[str, str]) -> None:
        super().__init__("HTTP Error 403: rate limit exceeded")
        self.headers = headers


def test_a_limited_connection_tries_again_when_github_lets_it():
    now = datetime(2026, 11, 25, 8, 36).astimezone()
    reset = int((now + timedelta(minutes=8)).timestamp())

    delay = retry_delay(RateLimitError({"X-RateLimit-Reset": str(reset)}), now)

    assert delay == timedelta(minutes=8) + RETRY_MARGIN


def test_a_reset_already_past_or_unreadable_still_waits_a_little():
    now = datetime(2026, 11, 25, 8, 36).astimezone()
    past = int((now - timedelta(minutes=5)).timestamp())

    assert retry_delay(RateLimitError({"X-RateLimit-Reset": str(past)}), now) == RETRY_MARGIN
    assert retry_delay(RateLimitError({"X-RateLimit-Reset": "soon"}), now) == RETRY_AFTER_FAILURE


def test_a_limited_check_says_when_to_try_again():
    def fetch(_url):
        reset = datetime.now().astimezone() + timedelta(minutes=10)
        raise RateLimitError({"X-RateLimit-Reset": str(int(reset.timestamp()))})

    check = UpdateService("0.2.0", fetch).check()

    assert check.release is None
    assert timedelta(minutes=10) <= check.retry_in <= timedelta(minutes=10) + RETRY_MARGIN


def test_release_notes_come_without_the_repeated_subject_line():
    notes = "Nodus 0.3.0\n\nNovedades:\n\n- Algo nuevo."

    release = checked(manifest_answer("0.3.0", notes)).release

    assert release.notes == "Novedades:\n\n- Algo nuevo."


def test_the_notes_come_in_the_language_nodus_is_in(english):
    notes = "Nodus 1.10.0\n\n- Algo nuevo.\n\n---\n\n<!-- en -->\n\n- Something new."

    release = checked(manifest_answer("1.10.0", notes)).release

    assert release.notes == "- Something new."


def test_release_without_notes_has_empty_notes():
    assert checked(manifest_answer("0.3.0")).release.notes == ""


# Installing


INSTALLER_BYTES = b"setup program" * 1000
INSTALLER_URL = (
    "https://github.com/germanricco/Nodus/releases/download/v0.3.0/Nodus-Setup-0.3.0.exe"
)


def installer_asset(content: bytes = INSTALLER_BYTES, name: str = "Nodus-Setup-0.3.0.exe"):
    """An installer as ``latest.json`` lists it: its name, size and SHA-256."""
    return {name: InstallerFile(len(content), hashlib.sha256(content).hexdigest())}


def release_with(assets: list[dict[str, InstallerFile]]) -> Release:
    installers = {name: file for asset in assets for name, file in asset.items()}
    return checked(manifest_answer("0.3.0", installers=installers)).release


def chunks(data: bytes, size: int = 1000):
    return [data[start : start + size] for start in range(0, len(data), size)]


def updater(tmp_path, stream=None, launch=None) -> UpdateService:
    return UpdateService(
        "0.2.0",
        stream=stream or (lambda _url: iter(chunks(INSTALLER_BYTES))),
        downloads_dir=tmp_path / "updates",
        launch=launch,
    )


def test_release_carries_its_installer():
    assert release_with([installer_asset()]).installer == Installer(
        INSTALLER_URL, len(INSTALLER_BYTES), hashlib.sha256(INSTALLER_BYTES).hexdigest()
    )


def test_installer_needs_the_right_name():
    other_version = installer_asset(name="Nodus-Setup-0.2.0.exe")

    assert release_with([other_version]).installer is None


def test_download_saves_the_checked_installer(tmp_path):
    progress = []

    path = updater(tmp_path).download(release_with([installer_asset()]), progress.append)

    assert path == tmp_path / "updates" / "Nodus-Setup-0.3.0.exe"
    assert path.read_bytes() == INSTALLER_BYTES
    assert progress[-1] == len(INSTALLER_BYTES)
    assert progress == sorted(progress)


def test_damaged_download_is_rejected_and_removed(tmp_path):
    damaged = lambda _url: iter([INSTALLER_BYTES[:-1] + b"?"])  # noqa: E731

    with pytest.raises(UpdateError, match="dañada"):
        updater(tmp_path, damaged).download(release_with([installer_asset()]))

    assert list((tmp_path / "updates").iterdir()) == []


def test_connection_lost_midway_is_an_update_error(tmp_path):
    def cut(_url):
        yield INSTALLER_BYTES[:1000]
        raise OSError("se cortó la conexión")

    with pytest.raises(UpdateError, match="Revisa la conexión") as raised:
        updater(tmp_path, cut).download(release_with([installer_asset()]))

    assert raised.value.detail == "se cortó la conexión"

    assert list((tmp_path / "updates").iterdir()) == []


def test_cancelled_download_leaves_nothing(tmp_path):
    progress = []

    path = updater(tmp_path).download(
        release_with([installer_asset()]), progress.append, cancelled=lambda: len(progress) >= 3
    )

    assert path is None
    assert len(progress) == 3
    assert list((tmp_path / "updates").iterdir()) == []


def test_release_without_installer_cannot_be_downloaded(tmp_path):
    with pytest.raises(UpdateError):
        updater(tmp_path).download(release_with([]))


def test_install_starts_the_installer_silently_and_asks_it_to_reopen_nodus(tmp_path):
    started = []
    installer = tmp_path / "Nodus-Setup-0.3.0.exe"

    updater(tmp_path, launch=started.append).install(installer)

    assert started == [[str(installer), *INSTALLER_ARGUMENTS]]
    assert "/RELAUNCH=1" in INSTALLER_ARGUMENTS


def test_installer_that_cannot_start_is_an_update_error(tmp_path):
    def broken(_command):
        raise OSError("acceso denegado")

    with pytest.raises(UpdateError, match="No se pudo abrir el instalador") as raised:
        updater(tmp_path, launch=broken).install(tmp_path / "setup.exe")

    assert raised.value.detail == "acceso denegado"


def test_only_the_installed_program_installs_updates(tmp_path):
    release = release_with([installer_asset()])

    assert updater(tmp_path, launch=lambda _command: None).can_install(release)
    assert not updater(tmp_path).can_install(release)  # run from the source code
    assert not updater(tmp_path, launch=lambda _command: None).can_install(release_with([]))
    assert not UpdateService.for_this_program("0.2.0").can_install(release)


def test_clean_removes_downloaded_installers(tmp_path):
    service = updater(tmp_path)
    service.download(release_with([installer_asset()]))

    service.clean()
    service.clean()  # nothing left: still fine

    assert not service.downloads_dir.exists()


# Installing on Linux, where the release file is the AppImage itself

APPIMAGE_BYTES = b"new appimage" * 1000


def appimage_asset():
    return installer_asset(APPIMAGE_BYTES, "Nodus-0.3.0-x86_64.AppImage")


@pytest.fixture
def on_linux(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")


@pytest.fixture
def appimage(tmp_path):
    """The AppImage that is running, in a folder of the user's with a space in it."""
    path = tmp_path / "Mis programas" / "Nodus-0.2.0-x86_64.AppImage"
    path.parent.mkdir()
    path.write_bytes(b"old appimage")
    path.chmod(0o755)
    return path


def linux_updater(tmp_path, appimage) -> UpdateService:
    return UpdateService(
        "0.2.0",
        stream=lambda _url: iter(chunks(APPIMAGE_BYTES)),
        downloads_dir=tmp_path / "updates",
        appimage=appimage,
    )


def test_on_linux_the_release_file_is_the_appimage(on_linux):
    release = release_with([installer_asset(), appimage_asset()])

    assert release.installer.url == INSTALLER_URL.replace(
        "Nodus-Setup-0.3.0.exe", "Nodus-0.3.0-x86_64.AppImage"
    )
    assert release.installer.size == len(APPIMAGE_BYTES)


def test_the_new_appimage_takes_the_place_and_name_of_the_old(on_linux, tmp_path, appimage):
    service = linux_updater(tmp_path, appimage)
    downloaded = service.download(release_with([appimage_asset()]))

    service.install(downloaded)

    assert appimage.read_bytes() == APPIMAGE_BYTES
    assert os.access(appimage, os.X_OK)
    assert sorted(p.name for p in appimage.parent.iterdir()) == [appimage.name]
    assert not service.reopens_by_itself  # Nodus restarts over the new one


def test_a_folder_it_cannot_write_keeps_the_old_appimage(on_linux, monkeypatch, tmp_path, appimage):
    service = linux_updater(tmp_path, appimage)
    downloaded = service.download(release_with([appimage_asset()]))

    # The swap is refused, as in a folder without write permission; failing it here,
    # rather than with chmod, runs on every system and as root.
    def refuse(_source, _destination):
        raise PermissionError("Permission denied")

    monkeypatch.setattr(os, "replace", refuse)
    with pytest.raises(UpdateError, match="No se pudo reemplazar Nodus"):
        service.install(downloaded)

    assert appimage.read_bytes() == b"old appimage"
    assert sorted(p.name for p in appimage.parent.iterdir()) == [appimage.name]


def test_only_the_appimage_installs_updates_on_linux(on_linux, monkeypatch, tmp_path, appimage):
    release = release_with([appimage_asset()])
    assert linux_updater(tmp_path, appimage).can_install(release)
    assert not UpdateService.for_this_program("0.2.0").can_install(release)  # source code

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setenv("APPIMAGE", str(appimage))
    assert UpdateService.for_this_program("0.2.0").can_install(release)


def test_the_windows_installer_reopens_nodus_by_itself(tmp_path):
    assert updater(tmp_path, launch=lambda _command: None).reopens_by_itself
