"""What each kind of notice offers in the bell, in one table: the text of its click and
what the click does, and whether and how it can be put away. A new kind of notice is a
new row here; ``test_every_kind_of_notice_has_its_row`` fails until it has one."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING

from nodus.i18n import N_
from nodus.models.period import Month
from nodus.services.app.notification_service import Notice, NoticeKind
from nodus.ui.dialogs.external_backup import save_copy_outside
from nodus.ui.navigation import DetailId, PageId

if TYPE_CHECKING:
    from nodus.ui.shell.main_window import MainWindow

NoticeAction = Callable[["MainWindow", Notice], None]


@dataclass(frozen=True)
class NoticeBehavior:
    """``action_text`` says where a click leads (tooltip, and bold in its menu) and
    ``open`` goes there; ``dismiss_text`` and ``dismiss`` put the notice away, for the
    kinds that can be. The texts are ``N_()``, translated where they are shown."""

    action_text: str
    open: NoticeAction
    dismiss_text: str | None = None
    dismiss: NoticeAction | None = None


def _update(window: MainWindow, _notice: Notice) -> None:
    if window.release is not None:
        window.start_update(window.release)


def _forget_release(window: MainWindow, _notice: Notice) -> None:
    window.services.notifications.dismiss_release()


def _settings(window: MainWindow, _notice: Notice) -> None:
    window.show_page(PageId.SETTINGS)


def _save_copy(window: MainWindow, _notice: Notice) -> None:
    save_copy_outside(window, window.services, window.event_bus)


def _put_off_copy(window: MainWindow, _notice: Notice) -> None:
    window.services.backups.put_off_reminder(date.today())


def _charges(window: MainWindow, _notice: Notice) -> None:
    # Opening it is «Ya lo vi» for its charges, which their rows show.
    window.event_bus.recurring_changed.emit()
    window.show_page(PageId.RECURRING)


def _budgets(window: MainWindow, _notice: Notice) -> None:
    window.show_budgets(Month.of(date.today()))


def _goal(window: MainWindow, notice: Notice) -> None:
    if notice.item_id is not None:
        window.services.goals.mark_seen(notice.item_id)
        window.show_detail(DetailId.GOAL, notice.item_id)


def _forget_goal(window: MainWindow, notice: Notice) -> None:
    if notice.item_id is not None:
        window.services.goals.mark_seen(notice.item_id)


NOTICES: dict[NoticeKind, NoticeBehavior] = {
    NoticeKind.UPDATE: NoticeBehavior(
        N_("Actualizar"), _update, N_("Descartar esta versión"), _forget_release
    ),
    NoticeKind.STALE_RATE: NoticeBehavior(N_("Ir a Ajustes"), _settings),
    NoticeKind.BACKUP_FAILED: NoticeBehavior(N_("Ir a Ajustes"), _settings),
    NoticeKind.BACKUP_REMINDER: NoticeBehavior(
        N_("Guardar copia…"),
        _save_copy,
        N_("Ahora no: avisar a fin del mes que viene"),
        _put_off_copy,
    ),
    NoticeKind.CHARGES_DUE: NoticeBehavior(N_("Ver cargos"), _charges),
    NoticeKind.BUDGET_OVER: NoticeBehavior(N_("Ver presupuestos"), _budgets),
    NoticeKind.GOAL_REACHED: NoticeBehavior(
        N_("Ver meta"), _goal, N_("Quitar el aviso"), _forget_goal
    ),
}
