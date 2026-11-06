-- Monthly spending limits per expense category, in pesos, with their history: a row
-- applies from start_month (YYYY-MM) until the category's next row. A NULL amount means
-- "no budget from this month on", so removing a budget keeps the past months as they were.
-- Deleting a category deletes its limits.
CREATE TABLE budget_limits (
    id           INTEGER PRIMARY KEY,
    category_id  INTEGER NOT NULL REFERENCES categories (id) ON DELETE CASCADE,
    start_month  TEXT    NOT NULL,
    amount_cents INTEGER CHECK (amount_cents IS NULL OR amount_cents > 0),
    UNIQUE (category_id, start_month)
);
