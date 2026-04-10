-- Soft delete support for payments
-- Adds removed_at timestamp so we know when a payment was removed and by whom.
-- status = 'removed' filters it from all existing queries (they filter on 'pending'/'paid').

ALTER TABLE payments ADD COLUMN IF NOT EXISTS removed_at TIMESTAMPTZ;
