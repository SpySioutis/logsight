-- 0005_error_states: lifecycle state per error fingerprint.

CREATE TABLE IF NOT EXISTS error_group_states (
    fingerprint VARCHAR(64) PRIMARY KEY,
    status VARCHAR(16) NOT NULL DEFAULT 'open',
    assignee VARCHAR(256),
    note TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_error_group_states_status
        CHECK (status IN ('open', 'acknowledged', 'resolved', 'muted'))
);
