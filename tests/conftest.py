"""Shared test setup."""

import os
import sys

import pytest

# Render Qt widgets without a visible window, so tests run headless and in CI.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
if sys.platform == "win32":
    os.environ.setdefault("QT_QPA_FONTDIR", os.path.join(os.environ["WINDIR"], "Fonts"))

from factories import ars, eur, services_for, usd  # noqa: E402
from qt_cleanup import flush_deleted  # noqa: E402

from nodus.config.paths import AppPaths
from nodus.database.database import Database  # noqa: E402
from nodus.models.account import Account, AccountType  # noqa: E402
from nodus.models.currency import Currency  # noqa: E402
from nodus.services.container import Services  # noqa: E402
from nodus.ui.theme.design import set_reduced_motion  # noqa: E402


@pytest.hookimpl(wrapper=True)
def pytest_runtest_teardown(item):
    """Frees the windows a test leaves behind. pytest-qt closes them and asks for their
    deletion but only processes events, so they stayed alive: the stylesheet each test
    applies then restyled every one of them, and the suite slowed down test after test."""
    result = yield
    flush_deleted()
    return result


@pytest.fixture(autouse=True)
def no_animations():
    """Charts and figures jump to their final state, so tests can check it right away.
    Tests of the transitions themselves turn motion back on (``animations``)."""
    set_reduced_motion(True)
    yield
    set_reduced_motion(False)


@pytest.fixture
def animations():
    """Transitions play at their normal length, for the tests of the transitions."""
    set_reduced_motion(False)


@pytest.fixture
def database(tmp_path):
    """A freshly migrated database in a temporary folder."""
    db = Database.open(AppPaths(tmp_path).database_path)
    yield db
    db.close()


@pytest.fixture
def services(database) -> Services:
    return services_for(database)


@pytest.fixture
def pesos(services) -> Account:
    """A peso bank account starting with $ 100.000."""
    return services.accounts.create("Banco", AccountType.BANK, Currency.ARS, ars("100000"))


@pytest.fixture
def dollars(services) -> Account:
    """A dollar savings account starting with US$ 500."""
    return services.accounts.create("Ahorro", AccountType.SAVINGS, Currency.USD, usd("500"))


@pytest.fixture
def euros(services) -> Account:
    """A euro account starting with € 0. Tests give the euro no rate, the one case a
    movement cannot be converted: a day before the first rate takes that first one."""
    return services.accounts.create("Viaje", AccountType.CASH, Currency.EUR, eur("0"))
