class DomainError(Exception):
    """A business-rule violation raised by services and rendered as a structured API error."""

    status_code = 400

    def __init__(self, message: str, code: str = "business_rule_violation", status_code=None):
        super().__init__(message)
        self.message = message
        self.code = code
        if status_code is not None:
            self.status_code = status_code


class PermissionDeniedError(DomainError):
    status_code = 403

    def __init__(self, message="You do not have permission to perform this action.", code="permission_denied"):
        super().__init__(message, code)


class LimitExceededError(DomainError):
    status_code = 403

    def __init__(self, message: str, code="plan_limit_exceeded"):
        super().__init__(message, code)
