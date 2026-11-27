"""Error-grouping fingerprint tests."""

from app.grouping import fingerprint, normalize_message


def test_same_shape_groups_together():
    a = fingerprint("connection refused to 10.0.0.5:5432 after 3 retries")
    b = fingerprint("connection refused to 10.0.0.9:5432 after 7 retries")
    assert a == b


def test_different_errors_stay_apart():
    assert fingerprint("connection refused") != fingerprint("out of memory")


def test_uuid_and_numbers_masked():
    a = normalize_message("request 550e8400-e29b-41d4-a716-446655440000 failed after 120ms")
    b = normalize_message("request 123e4567-e89b-12d3-a456-426614174000 failed after 5ms")
    assert a == b


def test_deterministic_and_bounded():
    fp = fingerprint("boom")
    assert fp == fingerprint("boom")
    assert len(fp) == 32
    assert len(normalize_message("x " * 1000)) <= 500


def test_timestamps_do_not_split_groups():
    # The hour in "T10:00" used to survive masking ("t10"), splitting one
    # error into a group per hour of day.
    same = [
        "2024-05-01T10:00:00Z ERROR boom",
        "2024-05-05T09:00:00Z ERROR boom",
        "2024-06-30T23:59:59.123+02:00 ERROR boom",
        "2024-06-30 23:59:59,123 ERROR boom",
    ]
    assert len({fingerprint(m) for m in same}) == 1
    assert fingerprint("May  1 08:11:00 host app: boom") == fingerprint("Jun 12 18:01:02 host app: boom")
    assert normalize_message("2024-05-01T10:00:00Z ERROR boom") == "<ts> error boom"


def test_timestamp_rules_keep_messages_distinct():
    assert fingerprint("2024-05-01T10:00:00Z ERROR boom") != fingerprint("2024-05-01T10:00:00Z ERROR bang")


def test_number_length_does_not_split_groups():
    # Integers with 4+ digits used to become <hex>, shorter ones <n>.
    assert fingerprint("line 120 connection refused") == fingerprint("line 10020 connection refused")
    assert fingerprint("retry 3 of 5") == fingerprint("retry 3 of 1234567")


def test_hex_ids_still_masked():
    assert fingerprint("job 3fa9c2e1 failed") == fingerprint("job 9bc0d1e2 failed")
    assert normalize_message("ptr 0xdeadbeef commit a1b2c3d") == "ptr <hex> commit <hex>"
