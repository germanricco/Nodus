"""Shared test setup."""

import os
import sys

import pytest

# Render Qt widgets without a visible window, so tests run headless and in CI.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
if sys.platform == "win32":
    os.environ.setdefault("QT_QPA_FONTDIR", os.path.join(os.environ["WINDIR"], "Fonts"))

from factories import ars, eur, usd  # noqa: E402

from nodus.database.database import Database  # noqa: E402
from nodus.models.account import Account, AccountType  # noqa: E402
from nodus.models.currency import Currency  # noqa: E402
from nodus.services.container import Services  # noqa: E402
from nodus.ui.theme.design import set_reduced_motion  # noqa: E402


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
    db = Database.open(tmp_path / "nodus.db")
    yield db
    db.close()


@pytest.fixture
def services(database) -> Services:
    return Services.create(database)


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
