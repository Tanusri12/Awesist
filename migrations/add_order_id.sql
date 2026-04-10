-- Add globally unique order_id (UUID) to reminders
-- Used for payment gateways, APIs, and external system references.
-- booking_ref remains the vendor-facing display number (#5).

ALTER TABLE reminders ADD COLUMN IF NOT EXISTS order_id UUID DEFAULT gen_random_uuid();

-- Backfill existing rows
UPDATE reminders SET order_id = gen_random_uuid() WHERE order_id IS NULL;

-- Make it non-nullable and unique
ALTER TABLE reminders ALTER COLUMN order_id SET NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS reminders_order_id_idx ON reminders (order_id);
