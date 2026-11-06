import sqlite3

import pytest

from nodus.database.database import Database, DatabaseError, Migration, load_packaged_migrations

CREATE_NOTES = Migration(1, "notes", "CREATE TABLE notes (id INTEGER PRIMARY KEY, text TEXT);")
ADD_TAGS = Migration(2, "tags", "CREATE TABLE tags (id INTEGER PRIMARY KEY);")
BROKEN = Migration(2, "broken", "CREATE TABLE half_done (id INTEGER); THIS IS NOT SQL;")


def table_names(database: Database) -> set[str]:
    rows = database.connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    return {row["name"] for row in rows}


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "nodus.db"


class TestPackagedSchema:
    def test_new_database_gets_full_schema(self, db_path):
        database = Database.open(db_path)

        latest = max(m.version for m in load_packaged_migrations())
        assert database.schema_version == latest
        assert {"accounts", "categories", "transactions", "exchange_rates", "settings"} <= (
            table_names(database)
        )
        database.close()

    def test_foreign_keys_are_enforced(self, db_path):
        database = Database.open(db_path)

        with pytest.raises(sqlite3.IntegrityError):
            database.connection.execute(
                "INSERT INTO transactions"
                " (account_id, type, amount_cents, occurred_on, category_id)"
                " VALUES (999, 'expense', 100, '2026-11-05', 999)"
            )
        database.close()

    def test_reopening_is_idempotent(self, db_path):
        Database.open(db_path).close()
        database = Database.open(db_path)

        assert database.schema_version == max(m.version for m in load_packaged_migrations())
        assert not database.backup_path.exists()
        database.close()


class TestMigrations:
    def test_applies_pending_migrations_in_order(self, db_path):
        database = Database.open(db_path, [ADD_TAGS, CREATE_NOTES])

        assert database.schema_version == 2
        assert {"notes", "tags"} <= table_names(database)
        database.close()

    def test_backs_up_existing_database_before_migrating(self, db_path):
        database = Database.open(db_path, [CREATE_NOTES])
        database.connection.execute("INSERT INTO notes (text) VALUES ('keep me')")
        database.connection.commit()
        database.close()

        database = Database.open(db_path, [CREATE_NOTES, ADD_TAGS])

        backup = sqlite3.connect(database.backup_path)
        assert backup.execute("PRAGMA user_version").fetchone()[0] == 1
        assert backup.execute("SELECT text FROM notes").fetchone()[0] == "keep me"
        backup.close()
        database.close()

    def test_failed_migration_is_rolled_back(self, db_path):
        Database.open(db_path, [CREATE_NOTES]).close()

        with pytest.raises(DatabaseError):
            Database.open(db_path, [CREATE_NOTES, BROKEN])

        database = Database.open(db_path, [CREATE_NOTES])
        assert database.schema_version == 1
        assert "half_done" not in table_names(database)
        database.close()


def test_corrupt_file_raises_database_error(db_path):
    db_path.write_bytes(b"this is not a sqlite database" * 100)

    with pytest.raises(DatabaseError):
        Database.open(db_path)


@pytest.mark.parametrize("released", [1, 2, 3, 4, 5, 6])
def test_migrations_keep_existing_data(db_path, released):
    """A database from an earlier release (schema 1 is v0.4, 2 is v0.5, 3 is v0.6, 4 is
    v0.7 and v0.8, 5 is v0.9, 6 is v0.9.1) with data gets the new tables and keeps its rows."""
    migrations = [m for m in load_packaged_migrations() if m.version <= released]
    database = Database.open(db_path, migrations)
    with database.transaction():
        database.connection.execute(
            "INSERT INTO accounts (name, type, currency, initial_balance_cents)"
            " VALUES ('Banco', 'bank', 'ARS', 500)"
        )
    database.close()

    database = Database.open(db_path)

    assert database.schema_version == 7
    assert {
        "recurring_charges",
        "budget_limits",
        "payees",
        "tags",
        "transaction_tags",
        "value_adjustments",
    } <= table_names(database)
    row = database.connection.execute("SELECT name, initial_balance_cents FROM accounts").fetchone()
    assert tuple(row) == ("Banco", 500)
    database.close()


def test_payees_migration_keeps_transactions_without_payee(db_path):
    migrations = [m for m in load_packaged_migrations() if m.version <= 3]
    database = Database.open(db_path, migrations)
    with database.transaction():
        database.connection.execute(
            "INSERT INTO accounts (name, type, currency, initial_balance_cents)"
            " VALUES ('Banco', 'bank', 'ARS', 0)"
        )
        database.connection.execute(
            "INSERT INTO transactions (account_id, type, amount_cents, occurred_on, category_id)"
            " VALUES (1, 'expense', 700, '2026-11-01', 1)"
        )
    database.close()

    database = Database.open(db_path)

    row = database.connection.execute("SELECT amount_cents, payee_id FROM transactions").fetchone()
    assert tuple(row) == (700, None)
    database.close()


def test_refunds_and_tags_migration_keeps_transactions(db_path):
    migrations = [m for m in load_packaged_migrations() if m.version <= 4]
    database = Database.open(db_path, migrations)
    with database.transaction():
        database.connection.execute(
            "INSERT INTO accounts (name, type, currency, initial_balance_cents)"
            " VALUES ('Banco', 'bank', 'ARS', 0)"
        )
        database.connection.execute(
            "INSERT INTO transactions (account_id, type, amount_cents, occurred_on, category_id)"
            " VALUES (1, 'expense', 700, '2026-11-01', 1)"
        )
    database.close()

    database = Database.open(db_path)

    row = database.connection.execute(
        "SELECT amount_cents, refund_of_id FROM transactions"
    ).fetchone()
    assert tuple(row) == (700, None)
    database.close()


def test_charge_currency_migration_takes_the_account_currency(db_path):
    migrations = [m for m in load_packaged_migrations() if m.version <= 5]
    database = Database.open(db_path, migrations)
    with database.transaction():
        for name, currency in (("Banco", "ARS"), ("Ahorro", "USD")):
            database.connection.execute(
                "INSERT INTO accounts (name, type, currency, initial_balance_cents)"
                " VALUES (?, 'bank', ?, 0)",
                (name, currency),
            )
        for account_id in (1, 2):
            database.connection.execute(
                "INSERT INTO recurring_charges (name, amount_cents, account_id, category_id,"
                " frequency, anchor_day, next_due_on) VALUES ('Cargo', 900, ?, 1, 'monthly', 5,"
                " '2026-12-05')",
                (account_id,),
            )
    database.close()

    database = Database.open(db_path)

    rows = database.connection.execute(
        "SELECT amount_cents, currency, last_paid_rate FROM recurring_charges ORDER BY id"
    ).fetchall()
    assert [tuple(row) for row in rows] == [(900, "ARS", None), (900, "USD", None)]
    database.close()
