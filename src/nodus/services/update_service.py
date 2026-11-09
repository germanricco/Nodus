"""Checks GitHub for a newer published version of Nodus, and installs it on request."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from nodus.links import REPOSITORY
from nodus.services.errors import UpdateError
from nodus.services.http import Fetch, Stream, downloader, streamer

LATEST_RELEASE_API = f"https://api.github.com/repos/{REPOSITORY}/releases/latest"
GITHUB_JSON = "application/vnd.github+json"
# The installer runs without questions, keeps the choices of the previous installation
# and opens Nodus again when it finishes (see [Run] in packaging/nodus.iss).
INSTALLER_ARGUMENTS = ("/SILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/RELAUNCH=1")


@dataclass(frozen=True)
class Installer:
    """The setup program attached to a release, with the checksum GitHub computed for it."""

    url: str
    size: int
    sha256: str


@dataclass(frozen=True)
class Release:
    """A published version: its number ("0.2.0"), the page to download it from, its
    release notes in Markdown (what it brings) and, when attached, its installer."""

    version: str
    url: str
    notes: str = ""
    installer: Installer | None = None


def parse_version(text: str) -> tuple[int, ...]:
    """ "v0.2.0" or "0.2.0" as (0, 2, 0), so versions compare as numbers ("0.10" > "0.9").

    Raises ValueError if ``text`` is not dot-separated numbers.
    """
    return tuple(int(part) for part in text.strip().removeprefix("v").split("."))


def installer_name(version: str) -> str:
    return f"Nodus-Setup-{version}.exe"


def _installer(version: str, assets: list[dict]) -> Installer | None:
    """The release's installer, if attached with a SHA-256 to check the download against."""
    for asset in assets:
        digest = asset.get("digest") or ""
        if asset.get("name") == installer_name(version) and digest.startswith("sha256:"):
            return Installer(asset["browser_download_url"], int(asset["size"]), digest[7:])
    return None


def _launch_detached(command: list[str]) -> None:
    """Starts ``command`` as its own process, so it outlives Nodus closing."""
    flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    subprocess.Popen(command, creationflags=flags, close_fds=True)


class UpdateService:
    """Asks GitHub for the latest release, and downloads and starts its installer.

    The check sends only the version number, nothing about the user or their data. The
    installer is downloaded only when the user asks for it.
    """

    def __init__(
        self,
        current_version: str,
        fetch: Fetch | None = None,
        stream: Stream | None = None,
        downloads_dir: Path | None = None,
        launch: Callable[[list[str]], None] | None = None,
    ) -> None:
        self.current_version = current_version
        user_agent = f"Nodus/{current_version}"
        self._fetch = fetch or downloader(user_agent, GITHUB_JSON)
        self._stream = stream or streamer(user_agent)
        self.downloads_dir = downloads_dir or Path(tempfile.gettempdir()) / "Nodus" / "updates"
        self._launch = launch

    @classmethod
    def for_this_program(cls, current_version: str) -> UpdateService:
        """Installs updates only when running as the installed program on Windows; run
        from the source code there is nothing to replace, so the release page opens."""
        installed = getattr(sys, "frozen", False) and sys.platform == "win32"
        return cls(current_version, launch=_launch_detached if installed else None)

    def check(self) -> Release | None:
        """The latest release if it is newer than the running version, otherwise None.

        Any failure (no internet, GitHub down, an unexpected answer) also gives None:
        the check is a courtesy and must never get in the way of using the app.
        """
        try:
            data = json.loads(self._fetch(LATEST_RELEASE_API))
            version = data["tag_name"].removeprefix("v")
            # The notes open with the tag's subject line, which repeats the version.
            notes = (data.get("body") or "").strip().removeprefix(f"Nodus {version}").strip()
            installer = _installer(version, data.get("assets") or [])
            latest = Release(version, data["html_url"], notes, installer)
            is_newer = parse_version(latest.version) > parse_version(self.current_version)
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            return None
        return latest if is_newer else None

    def can_install(self, release: Release) -> bool:
        """Whether ``release`` can be installed from Nodus, instead of from its page."""
        return self._launch is not None and release.installer is not None

    def download(
        self,
        release: Release,
        on_progress: Callable[[int], None] = lambda _received: None,
        cancelled: Callable[[], bool] = lambda: False,
    ) -> Path | None:
        """Downloads the installer of ``release`` and checks it arrived intact.

        ``on_progress`` receives the bytes received so far. Returns the installer's path,
        or None if ``cancelled`` turned true midway. Raises ``UpdateError`` if the
        download fails or does not match the checksum.
        """
        installer = release.installer
        if installer is None:
            raise UpdateError("Esta versión no trae un instalador para descargar.")
        destination = self.downloads_dir / installer_name(release.version)
        partial = destination.with_suffix(".part")
        digest = hashlib.sha256()
        received = 0
        try:
            self.downloads_dir.mkdir(parents=True, exist_ok=True)
            with partial.open("wb") as file:
                for chunk in self._stream(installer.url):
                    if cancelled():
                        break
                    file.write(chunk)
                    digest.update(chunk)
                    received += len(chunk)
                    on_progress(received)
        except OSError as error:
            partial.unlink(missing_ok=True)
            raise UpdateError(f"No se pudo descargar la actualización: {error}") from error
        if cancelled():
            partial.unlink(missing_ok=True)
            return None
        if digest.hexdigest() != installer.sha256:
            partial.unlink(missing_ok=True)
            raise UpdateError("La descarga llegó dañada. Vuelve a intentarlo.")
        partial.replace(destination)
        return destination

    def install(self, installer: Path) -> None:
        """Starts ``installer``; Nodus must close right after so its files can be replaced.

        Raises ``UpdateError`` if the installer cannot be started.
        """
        if self._launch is None:
            raise UpdateError("Las actualizaciones se instalan desde la versión instalada.")
        try:
            self._launch([str(installer), *INSTALLER_ARGUMENTS])
        except OSError as error:
            raise UpdateError(f"No se pudo abrir el instalador: {error}") from error

    def clean(self) -> None:
        """Deletes downloaded installers; called on startup, once they have done their job."""
        shutil.rmtree(self.downloads_dir, ignore_errors=True)
