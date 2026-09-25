CREATE TABLE attendance_session (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	user_id INTEGER NOT NULL, 
	work_date DATE NOT NULL, 
	login_at DATETIME NOT NULL, 
	last_activity_at DATETIME NOT NULL, 
	logout_at DATETIME, 
	status VARCHAR(15), 
	logout_type VARCHAR(20), 
	warning_pending BOOL, 
	admin_note VARCHAR(300), 
	reviewed_by_id INTEGER, 
	created_at DATETIME, 
	PRIMARY KEY (id)
);
CREATE INDEX ix_attendance_session_status ON attendance_session (status);
CREATE INDEX ix_attendance_session_work_date ON attendance_session (work_date);
CREATE INDEX ix_attendance_session_user_id ON attendance_session (user_id);
CREATE TABLE attendance_break (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	session_id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	start_at DATETIME NOT NULL, 
	end_at DATETIME, 
	break_type VARCHAR(12), 
	PRIMARY KEY (id), 
	FOREIGN KEY(session_id) REFERENCES attendance_session (id)
);
CREATE INDEX ix_attendance_break_session_id ON attendance_break (session_id);
