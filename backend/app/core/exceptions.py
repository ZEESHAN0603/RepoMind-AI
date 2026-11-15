from typing import Any, Optional
from fastapi import status


class AppException(Exception):
    """Base application exception with status code and error details."""

    def __init__(
        self,
        message: str,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        code: str = "INTERNAL_SERVER_ERROR",
        details: Optional[Any] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code
        self.details = details


class BadRequestException(AppException):
    def __init__(self, message: str = "Bad request", details: Optional[Any] = None) -> None:
        super().__init__(
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            code="BAD_REQUEST",
            details=details,
        )


class UnauthorizedException(AppException):
    def __init__(self, message: str = "Could not validate credentials", details: Optional[Any] = None) -> None:
        super().__init__(
            message=message,
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="UNAUTHORIZED",
            details=details,
        )


class ForbiddenException(AppException):
    def __init__(self, message: str = "Access forbidden", details: Optional[Any] = None) -> None:
        super().__init__(
            message=message,
            status_code=status.HTTP_403_FORBIDDEN,
            code="FORBIDDEN",
            details=details,
        )


class NotFoundException(AppException):
    def __init__(self, message: str = "Resource not found", details: Optional[Any] = None) -> None:
        super().__init__(
            message=message,
            status_code=status.HTTP_404_NOT_FOUND,
            code="NOT_FOUND",
            details=details,
        )


class ConflictException(AppException):
    def __init__(self, message: str = "Resource conflict", details: Optional[Any] = None) -> None:
        super().__init__(
            message=message,
            status_code=status.HTTP_409_CONFLICT,
            code="CONFLICT",
            details=details,
        )


class ValidationException(AppException):
    def __init__(self, message: str = "Validation failed", details: Optional[Any] = None) -> None:
        super().__init__(
            message=message,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            code="VALIDATION_ERROR",
            details=details,
        )

