from datetime import date

import pytest
from factories import ars

from nodus.models.payee import Payee
from nodus.models.transaction import Transaction, TransactionType


def test_payee_exposes_its_normalized_name():
    assert Payee(None, "Café Martínez").normalized_name == "cafe martinez"


def test_transfer_leg_cannot_have_payee():
    with pytest.raises(ValueError, match="payee"):
        Transaction(
            None, 1, TransactionType.EXPENSE, ars("10"), date(2026, 11, 1), None,
            transfer_id="abc", payee_id=3,
        )  # fmt: skip
