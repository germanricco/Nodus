import hashlib
import json

import pytest

from nodus.services.errors import UpdateError
from nodus.services.update_service import (
    INSTALLER_ARGUMENTS,
    LATEST_RELEASE_API,
    Installer,
    Release,
    UpdateService,
    parse_version,
)

RELEASE_PAGE = "https://github.com/germanricco/Nodus/releases/tag/v0.3.0"


def answer(tag: str) -> bytes:
    return json.dumps({"tag_name": tag, "html_url": RELEASE_PAGE}).encode()


@pytest.mark.parametrize(
    ("text", "expected"),
    [("v0.2.0", (0, 2, 0)), ("0.2.0", (0, 2, 0)), ("1.10", (1, 10))],
)
def test_parse_version(text, expected):
    assert parse_version(text) == expected


def test_versions_compare_as_numbers():
    assert parse_version("0.10.0") > parse_version("0.9.1")


def test_newer_release_is_reported():
    requested = []

    def fetch(url):
        requested.append(url)
        return answer("v0.3.0")

    assert UpdateService("0.2.0", fetch).check() == Release("0.3.0", RELEASE_PAGE)
    assert requested == [LATEST_RELEASE_API]


@pytest.mark.parametrize("tag", ["v0.2.0", "v0.1.1"])
def test_same_or_older_release_is_not_reported(tag):
    assert UpdateService("0.2.0", lambda _url: answer(tag)).check() is None


@pytest.mark.parametrize(
    "body",
    [b"not json", b"{}", b"[]", json.dumps({"tag_name": "beta", "html_url": "x"}).encode()],
)
def test_unexpected_answer_is_ignored(body):
    assert UpdateService("0.2.0", lambda _url: body).check() is None


def test_network_error_is_ignored():
    def fetch(_url):
        raise OSError("sin conexión")

    assert UpdateService("0.2.0", fetch).check() is None


def test_release_notes_come_without_the_repeated_subject_line():
    body = "Nodus 0.3.0\n\nNovedades:\n\n- Algo nuevo."
    data = {"tag_name": "v0.3.0", "html_url": RELEASE_PAGE, "body": body}

    release = UpdateService("0.2.0", lambda _url: json.dumps(data).encode()).check()

    assert release.notes == "Novedades:\n\n- Algo nuevo."


def test_release_without_notes_has_empty_notes():
    assert UpdateService("0.2.0", lambda _url: answer("v0.3.0")).check().notes == ""


# Installing


INSTALLER_BYTES = b"setup program" * 1000
INSTALLER_URL = (
    "https://github.com/germanricco/Nodus/releases/download/v0.3.0/Nodus-Setup-0.3.0.exe"
)


def installer_asset(**changes) -> dict:
    asset = {
        "name": "Nodus-Setup-0.3.0.exe",
        "size": len(INSTALLER_BYTES),
        "digest": f"sha256:{hashlib.sha256(INSTALLER_BYTES).hexdigest()}",
        "browser_download_url": INSTALLER_URL,
    }
    return asset | changes


def release_with(assets: list[dict]) -> Release:
    data = {"tag_name": "v0.3.0", "html_url": RELEASE_PAGE, "assets": assets}
    return UpdateService("0.2.0", lambda _url: json.dumps(data).encode()).check()


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


@pytest.mark.parametrize(
    "asset",
    [
        installer_asset(name="Nodus-Setup-0.2.0.exe"),  # another version's installer
        installer_asset(digest=None),  # nothing to check the download against
        installer_asset(digest="md5:abc"),
    ],
)
def test_installer_needs_the_right_name_and_a_sha256(asset):
    assert release_with([asset]).installer is None


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

    with pytest.raises(UpdateError, match="se cortó la conexión"):
        updater(tmp_path, cut).download(release_with([installer_asset()]))

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

    with pytest.raises(UpdateError, match="acceso denegado"):
        updater(tmp_path, launch=broken).install(tmp_path / "setup.exe")


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
