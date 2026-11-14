"""Dialog to create or edit a savings goal: its target, its date and the accounts that
fill it, with what they add today and what reaching it takes, updated while typing."""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import Signal
from PySide6.QtGui import QIntValidator
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from nodus.models.account import Account
from nodus.models.goal import Goal, GoalShare, GoalState
from nodus.models.money import Money
from nodus.models.period import Month
from nodus.services.container import Services
from nodus.services.goal_service import GoalDraft
from nodus.ui.dialogs.form_dialog import SAVE_CHANGES, TYPE_AMOUNT, TYPE_NAME, FormDialog
from nodus.ui.event_bus import EventBus
from nodus.ui.labels import CURRENCY_LABELS
from nodus.ui.theme.design import Space
from nodus.ui.widgets.amount_input import AmountInput
from nodus.ui.widgets.combo_box import ComboBox
from nodus.ui.widgets.date_input import DateInput
from nodus.ui.widgets.empty_state import EmptyState
from nodus.ui.widgets.goal_bar import NO_RATE_TEXT, month_phrase
from nodus.ui.widgets.money_label import amount_text

PERCENT_WIDTH = 48  # geometry: room for «100»
DEFAULT_MONTHS = 12  # a new goal's date, when one is set: a year from now


class ShareRow(QWidget):
    """An account a goal may count: whether it does, which part of it and what that is."""

    changed = Signal()

    def __init__(self, account: Account, free: int) -> None:
        super().__init__()
        self.account = account
        self.free = free
        # Once the user types a part, ticking the account again keeps it.
        self.typed = False
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(Space.S)
        self.check = QCheckBox(account.name)
        self.percent_input = QLineEdit(str(max(free, 1)))
        self.percent_input.setValidator(QIntValidator(1, 100, self.percent_input))
        self.percent_input.setFixedWidth(PERCENT_WIDTH)
        self.percent_input.setToolTip("La parte del saldo que cuenta para la meta")
        self.percent_sign = QLabel("%")
        self.hint = QLabel()
        self.hint.setObjectName("FieldHint")
        layout.addWidget(self.check)
        layout.addStretch()
        layout.addWidget(self.hint)
        layout.addWidget(self.percent_input)
        layout.addWidget(self.percent_sign)
        for widget in (self.percent_input, self.percent_sign):  # rows keep their height
            policy = widget.sizePolicy()
            policy.setRetainSizeWhenHidden(True)
            widget.setSizePolicy(policy)
        if free <= 0:  # every bit of it is already in other goals
            self.check.setEnabled(False)
        self.check.toggled.connect(self._follow_check)
        self.check.toggled.connect(self.changed)
        self.percent_input.textChanged.connect(self.changed)
        self.percent_input.textEdited.connect(self._mark_typed)
        self._follow_check()

    @property
    def percent(self) -> int:
        text = self.percent_input.text()
        return int(text) if text.isdigit() else 0

    def set_share(self, percent: int) -> None:
        """The part a saved goal already has, which counts as the user's choice."""
        self.typed = True
        self.check.setEnabled(True)
        self.check.setChecked(True)
        self.percent_input.setText(str(percent))

    def offer(self, percent: int) -> None:
        """Puts a suggested part, unless the user already typed one."""
        if not self.typed:
            self.percent_input.setText(str(percent))

    def show_counted(self, counted: Money | None, hidden: bool) -> None:
        """What the share adds today when it counts; how much is free when it does not."""
        if self.check.isChecked():
            shown = "" if counted is None else f"aporta {amount_text(counted, hidden)} hoy"
            self.hint.setText(shown)
        elif self.free <= 0:
            self.hint.setText("usada al 100 % en otras metas")
        elif self.free < 100:
            self.hint.setText(f"quedan {self.free} % libres")
        else:
            self.hint.setText("")

    def _mark_typed(self) -> None:
        self.typed = True

    def _follow_check(self) -> None:
        """The percent shows only for an account that counts."""
        self.percent_input.setVisible(self.check.isChecked())
        self.percent_sign.setVisible(self.check.isChecked())


class AccountShares(QWidget):
    """The accounts a goal may count, one row each; ``changed`` on any tick or percent."""

    changed = Signal()

    def __init__(self, rows: list[ShareRow]) -> None:
        super().__init__()
        self.rows = rows
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(Space.XS)
        for row in rows:
            layout.addWidget(row)
            row.changed.connect(self.changed)
        if not rows:
            layout.addWidget(
                EmptyState("Todavía no hay cuentas que junten dinero para una meta.", compact=True)
            )

    def shares(self) -> tuple[GoalShare, ...]:
        return tuple(
            GoalShare(row.account.id, row.percent) for row in self.rows if row.check.isChecked()
        )

    def row_for(self, account_id: int) -> ShareRow | None:
        return next((row for row in self.rows if row.account.id == account_id), None)


class GoalDialog(FormDialog):
    """Creates a goal, or edits ``goal`` when given. ``account`` comes ticked, for a goal
    started from an account's menu.

    The foot says what reaching the goal takes with what was typed, before saving it, so
    an unrealistic date shows while it can still be changed.
    """

    def __init__(
        self,
        services: Services,
        event_bus: EventBus,
        goal: Goal | None = None,
        account: Account | None = None,
        today: date | None = None,
        parent: QWidget | None = None,
    ) -> None:
        title = "Editar meta" if goal else "Nueva meta"
        super().__init__(title, parent, SAVE_CHANGES if goal else "Agregar meta")
        self._services = services
        self._event_bus = event_bus
        self._goal = goal
        self._today = today or date.today()
        self._hidden = services.settings.amounts_hidden()

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Ej.: Vacaciones, Fondo de emergencia")
        currency = goal.currency if goal else services.settings.net_worth_currency()
        self.target_input = AmountInput(currency)
        self.currency_input = ComboBox()
        for option, label in CURRENCY_LABELS.items():
            self.currency_input.addItem(label, option)
        self.currency_input.setCurrentIndex(self.currency_input.findData(currency))
        self.currency_input.currentIndexChanged.connect(
            lambda: self.target_input.set_currency(self.currency_input.currentData())
        )
        self.dated_input = QCheckBox("Con fecha")
        self.date_input = DateInput()
        self.date_input.set_day(Month.of(self._today).shifted(DEFAULT_MONTHS).end)
        date_row = QWidget()
        date_layout = QHBoxLayout(date_row)
        date_layout.setContentsMargins(0, 0, 0, 0)
        date_layout.addWidget(self.dated_input)
        date_layout.addWidget(self.date_input, stretch=1)
        self.dated_input.toggled.connect(self.date_input.setEnabled)
        self.shares_input = AccountShares(self._share_rows())
        self.summary_label = QLabel()
        self.summary_label.setObjectName("FieldHint")
        self.summary_label.setWordWrap(True)

        self.form.addRow("Nombre", self.name_input)
        self.form.addRow("Objetivo", self.target_input)
        self.form.addRow("Moneda", self.currency_input)
        self.form.addRow("Fecha", date_row)
        self.form.addRow("Cuentas", self.shares_input)
        self.form.addRow("", self.summary_label)
        self.bind_field(self.name_input, "name")
        self.bind_field(self.target_input, "target")
        self.bind_field(self.date_input, "target_date")
        self.bind_field(self.shares_input, "shares")

        if goal:
            self._load(goal)
        else:
            self.date_input.setEnabled(False)
            row = self.shares_input.row_for(account.id) if account else None
            if row is not None and row.check.isEnabled():
                row.check.setChecked(True)
        for row in self.shares_input.rows:
            row.check.toggled.connect(lambda ticked, r=row: ticked and self._suggest(r))
        self.target_input.line_edit.textChanged.connect(self._suggest_again)
        self.currency_input.currentIndexChanged.connect(self._suggest_again)
        for signal in (
            self.target_input.line_edit.textChanged,
            self.currency_input.currentIndexChanged,
            self.dated_input.toggled,
            self.date_input.dateChanged,
            self.shares_input.changed,
        ):
            signal.connect(self._update_preview)
        self._update_preview()

    def _share_rows(self) -> list[ShareRow]:
        """Every account that can fill a goal, plus those already in this one (an archived
        account still counts)."""
        goals = self._services.goals
        goal_id = self._goal.id if self._goal else None
        accounts = goals.eligible_accounts()
        if self._goal:
            known = {a.id for a in accounts}
            accounts += [
                self._services.accounts.get(share.account_id)
                for share in self._goal.shares
                if share.account_id not in known
            ]
        return [ShareRow(a, goals.free_percent(a.id, goal_id)) for a in accounts]

    def _load(self, goal: Goal) -> None:
        self.name_input.setText(goal.name)
        self.target_input.set_money(goal.target)
        self.dated_input.setChecked(goal.target_date is not None)
        self.date_input.setEnabled(goal.target_date is not None)
        if goal.target_date:
            self.date_input.set_day(goal.target_date)
        for share in goal.shares:
            row = self.shares_input.row_for(share.account_id)
            if row is not None:
                row.set_share(share.percent)

    def _suggest(self, row: ShareRow, counted: list[ShareRow] | None = None) -> None:
        """A ticked account comes with the part that covers what the goal still misses
        with ``counted`` (every other ticked account, by default)."""
        if counted is None:
            counted = [r for r in self.shares_input.rows if r.check.isChecked() and r is not row]
        shares = tuple(GoalShare(r.account.id, r.percent) for r in counted if 1 <= r.percent <= 100)
        preview = Goal(None, "", self._target(), self._target_date(), shares)
        row.offer(
            self._services.goals.suggested_percent(preview, row.account.id, row.free, self._today)
        )

    def _suggest_again(self) -> None:
        """A new target re-offers the parts the user did not type: those typed count
        first, then the rest fill what is missing in their order."""
        ticked = [row for row in self.shares_input.rows if row.check.isChecked()]
        counted = [row for row in ticked if row.typed]
        for row in ticked:
            if not row.typed:
                self._suggest(row, counted)
                counted.append(row)

    def _target(self) -> Money:
        """The target as typed so far; zero while it is not a valid amount."""
        try:
            return self.target_input.money()
        except ValueError:
            return Money.zero(self.currency_input.currentData())

    def _target_date(self) -> date | None:
        return self.date_input.day() if self.dated_input.isChecked() else None

    def _update_preview(self) -> None:
        """Each ticked account's part today, and what the goal takes, as it stands."""
        target = self._target()
        shares = tuple(share for share in self.shares_input.shares() if 1 <= share.percent <= 100)
        counted: dict[int, Money | None] = {}
        if shares:
            preview = Goal(None, "", target, self._target_date(), shares)
            for contribution in self._services.goals.contributions(preview, self._today):
                counted[contribution.account.id] = contribution.counted
            if target.cents > 0:
                self.summary_label.setText(self._summary(preview))
        for row in self.shares_input.rows:
            row.show_counted(counted.get(row.account.id), self._hidden)
        self.summary_label.setVisible(bool(shares) and target.cents > 0)

    def _summary(self, preview: Goal) -> str:
        progress = self._services.goals.progress(preview, self._today)
        if progress.state is GoalState.NO_RATE:
            return NO_RATE_TEXT
        if progress.state is GoalState.REACHED:
            return "Ya está cubierta: tus cuentas ya suman el objetivo."
        target = amount_text(preview.target, self._hidden)
        if preview.target_date is None or progress.needed_per_month is None:
            assert progress.remaining is not None
            return f"Faltan {amount_text(progress.remaining, self._hidden)} para {target}."
        month = month_phrase(Month.of(preview.target_date))
        needed = amount_text(progress.needed_per_month, self._hidden)
        return f"Para llegar a {target} en {month} hacen falta unos {needed} por mes."

    def missing(self) -> dict[QWidget, str]:
        return self.required((self.name_input, TYPE_NAME), (self.target_input, TYPE_AMOUNT))

    def save(self) -> None:
        draft = GoalDraft(
            self.name_input.text(),
            self.target_input.money(),
            self._target_date(),
            self.shares_input.shares(),
        )
        if self._goal:
            self._services.goals.update(self._goal.id, draft, self._today)
        else:
            self._services.goals.create(draft, self._today)
        self._event_bus.goals_changed.emit()
