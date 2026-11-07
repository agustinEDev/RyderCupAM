"""User Domain Exceptions."""

from .account_deactivated_exception import AccountDeactivatedException
from .account_locked_exception import AccountLockedException
from .current_device_revocation_exception import CurrentDeviceRevocationException
from .email_change_exceptions import (
    EmailChangeEmailInUseError,
    EmailChangeExpiredError,
    EmailChangeInvalidError,
)
from .login_attempts_exceeded_exception import LoginAttemptsExceededException
from .user_has_activity_exception import UserHasActivityException

__all__ = [
    "AccountDeactivatedException",
    "AccountLockedException",
    "CurrentDeviceRevocationException",
    "EmailChangeEmailInUseError",
    "EmailChangeExpiredError",
    "EmailChangeInvalidError",
    "LoginAttemptsExceededException",
    "UserHasActivityException",
]
