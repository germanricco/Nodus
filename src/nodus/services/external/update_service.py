"""Checks GitHub for a newer published version of Nodus, and installs it on request."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import sys
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from nodus import APP_NAME, USER_AGENT, is_installed, program_path
from nodus.config.logs import describe
from nodus.i18n import _, current_language
from nodus.links import LATEST_RELEASE_API
from nodus.models.version import parse_version
from nodus.services.app.changelog import notes_in
from nodus.services.errors import UpdateError
from nodus.services.external.http import Fetch, Stream, downloader, streamer
from nodus.services.external.process import launch_detached

logger = logging.getLogger(__name__)

GITHUB_JSON = "application/vnd.github+json"
# The installer runs without questions, keeps the choices of the previous installation
# and opens Nodus again when it finishes (see [Run] in packaging/nodus.iss).
INSTALLER_ARGUMENTS = ("/SILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/RELAUNCH=1")


@dataclass(frozen=True)
class Installer:
    """What installs a release on this system, attached to it with the checksum GitHub
    computed: the setup program on Windows, the AppImage itself on Linux."""

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


def installer_name(version: str) -> str:
    """The name scripts/build.py gives the file of ``version`` on this system."""
    if sys.platform == "win32":
        return f"Nodus-Setup-{version}.exe"
    return f"Nodus-{version}-x86_64.AppImage"


def _installer(version: str, assets: list[dict[str, Any]]) -> Installer | None:
    """The release's installer, if attached with a SHA-256 to check the download against."""
    for asset in assets:
        digest = asset.get("digest") or ""
        if asset.get("name") == installer_name(version) and digest.startswith("sha256:"):
            return Installer(asset["browser_download_url"], int(asset["size"]), digest[7:])
    return None


class UpdateService:
    """Asks GitHub for the latest release, downloads it and installs it: on Windows by
    starting its installer, on Linux by putting the new AppImage in place of ``appimage``.

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
        appimage: Path | None = None,
    ) -> None:
        self.current_version = current_version
        self._appimage = appimage
        self._fetch = fetch or downloader(USER_AGENT, GITHUB_JSON)
        self._stream = stream or streamer(USER_AGENT)
        self.downloads_dir = downloads_dir or Path(tempfile.gettempdir()) / APP_NAME / "updates"
        self._launch = launch

    @classmethod
    def for_this_program(cls, current_version: str) -> UpdateService:
        """Installs updates only when running as the installed program on Windows or the
        AppImage on Linux; run from the source code there is nothing to replace, so the
        release page opens."""
        if not is_installed():
            return cls(current_version)
        if sys.platform == "win32":
            return cls(current_version, launch=launch_detached)
        return cls(current_version, appimage=Path(program_path()))

    @property
    def reopens_by_itself(self) -> bool:
        """Whether the installer opens Nodus again once it closes, as the Windows one
        does; the AppImage, replaced in place, is reopened by Nodus (a restart)."""
        return self._appimage is None

    def check(self) -> Release | None:
        """The latest release if it is newer than the running version, otherwise None.

        Any failure (no internet, GitHub down, an unexpected answer) also gives None:
        the check is a courtesy and must never get in the way of using the app.
        """
        try:
            data = json.loads(self._fetch(LATEST_RELEASE_API))
            version = data["tag_name"].removeprefix("v")
            # The notes open with the tag's subject line, which repeats the version.
            body = (data.get("body") or "").strip().removeprefix(f"Nodus {version}").strip()
            notes = notes_in(current_language(), body)
            installer = _installer(version, data.get("assets") or [])
            latest = Release(version, data["html_url"], notes, installer)
            is_newer = parse_version(latest.version) > parse_version(self.current_version)
        except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
            logger.warning("Update check failed: %s", describe(error))
            return None
        logger.info("Update check: latest is %s", latest.version)
        return latest if is_newer else None

    def can_install(self, release: Release) -> bool:
        """Whether ``release`` can be installed from Nodus, instead of from its page."""
        can_replace = self._launch is not None or self._appimage is not None
        return can_replace and release.installer is not None

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
            raise UpdateError(_("Esta versión no trae un instalador para descargar."))
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
            logger.warning("Update download failed", exc_info=error)
            partial.unlink(missing_ok=True)
            raise UpdateError(
                _(
                    "No se pudo descargar la actualización. Revisa la conexión a internet "
                    "y vuelve a intentarlo."
                ),
                str(error),
            ) from error
        if cancelled():
            partial.unlink(missing_ok=True)
            return None
        if digest.hexdigest() != installer.sha256:
            logger.warning("Update download arrived damaged")
            partial.unlink(missing_ok=True)
            raise UpdateError(_("La descarga llegó dañada. Vuelve a intentarlo."))
        partial.replace(destination)
        return destination

    def install(self, installer: Path) -> None:
        """Starts ``installer``, or puts the new AppImage in place: Nodus must close right
        after so its files can be replaced, or so the new one opens.

        Raises ``UpdateError`` if the installer cannot be started.
        """
        if self._appimage is not None:
            self._replace_appimage(installer, self._appimage)
            return
        if self._launch is None:
            raise UpdateError(_("Las actualizaciones se instalan desde la versión instalada."))
        try:
            self._launch([str(installer), *INSTALLER_ARGUMENTS])
        except OSError as error:
            logger.warning("The installer could not start", exc_info=error)
            raise UpdateError(
                _("No se pudo abrir el instalador. Vuelve a intentarlo."),
                str(error),
            ) from error

    @staticmethod
    def _replace_appimage(new: Path, appimage: Path) -> None:
        """Copies ``new`` beside ``appimage`` and swaps them in one step, so an update cut
        short never leaves half an AppImage. The name stays: the menu entry and the
        sign-in entry point at it. The running Nodus keeps the old one open until it
        closes."""
        staged = appimage.with_name(f".{appimage.name}.new")
        try:
            shutil.copyfile(new, staged)
            staged.chmod(0o755)
            os.replace(staged, appimage)
        except OSError as error:
            logger.warning("The AppImage could not be replaced", exc_info=error)
            staged.unlink(missing_ok=True)
            raise UpdateError(
                _(
                    "No se pudo reemplazar Nodus en su carpeta. Revisa que puedas escribir"
                    " en ella, o descarga la versión nueva desde GitHub."
                ),
                str(error),
            ) from error

    def clean(self) -> None:
        """Deletes downloaded installers; called on startup, once they have done their job."""
        shutil.rmtree(self.downloads_dir, ignore_errors=True)
