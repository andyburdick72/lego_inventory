"""Additional tests for error classes to improve coverage."""
import pytest

from app.errors import (
    AppError,
    BadRequestError,
    ConflictError,
    DatabaseError,
    DuplicateError,
    ExternalServiceError,
    NotFoundError,
    PermissionDeniedError,
    PreconditionFailedError,
    RateLimitError,
    UnauthorizedError,
    ValidationError,
)


@pytest.mark.unit
def test_app_error_with_message():
    """Test AppError with custom message."""
    e = AppError("Custom error message")
    assert e.message == "Custom error message"
    assert e.details is None


@pytest.mark.unit
def test_app_error_with_details():
    """Test AppError with details."""
    details = {"field": "name", "value": "test"}
    e = AppError("Error occurred", details=details)
    assert e.message == "Error occurred"
    assert e.details == details


@pytest.mark.unit
def test_app_error_without_message_uses_default():
    """Test AppError without message uses default."""
    e = AppError()
    assert e.message == "An unexpected error occurred."
    assert e.message == e.default_message()


@pytest.mark.unit
def test_app_error_to_dict_with_request_id():
    """Test to_dict includes request_id when provided."""
    e = AppError("Test error")
    d = e.to_dict(request_id="req-123")
    assert "error" in d
    assert d["error"].get("request_id") == "req-123"


@pytest.mark.unit
def test_app_error_to_dict_with_details():
    """Test to_dict includes details when provided."""
    e = AppError("Test error", details={"key": "value"})
    d = e.to_dict()
    assert "error" in d
    assert d["error"].get("details") == {"key": "value"}


@pytest.mark.unit
def test_app_error_public_message_internal_error():
    """Test public_message for internal_error code."""
    e = AppError("Internal details")
    e.code = "internal_error"
    msg = e.public_message()
    assert "something went wrong" in msg.lower()
    assert "Internal details" not in msg


@pytest.mark.unit
def test_app_error_public_message_exposed():
    """Test public_message for exposed errors."""
    e = NotFoundError("Resource not found")
    assert e.expose is True
    msg = e.public_message()
    assert "not found" in msg.lower()


@pytest.mark.unit
def test_app_error_public_message_non_exposed_non_internal():
    """Test public_message for non-exposed, non-internal errors."""
    e = ExternalServiceError("Service unavailable")
    assert e.expose is False
    assert e.code != "internal_error"
    msg = e.public_message()
    assert "service" in msg.lower() or "unavailable" in msg.lower()


@pytest.mark.unit
def test_bad_request_error():
    """Test BadRequestError."""
    e = BadRequestError("Invalid input")
    assert e.http_status == 400
    assert e.code == "bad_request"
    assert e.message == "Invalid input"


@pytest.mark.unit
def test_unauthorized_error():
    """Test UnauthorizedError."""
    e = UnauthorizedError("Not authenticated")
    assert e.http_status == 401
    assert e.code == "unauthorized"


@pytest.mark.unit
def test_permission_denied_error():
    """Test PermissionDeniedError."""
    e = PermissionDeniedError("Access denied")
    assert e.http_status == 403
    assert e.code == "permission_denied"


@pytest.mark.unit
def test_not_found_error():
    """Test NotFoundError."""
    e = NotFoundError("Resource missing")
    assert e.http_status == 404
    assert e.code == "not_found"
    assert e.expose is True


@pytest.mark.unit
def test_not_found_error_with_details():
    """Test NotFoundError with details."""
    e = NotFoundError("Not found", details={"id": 123})
    assert e.details == {"id": 123}


@pytest.mark.unit
def test_conflict_error():
    """Test ConflictError."""
    e = ConflictError("Resource conflict")
    assert e.http_status == 409
    assert e.code == "conflict"


@pytest.mark.unit
def test_duplicate_error():
    """Test DuplicateError."""
    e = DuplicateError("Duplicate entry")
    assert e.http_status == 409
    assert e.code == "duplicate"


@pytest.mark.unit
def test_precondition_failed_error():
    """Test PreconditionFailedError."""
    e = PreconditionFailedError("Precondition failed")
    assert e.http_status == 412
    assert e.code == "precondition_failed"


@pytest.mark.unit
def test_validation_error():
    """Test ValidationError."""
    e = ValidationError("Invalid data")
    assert e.http_status == 422
    assert e.code == "validation_error"


@pytest.mark.unit
def test_rate_limit_error():
    """Test RateLimitError."""
    e = RateLimitError("Too many requests")
    assert e.http_status == 429
    assert e.code == "rate_limited"


@pytest.mark.unit
def test_external_service_error():
    """Test ExternalServiceError."""
    e = ExternalServiceError("Service error")
    assert e.http_status == 502
    assert e.code == "external_service_error"
    assert e.expose is False


@pytest.mark.unit
def test_database_error():
    """Test DatabaseError."""
    e = DatabaseError("Database error")
    assert e.http_status == 503
    assert e.code == "database_error"
    assert e.expose is False

