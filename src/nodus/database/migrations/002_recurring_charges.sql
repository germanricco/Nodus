-- Fixed expenses that repeat (rent, services, subscriptions) and when they are due next.
-- The amount's currency is the account's. anchor_day is the day of the month the charge
-- was set up for, so a charge on the 31st returns to the 31st after shorter months.
-- Deleting an account deletes its charges, as it deletes its movements.
CREATE TABLE recurring_charges (
    id           INTEGER PRIMARY KEY,
    name         TEXT    NOT NULL,
    amount_cents INTEGER NOT NULL CHECK (amount_cents > 0),
    account_id   INTEGER NOT NULL REFERENCES accounts (id) ON DELETE CASCADE,
    category_id  INTEGER NOT NULL REFERENCES categories (id) ON DELETE RESTRICT,
    frequency    TEXT    NOT NULL CHECK (frequency IN
                     ('weekly', 'biweekly', 'monthly', 'quarterly', 'semiannual', 'annual')),
    anchor_day   INTEGER NOT NULL CHECK (anchor_day BETWEEN 1 AND 31),
    next_due_on  TEXT    NOT NULL,
    is_active    INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    note         TEXT    NOT NULL DEFAULT '',
    created_at   TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now'))
);

CREATE INDEX recurring_charges_account ON recurring_charges (account_id);
