-- An investment or savings account changes value by itself, with interest or prices. An
-- adjustment records that change, with its sign, so the balance follows the real value.
-- It lives apart from transactions because it is neither income nor expense: every
-- statistic reads transactions only, and the balance adds both.
CREATE TABLE value_adjustments (
    id           INTEGER PRIMARY KEY,
    account_id   INTEGER NOT NULL REFERENCES accounts (id) ON DELETE CASCADE,
    occurred_on  TEXT    NOT NULL,
    amount_cents INTEGER NOT NULL CHECK (amount_cents <> 0),
    note         TEXT    NOT NULL DEFAULT ''
);

CREATE INDEX value_adjustments_account ON value_adjustments (account_id, occurred_on);
