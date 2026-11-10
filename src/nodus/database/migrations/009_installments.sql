-- Purchases paid in monthly installments. The plan keeps only the calendar (how many, the
-- total and the first day; settled_on when the rest was paid off early); each installment
-- is an ordinary expense that points at it. Deleting the plan deletes its installments.
CREATE TABLE installment_plans (
    id           INTEGER PRIMARY KEY,
    count        INTEGER NOT NULL CHECK (count BETWEEN 2 AND 72),
    total_cents  INTEGER NOT NULL CHECK (total_cents >= count),
    first_due_on TEXT NOT NULL,
    settled_on   TEXT CHECK (settled_on IS NULL OR settled_on >= first_due_on),
    created_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now'))
);

ALTER TABLE transactions ADD COLUMN installment_plan_id INTEGER REFERENCES installment_plans (id) ON DELETE CASCADE;
ALTER TABLE transactions ADD COLUMN installment_number INTEGER;

CREATE INDEX transactions_installment_plan ON transactions (installment_plan_id);

-- A plan always has installments: when its last one goes (with its account, say), so does
-- the plan.
CREATE TRIGGER installment_plans_without_installments
AFTER DELETE ON transactions
WHEN OLD.installment_plan_id IS NOT NULL
 AND NOT EXISTS (SELECT 1 FROM transactions WHERE installment_plan_id = OLD.installment_plan_id)
BEGIN
    DELETE FROM installment_plans WHERE id = OLD.installment_plan_id;
END;
