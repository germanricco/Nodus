import sqlite3

import pytest

from nodus.database.database import (
    Database,
    DatabaseError,
    Migration,
    latest_schema_version,
    load_packaged_migrations,
)

CREATE_NOTES = Migration(1, "notes", "CREATE TABLE notes (id INTEGER PRIMARY KEY, text TEXT);")
ADD_TAGS = Migration(2, "tags", "CREATE TABLE tags (id INTEGER PRIMARY KEY);")
BROKEN = Migration(2, "broken", "CREATE TABLE half_done (id INTEGER); THIS IS NOT SQL;")
# Rebuilds a table others refer to, as SQLite requires to change a constraint.
PARENT = Migration(
    1,
    "parent",
    "CREATE TABLE parent (id INTEGER PRIMARY KEY);"
    " CREATE TABLE child (id INTEGER PRIMARY KEY,"
    " parent_id INTEGER NOT NULL REFERENCES parent (id) ON DELETE CASCADE);",
)
REBUILD_PARENT = Migration(
    2,
    "rebuild",
    "CREATE TABLE parent_new (id INTEGER PRIMARY KEY, extra TEXT);"
    " INSERT INTO parent_new (id) SELECT id FROM parent;"
    " DROP TABLE parent; ALTER TABLE parent_new RENAME TO parent;",
)
# Leaves a child pointing to a parent that no longer exists.
ORPHAN_CHILDREN = Migration(2, "orphans", "DELETE FROM parent;")


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

    def test_rebuilding_a_referenced_table_keeps_the_rows_that_refer_to_it(self, db_path):
        database = Database.open(db_path, [PARENT])
        with database.transaction():
            database.connection.execute("INSERT INTO parent (id) VALUES (1)")
            database.connection.execute("INSERT INTO child (parent_id) VALUES (1)")
        database.close()

        database = Database.open(db_path, [PARENT, REBUILD_PARENT])

        assert database.connection.execute("SELECT COUNT(*) FROM child").fetchone()[0] == 1
        assert database.connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        database.close()

    def test_migration_that_breaks_references_is_rolled_back(self, db_path):
        database = Database.open(db_path, [PARENT])
        with database.transaction():
            database.connection.execute("INSERT INTO parent (id) VALUES (1)")
            database.connection.execute("INSERT INTO child (parent_id) VALUES (1)")
        database.close()

        with pytest.raises(DatabaseError):
            Database.open(db_path, [PARENT, ORPHAN_CHILDREN])

        database = Database.open(db_path, [PARENT])
        assert database.schema_version == 1
        assert database.connection.execute("SELECT COUNT(*) FROM parent").fetchone()[0] == 1
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


@pytest.mark.parametrize("released", [1, 2, 3, 4, 5, 6, 7, 8, 9])
def test_migrations_keep_existing_data(db_path, released):
    """A database from an earlier release (schema 1 is v0.4, 2 is v0.5, 3 is v0.6, 4 is
    v0.7 and v0.8, 5 is v0.9, 6 is v0.9.1, 7 is v1.0, 8 is v1.1, 9 is v1.4) with data gets
    the new tables and keeps its rows."""
    migrations = [m for m in load_packaged_migrations() if m.version <= released]
    database = Database.open(db_path, migrations)
    with database.transaction():
        database.connection.execute(
            "INSERT INTO accounts (name, type, currency, initial_balance_cents)"
            " VALUES ('Banco', 'bank', 'ARS', 500)"
        )
    database.close()

    database = Database.open(db_path)

    assert database.schema_version == latest_schema_version()
    assert {
        "recurring_charges",
        "budget_limits",
        "payees",
        "tags",
        "transaction_tags",
        "value_adjustments",
        "account_groups",
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


def test_migration_8_keeps_accounts_and_everything_that_refers_to_them(db_path):
    """Rebuilding accounts, rates and charges for wallets, the order and two currencies
    loses nothing: not the movements, charges and adjustments that cascade from accounts."""
    database = Database.open(db_path, [m for m in load_packaged_migrations() if m.version <= 7])
    connection = database.connection
    with database.transaction():
        connection.executescript(
            """
            INSERT INTO accounts (id, name, type, currency, initial_balance_cents, is_archived)
            VALUES (1, 'Banco', 'bank', 'ARS', 500, 0), (2, 'Ahorro', 'savings', 'USD', 0, 1);
            INSERT INTO transactions (account_id, type, amount_cents, occurred_on, category_id)
            VALUES (1, 'expense', 100, '2026-11-01', 1);
            INSERT INTO recurring_charges (name, amount_cents, account_id, category_id,
                frequency, anchor_day, next_due_on, currency, last_paid_rate)
            VALUES ('Netflix', 900, 1, 1, 'monthly', 8, '2026-11-08', 'USD', '1500');
            INSERT INTO value_adjustments (account_id, occurred_on, amount_cents)
            VALUES (2, '2026-11-02', 300);
            INSERT INTO exchange_rates (rate_date, base_currency, quote_currency, rate)
            VALUES ('2026-11-01', 'USD', 'ARS', '1215.5');
            """
        )
    database.close()

    database = Database.open(db_path)
    connection = database.connection

    def rows(sql: str) -> list[tuple]:
        return [tuple(row) for row in connection.execute(sql)]

    accounts = rows(
        "SELECT id, name, type, currency, initial_balance_cents, is_archived, position"
        " FROM accounts ORDER BY id"
    )
    assert accounts == [
        (1, "Banco", "bank", "ARS", 500, 0, 0),
        (2, "Ahorro", "savings", "USD", 0, 1, 0),
    ]
    assert rows("SELECT account_id, amount_cents FROM transactions") == [(1, 100)]
    assert rows("SELECT name, currency, last_paid_rate FROM recurring_charges") == [
        ("Netflix", "USD", "1500")
    ]
    assert rows("SELECT account_id, amount_cents FROM value_adjustments") == [(2, 300)]
    assert rows("SELECT base_currency, rate FROM exchange_rates") == [("USD", "1215.5")]
    # The new values are accepted, and the references still hold.
    with database.transaction():
        connection.execute(
            "INSERT INTO accounts (name, type, currency) VALUES ('MP', 'wallet', 'EUR')"
        )
        connection.execute(
            "INSERT INTO exchange_rates (rate_date, base_currency, quote_currency, rate)"
            " VALUES ('2026-11-01', 'CLP', 'ARS', '1.58')"
        )
    with pytest.raises(sqlite3.IntegrityError), database.transaction():
        connection.execute("DELETE FROM accounts WHERE id = 1")  # it has a movement
    database.close()


class TestInstallmentsMigration:
    """009 adds installments to databases that already hold years of movements."""

    def test_a_version_8_database_with_movements_migrates(self, db_path):
        before = [m for m in load_packaged_migrations() if m.version <= 8]
        old = Database.open(db_path, before)
        old.connection.execute(
            "INSERT INTO accounts (name, type, currency, initial_balance_cents)"
            " VALUES ('Banco', 'bank', 'ARS', 0)"
        )
        category = old.connection.execute(
            "SELECT id FROM categories WHERE kind = 'expense' LIMIT 1"
        ).fetchone()[0]
        old.connection.execute(
            "INSERT INTO transactions (account_id, type, amount_cents, occurred_on, category_id)"
            " VALUES (1, 'expense', 500, '2026-01-01', ?)",
            (category,),
        )
        old.connection.commit()
        old.close()

        database = Database.open(db_path)

        assert database.schema_version == latest_schema_version()
        row = database.connection.execute(
            "SELECT installment_plan_id, installment_number FROM transactions"
        ).fetchone()
        assert tuple(row) == (None, None)
        assert database.connection.execute("PRAGMA foreign_key_check").fetchall() == []
        database.close()

    @pytest.mark.parametrize(
        ("count", "total", "first", "settled"),
        [
            (1, 100, "2026-01-01", None),  # a single payment is not a plan
            (73, 10_000, "2026-01-01", None),
            (6, 5, "2026-01-01", None),  # less than a cent each
            (6, 600, "2026-02-01", "2026-01-01"),  # paid off before it starts
        ],
    )
    def test_the_table_refuses_what_the_model_refuses(self, db_path, count, total, first, settled):
        database = Database.open(db_path)
        with pytest.raises(sqlite3.IntegrityError):
            database.connection.execute(
                "INSERT INTO installment_plans (count, total_cents, first_due_on, settled_on)"
                " VALUES (?, ?, ?, ?)",
                (count, total, first, settled),
            )
        database.close()


class TestAccountGroupsMigration:
    """010 adds account groups to databases whose accounts already hold movements."""

    def test_accounts_keep_everything_and_start_in_no_group(self, db_path):
        old = Database.open(db_path, [m for m in load_packaged_migrations() if m.version <= 9])
        with old.transaction():
            old.connection.execute(
                "INSERT INTO accounts (name, type, currency, initial_balance_cents, position)"
                " VALUES ('Banco', 'bank', 'ARS', 500, 3)"
            )
        old.close()

        database = Database.open(db_path)

        row = database.connection.execute(
            "SELECT name, initial_balance_cents, position, group_id FROM accounts"
        ).fetchone()
        assert tuple(row) == ("Banco", 500, 3, None)
        assert database.connection.execute("PRAGMA foreign_key_check").fetchall() == []
        database.close()

    def test_deleting_a_group_leaves_its_accounts_without_one(self, db_path):
        database = Database.open(db_path)
        connection = database.connection
        with database.transaction():
            connection.execute(
                "INSERT INTO account_groups (id, name, normalized_name)"
                " VALUES (1, 'Bancos', 'bancos')"
            )
            connection.execute(
                "INSERT INTO accounts (name, type, currency, group_id)"
                " VALUES ('B', 'bank', 'ARS', 1)"
            )
        with database.transaction():
            connection.execute("DELETE FROM account_groups WHERE id = 1")

        assert connection.execute("SELECT name, group_id FROM accounts").fetchall()[0][:] == (
            "B",
            None,
        )
        database.close()
