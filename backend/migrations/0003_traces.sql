-- 0003_traces: trace/request correlation columns on log entries.

ALTER TABLE log_entries ADD COLUMN IF NOT EXISTS trace_id VARCHAR(128);
ALTER TABLE log_entries ADD COLUMN IF NOT EXISTS request_id VARCHAR(128);

CREATE INDEX IF NOT EXISTS ix_log_entries_trace_id ON log_entries (trace_id);
CREATE INDEX IF NOT EXISTS ix_log_entries_request_id ON log_entries (request_id);
