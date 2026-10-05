-- Google Sheet two-way sync: link each imported row to its lead and track its sheet row number.
-- Run once on the CRM database (leads) before deploying this version.
ALTER TABLE sheet_sync_row
  ADD COLUMN lead_id INT NULL,
  ADD COLUMN row_number INT NULL;
