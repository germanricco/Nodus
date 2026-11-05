"""Renders every page of Nodus, in light and dark themes, to PNG files.

Used to review the interface without opening it and to produce README images. It runs
over a temporary database (optionally filled with demo data), never over real user data.

    .venv/Scripts/python scripts/screenshot.py --demo --out screenshots
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
from datetime import date
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
# The offscreen platform does not see the system fonts on Windows unless told where they are.
if sys.platform == "win32":
    os.environ.setdefault("QT_QPA_FONTDIR", str(Path(os.environ["WINDIR"]) / "Fonts"))

from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402

from nodus.database.database import Database  # noqa: E402
from nodus.services.container import Services  # noqa: E402
from nodus.ui.dialogs.account_dialog import AccountDialog  # noqa: E402
from nodus.ui.dialogs.category_dialog import CategoryDialog  # noqa: E402
from nodus.ui.event_bus import EventBus  # noqa: E402
from nodus.ui.main_window import MainWindow  # noqa: E402
from nodus.ui.navigation import PageId  # noqa: E402
from nodus.ui.theme.theme import ThemeMode  # noqa: E402
from nodus.ui.theme.theme_manager import ThemeManager  # noqa: E402

sys.path.insert(0, str(Path(__file__).parent))
from demo_data import load_demo_data  # noqa: E402

# Dialogs to capture, built over the demo data: name -> factory(services, event_bus, window).
DIALOGS = {
    "account-dialog": lambda services, event_bus, window: AccountDialog(
        services, event_bus, parent=window
    ),
    "category-dialog": lambda services, event_bus, window: CategoryDialog(
        services, event_bus, parent=window
    ),
}


def render_pages(app: QApplication, services: Services, args: argparse.Namespace) -> None:
    if args.demo:
        load_demo_data(services, args.today)
    theme_manager = ThemeManager(app, ThemeMode.LIGHT)
    event_bus = EventBus()
    window = MainWindow(services, event_bus, theme_manager)
    window.show()
    for mode in (ThemeMode.LIGHT, ThemeMode.DARK):
        theme_manager.set_mode(mode)
        for page_id in PageId:
            window.show_page(page_id)
            app.processEvents()
            save(window, args.out / f"{page_id.name.lower()}-{mode.value}.png")
        for name, build_dialog in DIALOGS.items():
            dialog = build_dialog(services, event_bus, window)
            dialog.show()
            app.processEvents()
            save(dialog, args.out / f"{name}-{mode.value}.png")
            dialog.close()
    window.close()


def save(widget: QWidget, path: Path) -> None:
    widget.grab().save(str(path))
    print(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=Path("screenshots"))
    parser.add_argument("--demo", action="store_true", help="load sample accounts and movements")
    parser.add_argument("--today", type=date.fromisoformat, default=date.today())
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    app = QApplication(sys.argv)
    with tempfile.TemporaryDirectory() as data_dir:
        database = Database.open(Path(data_dir) / "nodus.db")
        try:
            render_pages(app, Services.create(database), args)
        finally:
            database.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
