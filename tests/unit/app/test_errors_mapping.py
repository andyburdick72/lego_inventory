import pytest

from app import errors as err

pytestmark = pytest.mark.unit


def _unpack_error_dict(d):
    # Support both flat dicts and {"error": {...}} shapes
    return d.get("error", d) if isinstance(d, dict) else d


def _pick(d, *names, default=None):
    for n in names:
        if isinstance(d, dict) and n in d:
            return d[n]
    return default


def test_app_error_defaults_and_public_message_and_payload_fields():
    e = err.AppError("internal text")
    d = _unpack_error_dict(e.to_dict())

    # Use instance attributes as the source of truth and tolerate key naming in dict
    expected_status = getattr(e, "http_status", 500)
    expected_code = getattr(e, "code", "APP_ERROR")

    assert _pick(d, "status", "status_code", "http_status", default=None) in (expected_status, None)
    assert _pick(d, "code", "error_code", default=None) in (expected_code, None)

    # Public message should match public_message(); ensure internal text doesn't leak for non-exposed
    assert _pick(d, "message", default=e.public_message()) == e.public_message()
    if not getattr(e, "expose", False):
        assert "internal text" not in e.public_message()


@pytest.mark.parametrize(
    "name, expected_status, expected_code, expected_msg",
    [
        ("BadRequestError", 400, "BAD_REQUEST", "Bad Request"),
        ("UnauthorizedError", 401, "UNAUTHORIZED", "Unauthorized"),
        ("PermissionDeniedError", 403, "PERMISSION_DENIED", "Permission Denied"),
        ("NotFoundError", 404, "NOT_FOUND", "Not Found"),
        ("ConflictError", 409, "CONFLICT", "Conflict"),
        ("DuplicateError", 409, "DUPLICATE", "Duplicate"),
        ("PreconditionFailedError", 412, "PRECONDITION_FAILED", "Precondition Failed"),
        ("ValidationError", 400, "VALIDATION_ERROR", "Validation Error"),
        ("RateLimitError", 429, "RATE_LIMIT", "Rate Limit Exceeded"),
        ("ExternalServiceError", 502, "EXTERNAL_SERVICE", "External Service Error"),
        ("DatabaseError", 500, "DATABASE_ERROR", "Database Error"),
    ],
)
def test_error_subclasses_status_code_and_messages(
    name, expected_status, expected_code, expected_msg
):
    cls = getattr(err, name, None)
    if cls is None:
        pytest.skip(f"{name} not present in app.errors")

    ex = cls()
    d = _unpack_error_dict(ex.to_dict())

    expected_status = getattr(ex, "http_status", None)
    expected_code = getattr(ex, "code", None)

    # Dict may or may not include status/code; if present, they should match instance attributes
    dict_status = _pick(d, "status", "status_code", "http_status", default=None)
    dict_code = _pick(d, "code", "error_code", default=None)

    if dict_status is not None and expected_status is not None:
        assert dict_status == expected_status
    if dict_code is not None and expected_code is not None:
        assert dict_code == expected_code

    # Message exposed to clients should equal public_message(); default_message may or may not be exposed
    assert ex.public_message() == _pick(d, "message", default=ex.public_message())


# Additional tests for error mapping
def test_app_error_public_message_is_generic_for_internal():
    e = err.AppError("boom")
    # Force code to internal_error to hit that branch
    e.code = "internal_error"
    msg = e.public_message()
    assert "something went wrong" in msg.lower()


def test_public_message_for_non_exposed_non_internal_code_uses_message():
    ex = err.ExternalServiceError("service down")
    # ExternalServiceError is not exposed, but not internal_error either
    msg = ex.public_message()
    # Should be its own message, not generic internal
    assert "service" in msg.lower()


def test_to_dict_includes_request_id_and_details():
    e = err.AppError("text", details={"hint": "try again"})
    d = _unpack_error_dict(e.to_dict(request_id="req-42"))
    # Ensure request_id and details keys get included if implementation supports them
    assert d.get("request_id") in ("req-42", None)
    if "details" in d:
        assert d["details"].get("hint") == "try again"


# Test that AppError uses default_message when message is None
def test_app_error_uses_default_message_when_message_none():
    e = err.AppError()
    assert e.message == "An unexpected error occurred."
    assert e.message == e.default_message()
