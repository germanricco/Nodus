-- Refunds: an income that pays back an expense points at it. An expense may have several
-- partial refunds; deleting it leaves them as plain income.
ALTER TABLE transactions ADD COLUMN refund_of_id INTEGER REFERENCES transactions (id) ON DELETE SET NULL;

CREATE INDEX transactions_refund_of ON transactions (refund_of_id);

-- Tags group transactions across categories, such as a trip. Like payees, a tag's name is
-- unique once normalized. Deleting a tag or a transaction removes their links.
CREATE TABLE tags (
    id              INTEGER PRIMARY KEY,
    name            TEXT NOT NULL,
    normalized_name TEXT NOT NULL UNIQUE,
    color           TEXT NOT NULL,
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now'))
);

CREATE TABLE transaction_tags (
    transaction_id INTEGER NOT NULL REFERENCES transactions (id) ON DELETE CASCADE,
    tag_id         INTEGER NOT NULL REFERENCES tags (id) ON DELETE CASCADE,
    PRIMARY KEY (transaction_id, tag_id)
);

CREATE INDEX transaction_tags_tag ON transaction_tags (tag_id);
