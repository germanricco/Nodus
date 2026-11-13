-- v1.6: savings goals. A goal is an amount to reach, by a date or not, filled by the
-- balance of the accounts the user links to it: no money moves and nothing is entered
-- by hand. An account can serve several goals, each with a share of it.
CREATE TABLE goals (
    id           INTEGER PRIMARY KEY,
    name         TEXT    NOT NULL,
    target_cents INTEGER NOT NULL CHECK (target_cents > 0),
    currency     TEXT    NOT NULL CHECK (currency IN ('ARS', 'USD', 'EUR', 'CLP')),
    target_date  TEXT,
    -- Set once, the first day the goal is reached, so it stays reached when that money
    -- is then spent; cleared when the target changes.
    reached_on   TEXT,
    -- Whether the user has seen the notice that it was reached.
    reached_seen INTEGER NOT NULL DEFAULT 0 CHECK (reached_seen IN (0, 1)),
    is_archived  INTEGER NOT NULL DEFAULT 0 CHECK (is_archived IN (0, 1)),
    position     INTEGER NOT NULL DEFAULT 0,
    created_at   TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now'))
);

-- The share of an account's balance that counts for a goal, in whole percents.
CREATE TABLE goal_accounts (
    goal_id       INTEGER NOT NULL REFERENCES goals (id) ON DELETE CASCADE,
    account_id    INTEGER NOT NULL REFERENCES accounts (id) ON DELETE CASCADE,
    share_percent INTEGER NOT NULL CHECK (share_percent BETWEEN 1 AND 100),
    PRIMARY KEY (goal_id, account_id)
);

CREATE INDEX goal_accounts_account ON goal_accounts (account_id);
