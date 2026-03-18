

CREATE INDEX idx_reminders_due
ON reminders(status, reminder_time);

CREATE UNIQUE INDEX unique_reminder
ON reminders(user_id, task, reminder_time);



-- Query reminders per user

CREATE INDEX reminder_user_idx
ON reminders(user_id);


ALTER TABLE users
ADD COLUMN morning_summary_enabled BOOLEAN DEFAULT TRUE;



