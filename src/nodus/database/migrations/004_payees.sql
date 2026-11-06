-- Who a transaction was paid to or received from. A payee's name is unique once
-- normalized (lowercase, no accents or signs), so "Café Martínez" and "cafe martinez" are
-- the same payee. Deleting a payee leaves its transactions without one; deleting a
-- category leaves its payees without a default category.
CREATE TABLE payees (
    id                  INTEGER PRIMARY KEY,
    name                TEXT NOT NULL,
    normalized_name     TEXT NOT NULL UNIQUE,
    default_category_id INTEGER REFERENCES categories (id) ON DELETE SET NULL,
    created_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now'))
);

ALTER TABLE transactions ADD COLUMN payee_id INTEGER REFERENCES payees (id) ON DELETE SET NULL;

CREATE INDEX transactions_payee ON transactions (payee_id);
