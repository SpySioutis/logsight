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
    resp = upload(client, "app.csv", b"a,b,c")
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
    entries = client.get(f"/api/errors/groups/{fp}").json()
    assert entries["total"] == 2

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
