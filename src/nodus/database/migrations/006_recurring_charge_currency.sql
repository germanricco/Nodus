-- A recurring charge keeps its own currency, so a subscription of a fixed amount in dollars
-- can be paid from a peso account. Existing charges take their account's currency, which
-- is what they had so far.
ALTER TABLE recurring_charges ADD COLUMN currency TEXT NOT NULL DEFAULT 'ARS'
    CHECK (currency IN ('ARS', 'USD'));

UPDATE recurring_charges
SET currency = (SELECT accounts.currency FROM accounts WHERE accounts.id = recurring_charges.account_id);

-- Pesos per dollar of the last payment of a dollar charge paid in pesos, card taxes
-- included, as a decimal string; it estimates the next payment. NULL until then.
ALTER TABLE recurring_charges ADD COLUMN last_paid_rate TEXT;
