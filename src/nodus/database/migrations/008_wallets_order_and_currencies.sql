-- v1.1: virtual wallets as an account type, accounts in the user's own order, and euros
-- and Chilean pesos besides pesos and dollars.
--
-- SQLite cannot change a CHECK constraint, so the three tables that limit types or
-- currencies are rebuilt with the usual steps: create the new table, copy, drop the old one
-- and rename. Database._apply runs this with foreign keys off and checks them before
-- committing, because transactions, recurring charges and value adjustments refer to
-- accounts.

-- Accounts: 'wallet' type, two more currencies and their position in the list. Every
-- account starts at position 0, and the app breaks ties by name, so the order stays the
-- alphabetical one users had until they move an account.
CREATE TABLE accounts_new (
    id                    INTEGER PRIMARY KEY,
    name                  TEXT    NOT NULL,
    type                  TEXT    NOT NULL CHECK (type IN
                              ('cash', 'bank', 'wallet', 'credit_card', 'savings', 'investment')),
    currency              TEXT    NOT NULL CHECK (currency IN ('ARS', 'USD', 'EUR', 'CLP')),
    initial_balance_cents INTEGER NOT NULL DEFAULT 0,
    is_archived           INTEGER NOT NULL DEFAULT 0 CHECK (is_archived IN (0, 1)),
    position              INTEGER NOT NULL DEFAULT 0,
    created_at            TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now'))
);
INSERT INTO accounts_new
    (id, name, type, currency, initial_balance_cents, is_archived, position, created_at)
SELECT id, name, type, currency, initial_balance_cents, is_archived, 0, created_at
FROM accounts;
DROP TABLE accounts;
ALTER TABLE accounts_new RENAME TO accounts;

-- Exchange rates: one history per foreign currency, each against pesos.
CREATE TABLE exchange_rates_new (
    id             INTEGER PRIMARY KEY,
    rate_date      TEXT NOT NULL,
    base_currency  TEXT NOT NULL CHECK (base_currency IN ('ARS', 'USD', 'EUR', 'CLP')),
    quote_currency TEXT NOT NULL CHECK (quote_currency IN ('ARS', 'USD', 'EUR', 'CLP')),
    rate           TEXT NOT NULL,
    UNIQUE (rate_date, base_currency, quote_currency)
);
INSERT INTO exchange_rates_new (id, rate_date, base_currency, quote_currency, rate)
SELECT id, rate_date, base_currency, quote_currency, rate FROM exchange_rates;
DROP TABLE exchange_rates;
ALTER TABLE exchange_rates_new RENAME TO exchange_rates;

-- Recurring charges: a charge on a euro or Chilean peso account is in that currency.
CREATE TABLE recurring_charges_new (
    id             INTEGER PRIMARY KEY,
    name           TEXT    NOT NULL,
    amount_cents   INTEGER NOT NULL CHECK (amount_cents > 0),
    account_id     INTEGER NOT NULL REFERENCES accounts (id) ON DELETE CASCADE,
    category_id    INTEGER NOT NULL REFERENCES categories (id) ON DELETE RESTRICT,
    frequency      TEXT    NOT NULL CHECK (frequency IN
                       ('weekly', 'biweekly', 'monthly', 'quarterly', 'semiannual', 'annual')),
    anchor_day     INTEGER NOT NULL CHECK (anchor_day BETWEEN 1 AND 31),
    next_due_on    TEXT    NOT NULL,
    is_active      INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    note           TEXT    NOT NULL DEFAULT '',
    created_at     TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now')),
    currency       TEXT    NOT NULL DEFAULT 'ARS'
                           CHECK (currency IN ('ARS', 'USD', 'EUR', 'CLP')),
    last_paid_rate TEXT
);
INSERT INTO recurring_charges_new
    (id, name, amount_cents, account_id, category_id, frequency, anchor_day, next_due_on,
     is_active, note, created_at, currency, last_paid_rate)
SELECT id, name, amount_cents, account_id, category_id, frequency, anchor_day, next_due_on,
       is_active, note, created_at, currency, last_paid_rate
FROM recurring_charges;
DROP TABLE recurring_charges;
ALTER TABLE recurring_charges_new RENAME TO recurring_charges;
CREATE INDEX recurring_charges_account ON recurring_charges (account_id);
