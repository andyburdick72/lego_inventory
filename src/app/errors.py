# src/app/errors.py
from __future__ import annotations

from typing import Any


class AppError(Exception):
    """
    Base application error.

    Attributes:
        message: Human-friendly explanation.
        details: Optional machine-friendly context (dict/str).
        http_status: HTTP status code to return.
        code: Stable, snake_case application code (e.g., 'not_found').
        expose: If False, we’ll replace message with a generic one in responses.
    """

    http_status: int = 500
    code: str = "internal_error"
    expose: bool = False

    def __init__(
        self,
        message: str | None = None,
        *,
        details: Any | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message or self.default_message()
        self.details = details

    def default_message(self) -> str:
        return "An unexpected error occurred."

    def to_dict(self, *, request_id: str | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "type": self.__class__.__name__,
            "code": self.code,
            "message": self.message if self.expose else self.public_message(),
        }
        if request_id:
            payload["request_id"] = request_id
        if self.details is not None:
            payload["details"] = self.details
        return {"error": payload}

    def public_message(self) -> str:
        # Default public message for non-exposed errors
        if self.code == "internal_error":
            return "Something went wrong on our side."
        return self.message


# 4xx
class BadRequestError(AppError):
    http_status = 400
    code = "bad_request"
    expose = True

    def default_message(self) -> str:
        return "Your request is invalid."


class UnauthorizedError(AppError):
    http_status = 401
    code = "unauthorized"
    expose = True

    def default_message(self) -> str:
        return "You must be signed in."


class PermissionDeniedError(AppError):
    http_status = 403
    code = "permission_denied"
    expose = True

    def default_message(self) -> str:
        return "You do not have permission to perform this action."


class NotFoundError(AppError):
    http_status = 404
    code = "not_found"
    expose = True

    def default_message(self) -> str:
        return "The requested resource was not found."


class ConflictError(AppError):
    http_status = 409
    code = "conflict"
    expose = True

    def default_message(self) -> str:
        return "The request conflicts with current resource state."


class DuplicateError(ConflictError):
    code = "duplicate"
    expose = True

    def default_message(self) -> str:
        return "A resource with the same unique key already exists."


class PreconditionFailedError(AppError):
    http_status = 412
    code = "precondition_failed"
    expose = True

    def default_message(self) -> str:
        return "A required precondition failed."


class ValidationError(AppError):
    http_status = 422
    code = "validation_error"
    expose = True

    def default_message(self) -> str:
        return "One or more fields failed validation."


# 5xx
class RateLimitError(AppError):
    http_status = 429
    code = "rate_limited"
    expose = True

    def default_message(self) -> str:
        return "Too many requests. Please try again later."


class ExternalServiceError(AppError):
    http_status = 502
    code = "external_service_error"
    expose = False

    def default_message(self) -> str:
        return "Upstream service failed."


class DatabaseError(AppError):
    http_status = 503
    code = "database_error"
    expose = False

    def default_message(self) -> str:
        return "A database error occurred."
