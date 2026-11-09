import csv
from datetime import date

from factories import ars, expense_draft, income_draft, usd

from nodus.models.transaction_filter import TransactionFilter
from nodus.services.export_service import HEADER
from nodus.services.transaction_service import TransferDraft


def all_transactions(services):
    return services.transactions.list_transactions(TransactionFilter())


def read_csv(path) -> list[list[str]]:
    with path.open(encoding="utf-8-sig", newline="") as file:
        return list(csv.reader(file, delimiter=";"))


def test_rows_for_expense_and_income_oldest_first(services, pesos):
    services.transactions.create(
        expense_draft(services, pesos.id, ars("1234.5"), date(2026, 11, 3), note="Súper")
    )
    services.transactions.create(income_draft(services, pesos.id, ars("500000"), date(2026, 11, 1)))

    rows = services.export.rows(all_transactions(services))

    assert rows == [
        ["01/11/2026", "Ingreso", "Banco", "Sueldo", "", "", "500000,00", "ARS", ""],
        [
            "03/11/2026",
            "Gasto",
            "Banco",
            "Supermercado y comida",
            "",
            "Súper",
            "-1234,50",
            "ARS",
            "",
        ],
    ]


def test_transfer_is_one_row_per_leg(services, pesos, dollars):
    services.transactions.create_transfer(
        TransferDraft(pesos.id, dollars.id, ars("120000"), date(2026, 11, 2), amount_in=usd("100"))
    )

    rows = services.export.rows(all_transactions(services))

    assert sorted((row[1], row[2], row[6], row[7]) for row in rows) == [
        ("Transferencia", "Ahorro", "100,00", "USD"),
        ("Transferencia", "Banco", "-120000,00", "ARS"),
    ]
    assert all(row[3] == row[4] == "" for row in rows)


def test_csv_has_bom_semicolons_and_quotes(services, pesos, tmp_path):
    services.transactions.create(
        expense_draft(services, pesos.id, ars("10"), date(2026, 11, 3), note='Cena; "amigos"')
    )
    path = tmp_path / "export.csv"

    services.export.write_csv(all_transactions(services), path)

    raw = path.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")
    assert raw.decode("utf-8-sig").splitlines()[0] == ";".join(HEADER)
    assert read_csv(path)[1][5] == 'Cena; "amigos"'


def test_payee_column(services, pesos):
    services.transactions.create(
        expense_draft(services, pesos.id, ars("10"), date(2026, 11, 3), payee_name="Coto")
    )

    (row,) = services.export.rows(all_transactions(services))

    assert HEADER[4] == "Beneficiario"
    assert row[4] == "Coto"
