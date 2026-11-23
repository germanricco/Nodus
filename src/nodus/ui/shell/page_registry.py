"""Which class each page is, so the window builds and wires every page the same way.

Adding a page is adding its ``PageId`` and a line here; what it asks of the window (open
a detail, go to Transacciones, start the tour) is wired by the name of its signal, in
``MainWindow``.
"""

from __future__ import annotations

from nodus.ui.navigation import DetailId, PageId
from nodus.ui.pages.account_detail_page import AccountDetailPage
from nodus.ui.pages.accounts_page import AccountsPage
from nodus.ui.pages.analysis.analysis_page import AnalysisPage
from nodus.ui.pages.base.detail_page import DetailPage
from nodus.ui.pages.base.page import Page
from nodus.ui.pages.budgets_page import BudgetsPage
from nodus.ui.pages.categories_page import CategoriesPage
from nodus.ui.pages.category_detail_page import CategoryDetailPage
from nodus.ui.pages.dashboard.dashboard_page import DashboardPage
from nodus.ui.pages.goal_detail_page import GoalDetailPage
from nodus.ui.pages.goals_page import GoalsPage
from nodus.ui.pages.payee_detail_page import PayeeDetailPage
from nodus.ui.pages.payees_page import PayeesPage
from nodus.ui.pages.recurring_page import RecurringPage
from nodus.ui.pages.settings.settings_page import SettingsPage
from nodus.ui.pages.tag_detail_page import TagDetailPage
from nodus.ui.pages.tags_page import TagsPage
from nodus.ui.pages.transactions_page import TransactionsPage

PAGE_TYPES: dict[PageId, type[Page]] = {
    PageId.DASHBOARD: DashboardPage,
    PageId.ACCOUNTS: AccountsPage,
    PageId.TRANSACTIONS: TransactionsPage,
    PageId.RECURRING: RecurringPage,
    PageId.BUDGETS: BudgetsPage,
    PageId.GOALS: GoalsPage,
    PageId.ANALYSIS: AnalysisPage,
    PageId.CATEGORIES: CategoriesPage,
    PageId.PAYEES: PayeesPage,
    PageId.TAGS: TagsPage,
    PageId.SETTINGS: SettingsPage,
}

DETAIL_TYPES: dict[DetailId, type[DetailPage]] = {
    DetailId.ACCOUNT: AccountDetailPage,
    DetailId.CATEGORY: CategoryDetailPage,
    DetailId.PAYEE: PayeeDetailPage,
    DetailId.TAG: TagDetailPage,
    DetailId.GOAL: GoalDetailPage,
}

# The detail a list page opens with ``detail_requested``: its items' own page.
DETAIL_OF_LIST = {detail.list_page: detail for detail in DetailId}
