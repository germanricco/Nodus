-- The refunds category is found by this mark, not by its name, so renaming or deleting
-- «Reembolsos» can no longer silently turn off linking refunds to their expenses.
-- Like «Otros», it can no longer be renamed or deleted.
ALTER TABLE categories ADD COLUMN is_refunds INTEGER NOT NULL DEFAULT 0
    CHECK (is_refunds IN (0, 1));

CREATE UNIQUE INDEX categories_one_refunds ON categories (is_refunds) WHERE is_refunds = 1;

-- The default «Reembolsos», as the initial migration created it.
UPDATE categories SET is_refunds = 1
WHERE id = (
    SELECT id FROM categories
    WHERE kind = 'income' AND parent_id IS NULL AND name = 'Reembolsos' COLLATE NOCASE
    ORDER BY id LIMIT 1
);

-- Renamed: the top-level income category most refunds were saved in.
UPDATE categories SET is_refunds = 1
WHERE NOT EXISTS (SELECT 1 FROM categories WHERE is_refunds = 1)
  AND id = (
    SELECT t.category_id FROM transactions t
    JOIN categories c ON c.id = t.category_id
    WHERE t.refund_of_id IS NOT NULL AND c.kind = 'income' AND c.parent_id IS NULL
      AND c.is_system = 0
    GROUP BY t.category_id ORDER BY COUNT(*) DESC, t.category_id LIMIT 1
);

-- Deleted, and no refund to tell where it went: a new one.
INSERT INTO categories (name, kind, color, is_system, is_refunds)
SELECT 'Reembolsos', 'income', '#1abc9c', 0, 1
WHERE NOT EXISTS (SELECT 1 FROM categories WHERE is_refunds = 1);
