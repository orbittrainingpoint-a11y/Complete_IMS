-- Office network for attendance (run once on the CRM database "leads")
CREATE TABLE IF NOT EXISTS attendance_office_network (
    id INTEGER NOT NULL AUTO_INCREMENT,
    cidr VARCHAR(64) NOT NULL,
    label VARCHAR(100),
    added_by_id INTEGER,
    created_at DATETIME,
    PRIMARY KEY (id)
);
