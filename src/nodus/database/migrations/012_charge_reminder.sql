-- v1.8: «Ya lo vi» on a charge due soon. Its warning stays quiet until this day (the
-- day before it is due); empty when nothing was put off. Paying or skipping the charge
-- clears it, so the next due date warns again.
ALTER TABLE recurring_charges ADD COLUMN remind_from TEXT;
