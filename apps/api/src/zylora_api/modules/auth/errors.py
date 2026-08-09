from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AuthProblem(Exception):
    status_code: int
    code: str
    title: str
    detail: str
    retry_after_seconds: int | None = None


INVALID_CREDENTIALS = AuthProblem(
    401, "invalid_credentials", "Authentication failed", "Email or password is incorrect."
)
AUTHENTICATION_REQUIRED = AuthProblem(
    401, "authentication_required", "Authentication required", "Sign in to continue."
)
FORBIDDEN = AuthProblem(403, "forbidden", "Access denied", "You cannot access this resource.")
CSRF_REJECTED = AuthProblem(
    403, "csrf_rejected", "Request rejected", "The request could not be verified."
)
VERIFICATION_INVALID = AuthProblem(
    400,
    "verification_invalid",
    "Verification failed",
    "The verification code is invalid or expired.",
)
RESET_INVALID = AuthProblem(
    400, "reset_invalid", "Reset failed", "The reset link is invalid or expired."
)
ACCOUNT_UNAVAILABLE = AuthProblem(
    403, "account_unavailable", "Account unavailable", "This account cannot sign in."
)
RATE_LIMITED = AuthProblem(
    429, "rate_limited", "Try again later", "Too many attempts. Wait before trying again."
)
OAUTH_INVALID = AuthProblem(
    400, "oauth_invalid", "Google sign-in failed", "The Google sign-in response was invalid."
)
OAUTH_UNAVAILABLE = AuthProblem(
    503,
    "oauth_unavailable",
    "Google sign-in unavailable",
    "Google sign-in is temporarily unavailable.",
)
DELIVERY_UNAVAILABLE = AuthProblem(
    503,
    "delivery_unavailable",
    "Email delivery unavailable",
    "Email delivery is temporarily unavailable.",
)


def rate_limited(retry_after_seconds: int) -> AuthProblem:
    return AuthProblem(
        429,
        "rate_limited",
        "Try again later",
        f"Too many attempts. Try again in {retry_after_seconds} seconds.",
        retry_after_seconds,
    )


CHALLENGE_REQUIRED = AuthProblem(
    400,
    "challenge_required",
    "Security verification required",
    "Complete the security check and try again.",
)
CHALLENGE_FAILED = AuthProblem(
    400,
    "challenge_failed",
    "Security verification failed",
    "The security check expired or could not be verified. Please try again.",
)
CHALLENGE_UNAVAILABLE = AuthProblem(
    503,
    "challenge_unavailable",
    "Security verification unavailable",
    "Security verification is temporarily unavailable. Please try again later.",
)
