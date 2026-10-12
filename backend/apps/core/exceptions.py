from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import Http404
from rest_framework import exceptions, status
from rest_framework.serializers import as_serializer_error
from rest_framework.views import exception_handler

from .request_context import get_request_id


class ApplicationError(exceptions.APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "The request could not be completed."
    default_code = "application_error"


class BusinessRuleViolation(ApplicationError):
    default_detail = "The request violates a business rule."
    default_code = "business_rule_violation"


class ConflictError(ApplicationError):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "The request conflicts with the current state."
    default_code = "conflict"


class OrganizationRequired(ApplicationError):
    default_detail = "Select an organization using the X-Organization-ID header."
    default_code = "organization_required"


class OrganizationUnavailable(ApplicationError):
    # Same response for unknown, foreign and inaccessible organizations so existence never leaks.
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = "The selected organization is not available."
    default_code = "organization_unavailable"


class SubscriptionInactive(ApplicationError):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = "The organization's subscription is not active."
    default_code = "subscription_inactive"


class FeatureNotAvailable(ApplicationError):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = "This feature is not included in the organization's plan."
    default_code = "feature_not_available"


class PlanLimitReached(ApplicationError):
    status_code = status.HTTP_403_FORBIDDEN
    default_detail = "The organization's plan limit has been reached."
    default_code = "plan_limit_reached"


def _error_code(exc: exceptions.APIException, data) -> str:
    if isinstance(data, dict) and isinstance(data.get("code"), str):
        return data["code"]
    codes = exc.get_codes()
    if isinstance(codes, str):
        return codes
    if isinstance(codes, dict) and isinstance(codes.get("detail"), str):
        return codes["detail"]
    return exc.default_code


def api_exception_handler(exc, context):
    if isinstance(exc, DjangoValidationError):
        exc = exceptions.ValidationError(detail=as_serializer_error(exc))
    elif isinstance(exc, Http404):
        exc = exceptions.NotFound()
    elif isinstance(exc, DjangoPermissionDenied):
        exc = exceptions.PermissionDenied()

    response = exception_handler(exc, context)
    if response is None:
        return None

    data = response.data
    if isinstance(exc, exceptions.ValidationError):
        error = {
            "code": "validation_error",
            "message": "Some fields are invalid.",
            "details": data,
        }
    else:
        message = data.get("detail") if isinstance(data, dict) else None
        error = {
            "code": _error_code(exc, data),
            "message": str(message or exc.default_detail),
        }
    error["request_id"] = get_request_id()
    response.data = {"error": error}
    return response
