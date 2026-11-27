"""API integration tests against an isolated SQLite database."""

import io

PLAIN_LOG = b"""2024-05-01T10:00:00Z INFO service:api source:web-1 server started on :8000
2024-05-01T10:01:00Z WARN service:api source:web-1 slow query took 1200ms id=7
2024-05-01T10:02:00Z ERROR service:api source:web-1 connection refused to 10.0.0.5:5432
2024-05-01T10:03:00Z ERROR service:api source:web-2 connection refused to 10.0.0.9:5432
2024-05-01T10:04:00Z CRITICAL service:worker source:worker-1 out of memory
"""

JSONL_LOG = b"""{"timestamp": "2024-05-01T11:00:00Z", "level": "info", "service": "web", "msg": "ok"}
{"timestamp": "2024-05-01T11:01:00Z", "level": "error", "service": "web", "msg": "disk full on /dev/sda1"}
not-json-at-all
{"timestamp": "2024-05-01T11:02:00Z", "level": "weird-level", "service": "web", "msg": "kept as unknown"}
"""


def upload(client, filename, content):
    return client.post("/api/imports/upload", files={"file": (filename, io.BytesIO(content))})


def test_health(client):
    assert client.get("/api/health").json()["status"] == "ok"


def test_upload_plain_and_explore(client):
    resp = upload(client, "app.log", PLAIN_LOG)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["parsed_count"] == 5
    assert body["error_count"] == 0

    logs = client.get("/api/logs", params={"page_size": 50}).json()
    assert logs["total"] == 5

    errors = client.get("/api/logs", params={"severity": ["ERROR"], "page_size": 50}).json()
    assert errors["total"] == 2

    search = client.get("/api/logs", params={"q": "slow query"}).json()
    assert search["total"] == 1

    ranged = client.get(
        "/api/logs",
        params={"date_from": "2024-05-01T10:01:00Z", "date_to": "2024-05-01T10:03:30Z", "page_size": 50},
    ).json()
    assert ranged["total"] == 3


def test_upload_rejects_unsupported_type(client):
    resp = upload(client, "app.xml", b"<logs><entry>nope</entry></logs>")
    assert resp.status_code == 400


def test_upload_duplicate_strategy(client):
    first = upload(client, "app.log", PLAIN_LOG).json()
    second = upload(client, "app-copy.log", PLAIN_LOG).json()
    assert second["duplicate"] is True
    assert second["duplicate_of"] == first["id"]
    assert second["status"] == "duplicate"
    # No rows re-inserted.
    assert client.get("/api/logs", params={"page_size": 1}).json()["total"] == 5


def test_jsonl_partial_errors(client):
    resp = upload(client, "app.jsonl", JSONL_LOG)
    assert resp.status_code == 201
    body = resp.json()
    assert body["parsed_count"] == 3
    assert body["error_count"] == 1
    unknowns = client.get("/api/logs", params={"severity": ["UNKNOWN"], "page_size": 50}).json()
    assert unknowns["total"] >= 1


def test_invalid_severity_rejected(client):
    resp = client.get("/api/logs", params={"severity": ["BOGUS"]})
    assert resp.status_code == 400


def test_dashboard_and_errors_from_real_data(client):
    upload(client, "app.log", PLAIN_LOG)
    summary = client.get("/api/dashboard/summary").json()
    assert summary["total"] == 5
    assert summary["errors"] == 3  # 2 ERROR + 1 CRITICAL
    assert summary["critical"] == 1

    groups = client.get("/api/errors/groups").json()
    refused = [g for g in groups if "connection refused" in g["sample"]]
    assert refused and refused[0]["count"] == 2
    fp = refused[0]["fingerprint"]
    entries = client.get(f"/api/errors/groups/{fp}", params={"page_size": 25}).json()
    assert entries["total"] == 2
    assert len(entries["items"]) == 2

    timeline = client.get("/api/dashboard/timeline").json()
    assert timeline and timeline[0]["total"] == 5


def test_delete_import_cascades(client):
    record = upload(client, "app.log", PLAIN_LOG).json()
    assert client.delete(f"/api/imports/{record['id']}").status_code == 204
    assert client.get("/api/logs", params={"page_size": 1}).json()["total"] == 0


def test_saved_filters_crud(client):
    created = client.post(
        "/api/filters", json={"name": "api errors", "params": {"severity": ["ERROR"], "service": "api"}}
    )
    assert created.status_code == 201
    fid = created.json()["id"]
    assert len(client.get("/api/filters").json()) == 1

    clash = client.post("/api/filters", json={"name": "api errors", "params": {}})
    assert clash.status_code == 409

    updated = client.put(fid := f"/api/filters/{fid}", json={"name": "api errors", "params": {"q": "boom"}})
    assert updated.status_code == 200
    assert updated.json()["params"] == {"q": "boom"}

    assert client.delete(fid).status_code == 204
    assert client.get("/api/filters").json() == []


CSV_LOG = b"""timestamp,level,service,source,message,trace_id,request_id
2024-05-01T10:00:00Z,INFO,api,web-1,server started,abc-123,req-1
2024-05-01T10:01:00Z,ERROR,api,web-1,connection refused,abc-123,req-2
"""

SYSLOG_LOG = (
    b'<165>1 2024-05-01T10:00:00.000Z web-1 api - - [exampleSDID@32473 trace_id="t-1"] server started\n'
    b"<27>1 2024-05-01T10:01:00.000Z web-1 api - - - disk failure on /dev/sda1\n"
)

MULTILINE_LOG = (
    b"2024-05-01T10:00:00Z ERROR service:api source:web-1 NullPointerException in handler\n"
    b"\tat com.example.Handler.handle(Handler.java:42)\n"
    b"\tat com.example.Main.main(Main.java:10)\n"
    b"Caused by: java.lang.NullPointerException\n"
    b"2024-05-01T10:01:00Z INFO service:api source:web-1 recovered\n"
)

TRACE_LOG = b"""{"timestamp": "2024-05-01T11:00:00Z", "level": "info", "service": "web", "msg": "start", "trace_id": "t-9"}
{"timestamp": "2024-05-01T11:00:01Z", "level": "error", "service": "db", "msg": "boom", "trace_id": "t-9", "request_id": "r-1"}
"""


def test_csv_import_with_traces(client):
    resp = upload(client, "events.csv", CSV_LOG)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["format"] == "csv"
    assert body["parsed_count"] == 2

    errors = client.get("/api/logs", params={"severity": ["ERROR"], "page_size": 50}).json()
    assert errors["total"] == 1
    assert errors["items"][0]["trace_id"] == "abc-123"
    assert errors["items"][0]["request_id"] == "req-2"

    traced = client.get("/api/logs", params={"trace_id": "abc-123", "page_size": 50}).json()
    assert traced["total"] == 2


def test_syslog_import(client):
    resp = upload(client, "sys.log", SYSLOG_LOG)
    assert resp.status_code == 201, resp.text
    assert resp.json()["parsed_count"] == 2

    logs = client.get("/api/logs", params={"page_size": 50, "sort": "timestamp", "direction": "asc"}).json()
    assert logs["total"] == 2
    first, second = logs["items"]
    assert first["severity"] == "INFO"  # PRI 165 -> notice
    assert first["service"] == "api"
    assert first["source"] == "web-1"
    assert first["trace_id"] == "t-1"
    assert second["severity"] == "ERROR"  # PRI 27 -> err


def test_multiline_stacktrace_joined(client):
    resp = upload(client, "stack.log", MULTILINE_LOG)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["total_lines"] == 5
    assert body["parsed_count"] == 2

    logs = client.get("/api/logs", params={"severity": ["ERROR"], "page_size": 50}).json()
    assert logs["total"] == 1
    assert "at com.example.Handler.handle" in logs["items"][0]["message"]
    assert "Caused by" in logs["items"][0]["message"]


def test_gzip_import(client):
    import gzip

    resp = upload(client, "app.log.gz", gzip.compress(PLAIN_LOG))
    assert resp.status_code == 201, resp.text
    assert resp.json()["parsed_count"] == 5
    assert client.get("/api/logs", params={"page_size": 1}).json()["total"] == 5


def test_zip_import_bundle(client):
    import zipfile

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("a.log", PLAIN_LOG.decode())
        zf.writestr("b.csv", CSV_LOG.decode())
        zf.writestr("notes.md", "# not a log file")
    resp = upload(client, "bundle.zip", buf.getvalue())
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["format"] == "zip"
    assert body["parsed_count"] == 7


def test_zip_without_logs_fails(client):
    import zipfile

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("readme.md", "# nothing to import")
    resp = upload(client, "empty.zip", buf.getvalue())
    assert resp.status_code == 422


def test_search_operators_and_snippets(client):
    upload(client, "app.log", PLAIN_LOG)

    phrase = client.get("/api/logs", params={"q": '"slow query"'}).json()
    assert phrase["total"] == 1
    assert "<mark>" in (phrase["items"][0]["snippet"] or "")

    excluded = client.get("/api/logs", params={"q": "connection -refused"}).json()
    assert excluded["total"] == 0

    kept = client.get("/api/logs", params={"q": "connection -memory"}).json()
    assert kept["total"] == 2

    by_service = client.get("/api/logs", params={"q": "service:api", "page_size": 50}).json()
    assert by_service["total"] == 4  # the CRITICAL line belongs to service:worker

    by_source = client.get("/api/logs", params={"q": "source:web-2"}).json()
    assert by_source["total"] == 1

    by_severity = client.get("/api/logs", params={"q": "severity:error", "page_size": 50}).json()
    assert by_severity["total"] == 2

    ranked = client.get(
        "/api/logs", params={"q": "connection", "sort": "relevance", "page_size": 50}
    ).json()
    assert ranked["total"] == 2


def test_trace_endpoints(client):
    upload(client, "trace.jsonl", TRACE_LOG)

    listed = client.get("/api/traces").json()
    assert len(listed) == 1
    assert listed[0]["trace_id"] == "t-9"
    assert listed[0]["count"] == 2

    detail = client.get("/api/traces/t-9").json()
    assert detail["count"] == 2
    assert detail["services"] == ["db", "web"]
    assert detail["duration_seconds"] == 1.0
    assert [e["service"] for e in detail["entries"]] == ["web", "db"]

    via_request = client.get("/api/traces/r-1").json()
    assert via_request["count"] == 1

    assert client.get("/api/traces/does-not-exist").status_code == 404


def test_error_group_lifecycle(client):
    upload(client, "app.log", PLAIN_LOG)
    groups = client.get("/api/errors/groups").json()
    fp = next(g["fingerprint"] for g in groups if "connection refused" in g["sample"])

    state = client.put(
        f"/api/errors/groups/{fp}/state",
        json={"status": "acknowledged", "assignee": "ops", "note": "known outage"},
    )
    assert state.status_code == 200, state.text
    assert state.json()["assignee"] == "ops"

    groups = client.get("/api/errors/groups").json()
    updated = next(g for g in groups if g["fingerprint"] == fp)
    assert updated["status"] == "acknowledged"
    assert updated["note"] == "known outage"

    assert any(
        g["fingerprint"] == fp for g in client.get("/api/errors/groups", params={"status": "acknowledged"}).json()
    )
    assert all(
        g["fingerprint"] != fp for g in client.get("/api/errors/groups", params={"status": "resolved"}).json()
    )
    assert client.get("/api/errors/groups", params={"status": "bogus"}).status_code == 400
    assert (
        client.put(f"/api/errors/groups/{fp}/state", json={"status": "bogus"}).status_code == 422
    )
    assert client.put("/api/errors/groups/deadbeef/state", json={"status": "open"}).status_code == 404

    trend = client.get(f"/api/errors/groups/{fp}/trend").json()
    assert len(trend) == 1
    assert trend[0]["count"] == 2

    client.put(f"/api/errors/groups/{fp}/state", json={"status": "muted"})
    top = client.get("/api/dashboard/top-errors").json()
    assert all(g["fingerprint"] != fp for g in top)


def test_failed_zip_member_rolls_back_partial_rows(client, monkeypatch):
    import zipfile

    from app import import_service

    # Tiny batches so the good member's rows are committed before the
    # bad member fails; the failure must remove them again.
    monkeypatch.setattr(import_service, "CHUNK_ROWS", 2)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("a.log", PLAIN_LOG.decode())
        zf.writestr("b.json", "{not valid json")
    resp = upload(client, "partial.zip", buf.getvalue())
    assert resp.status_code == 422
    assert client.get("/api/logs", params={"page_size": 1}).json()["total"] == 0
    record = client.get("/api/imports").json()[0]
    assert record["status"] == "failed"
    assert record["parsed_count"] == 0


def test_decompressed_cap_marks_import_failed(client, monkeypatch):
    import gzip

    from app import import_service

    monkeypatch.setattr(import_service, "CHUNK_ROWS", 2)
    # Raw upload fits, but the decompressed stream exceeds the cap.
    monkeypatch.setattr(type(import_service.settings), "max_upload_bytes", property(lambda self: 600))
    payload = PLAIN_LOG * 20
    assert len(gzip.compress(payload)) < 600 < len(payload)
    resp = upload(client, "big.log.gz", gzip.compress(payload))
    assert resp.status_code == 413
    record = client.get("/api/imports").json()[0]
    assert record["status"] == "failed"
    assert client.get("/api/logs", params={"page_size": 1}).json()["total"] == 0


def test_recover_interrupted_imports(client, db_session):
    from app.import_service import recover_interrupted_imports
    from app.models import Import, LogEntry

    stuck = Import(filename="x.log", file_size=1, file_hash="h" * 64, format="plaintext", status="processing")
    db_session.add(stuck)
    db_session.commit()
    db_session.add(LogEntry(import_id=stuck.id, severity="INFO", message="partial"))
    db_session.commit()
    assert recover_interrupted_imports(db_session) == 1
    record = client.get(f"/api/imports/{stuck.id}").json()
    assert record["status"] == "failed"
    assert "interrupted" in record["error_message"]
    assert client.get("/api/logs").json()["total"] == 0
