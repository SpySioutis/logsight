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
