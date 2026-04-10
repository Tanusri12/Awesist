-- Track WhatsApp delivery status for customer notifications.
-- customer_msg_id  = wamid returned by WhatsApp Cloud API when we send the nudge.
-- customer_msg_status = last known status: sent | delivered | read

ALTER TABLE payments ADD COLUMN IF NOT EXISTS customer_msg_id TEXT;
ALTER TABLE payments ADD COLUMN IF NOT EXISTS customer_msg_status TEXT DEFAULT 'sent';
