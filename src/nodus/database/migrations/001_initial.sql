-- Initial schema for Nodus v0.1.
-- Money columns hold integer cents. Dates are ISO 8601 text (YYYY-MM-DD).

CREATE TABLE accounts (
    id                    INTEGER PRIMARY KEY,
    name                  TEXT    NOT NULL,
    type                  TEXT    NOT NULL
                          CHECK (type IN ('cash', 'bank', 'credit_card', 'savings', 'investment')),
    currency              TEXT    NOT NULL CHECK (currency IN ('ARS', 'USD')),
    initial_balance_cents INTEGER NOT NULL DEFAULT 0,
    is_archived           INTEGER NOT NULL DEFAULT 0 CHECK (is_archived IN (0, 1)),
    created_at            TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now'))
);

-- kind matches the transaction type a category can be used with.
-- parent_id makes it a subcategory; subcategories share their parent's kind.
-- is_system marks the "Otros" fallback of each kind, which cannot be deleted.
CREATE TABLE categories (
    id        INTEGER PRIMARY KEY,
    name      TEXT    NOT NULL,
    kind      TEXT    NOT NULL CHECK (kind IN ('income', 'expense')),
    color     TEXT    NOT NULL,
    parent_id INTEGER REFERENCES categories (id) ON DELETE RESTRICT,
    is_system INTEGER NOT NULL DEFAULT 0 CHECK (is_system IN (0, 1))
);

-- A plain UNIQUE would allow duplicate top-level names, because NULL parent_ids never compare equal.
CREATE UNIQUE INDEX categories_unique_name
    ON categories (kind, COALESCE(parent_id, 0), name COLLATE NOCASE);

-- Amounts are always positive; type gives the direction.
-- A transfer is two rows (expense in the source account, income in the destination)
-- sharing a transfer_id. Transfers have no category; every other transaction has one.
CREATE TABLE transactions (
    id           INTEGER PRIMARY KEY,
    account_id   INTEGER NOT NULL REFERENCES accounts (id) ON DELETE RESTRICT,
    type         TEXT    NOT NULL CHECK (type IN ('income', 'expense')),
    amount_cents INTEGER NOT NULL CHECK (amount_cents > 0),
    occurred_on  TEXT    NOT NULL,
    category_id  INTEGER REFERENCES categories (id) ON DELETE RESTRICT,
    note         TEXT    NOT NULL DEFAULT '',
    transfer_id  TEXT,
    created_at   TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now')),
    updated_at   TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now')),
    CHECK ((transfer_id IS NULL) = (category_id IS NOT NULL))
);

CREATE INDEX transactions_account     ON transactions (account_id);
CREATE INDEX transactions_occurred_on ON transactions (occurred_on);
CREATE INDEX transactions_category    ON transactions (category_id);
CREATE INDEX transactions_transfer    ON transactions (transfer_id);

-- rate = units of quote_currency per one unit of base_currency, stored as decimal text
-- so it keeps every digit the user typed.
CREATE TABLE exchange_rates (
    id             INTEGER PRIMARY KEY,
    rate_date      TEXT NOT NULL,
    base_currency  TEXT NOT NULL CHECK (base_currency IN ('ARS', 'USD')),
    quote_currency TEXT NOT NULL CHECK (quote_currency IN ('ARS', 'USD')),
    rate           TEXT NOT NULL,
    UNIQUE (rate_date, base_currency, quote_currency)
);

CREATE TABLE settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- Default categories. Users add, rename or delete their own; the two "Otros" are system
-- categories that receive the transactions of deleted ones.
INSERT INTO categories (name, kind, color, is_system) VALUES
    ('Supermercado y comida', 'expense', '#e74c3c', 0),
    ('Vivienda',              'expense', '#e67e22', 0),
    ('Servicios',             'expense', '#2980b9', 0),
    ('Transporte',            'expense', '#95a5a6', 0),
    ('Salud',                 'expense', '#2ecc71', 0),
    ('Educación',             'expense', '#8e44ad', 0),
    ('Proyectos',             'expense', '#16a085', 0),
    ('Ocio',                  'expense', '#f39c12', 0),
    ('Ropa',                  'expense', '#3498db', 0),
    ('Otros',                 'expense', '#7f8c8d', 1),
    ('Sueldo',                'income',  '#f1c40f', 0),
    ('Trabajo freelance',     'income',  '#27ae60', 0),
    ('Reembolsos',            'income',  '#1abc9c', 0),
    ('Otros',                 'income',  '#7f8c8d', 1);
