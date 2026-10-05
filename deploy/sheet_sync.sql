-- Google Sheet social-lead sync: two new tables (additive only).
-- Run on the CRM database (leads) once, before enabling GOOGLE_SHEET_ENABLED=1.
CREATE TABLE IF NOT EXISTS sheet_sync_row (
  id INT AUTO_INCREMENT PRIMARY KEY,
  external_id VARCHAR(64) NOT NULL UNIQUE,
  imported_at DATETIME NULL
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS sheet_sync_state (
  id INT PRIMARY KEY,
  last_run_at DATETIME NULL,
  last_status VARCHAR(20) NULL,
  last_error TEXT NULL,
  last_counts VARCHAR(200) NULL,
  rows_seen INT DEFAULT 0
) ENGINE=InnoDB;
