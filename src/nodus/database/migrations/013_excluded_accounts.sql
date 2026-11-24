-- An account the user keeps but that is not theirs, such as one shared with a band:
-- its balance and its movements stay out of every total and statistic.
ALTER TABLE accounts ADD COLUMN excluded INTEGER NOT NULL DEFAULT 0
    CHECK (excluded IN (0, 1));
