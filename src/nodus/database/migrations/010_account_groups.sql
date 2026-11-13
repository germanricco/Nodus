-- v1.6: account groups (Bancos, Billeteras, Inversiones…), one level deep, in the user's
-- own order. An account belongs to one group or to none; deleting a group leaves its
-- accounts without one, never deletes them.
CREATE TABLE account_groups (
    id              INTEGER PRIMARY KEY,
    name            TEXT    NOT NULL,
    normalized_name TEXT    NOT NULL UNIQUE,
    position        INTEGER NOT NULL DEFAULT 0
);

-- A column added with REFERENCES and a NULL default needs no rebuild of accounts.
ALTER TABLE accounts ADD COLUMN group_id INTEGER
    REFERENCES account_groups (id) ON DELETE SET NULL;

CREATE INDEX accounts_group ON accounts (group_id);
