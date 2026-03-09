"""Tests for exceptions.py — custom exception types."""


def test_conflict_error_is_value_error():
    from exceptions import ConflictError
    assert issubclass(ConflictError, ValueError)


def test_conflict_error_message():
    from exceptions import ConflictError
    err = ConflictError("duplicate entry")
    assert str(err) == "duplicate entry"


def test_conflict_error_catchable_as_value_error():
    from exceptions import ConflictError
    with __import__("pytest").raises(ValueError):
        raise ConflictError("test")
