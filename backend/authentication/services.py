import logging
import jwt
import uuid
from datetime import timedelta
from types import SimpleNamespace
from urllib.parse import quote

from dataclasses import dataclass
from typing import Any, Callable, Protocol, TypedDict
from django.conf import settings
from django.core.cache import cache
from django.core.signing import BadSignature, TimestampSigner
from django.utils import timezone

from authentication.models import User
from authentication.logout.adapters import DjangoTokenBlacklistRepository
from authentication.logout.contracts import TokenBlacklistPort
from authentication.serializers import TokenObtainPairSerializer

logger = logging.getLogger(__name__)
PASSWORD_RESET_TOKEN_PREFIX = "password-reset"
PASSWORD_RESET_SUCCESS_MESSAGE = (
    "If the email exists, we sent a reset link."
)
PASSWORD_RESET_RESEND_SUCCESS_MESSAGE = (
    "If the email exists, we sent a new reset link."
)
RESEND_FROM_EMAIL_NOT_CONFIGURED_MESSAGE = "RESEND_FROM_EMAIL is not configured."


@dataclass(frozen=True)
class TokenPair:
    access_token: str
    refresh_token: str


@dataclass(frozen=True)
class AuthenticatedUserDTO:
    id: str
    email: str
    name: str


@dataclass(frozen=True)
class LoginResult:
    tokens: TokenPair
    user: AuthenticatedUserDTO


class AuthenticationError(Exception):
    """Base class for authentication domain errors."""


class LoginRateLimitedError(AuthenticationError):
    pass


class InvalidCredentialsError(AuthenticationError):
    pass


class EmailNotVerifiedError(AuthenticationError):
    pass


class RefreshTokenError(AuthenticationError):
    pass


class RefreshTokenExpiredError(RefreshTokenError):
    pass


class InvalidRefreshTokenError(RefreshTokenError):
    pass


class BlacklistedRefreshTokenError(RefreshTokenError):
    pass


class UserLookupGateway(Protocol):
    def get_by_email(self, email: str) -> User:
        ...


class DjangoUserLookupGateway:
    def get_by_email(self, email: str) -> User:
        return User.objects.get(email=email)


class TokenPayload(TypedDict):
    access_token: str
    refresh_token: str


class FailureTrackerProtocol(Protocol):
    @classmethod
    def is_rate_limited(cls, email: str) -> bool:
        ...

    @classmethod
    def record_failure(cls, email: str) -> int:
        ...

    @classmethod
    def reset_failures(cls, email: str):
        ...


def _get_resend_from_email() -> str:
    from_email = getattr(settings, "RESEND_FROM_EMAIL", "")
    if not isinstance(from_email, str):
        return ""
    return from_email.strip()


def _require_resend_from_email() -> str:
    from_email = _get_resend_from_email()
    if not from_email:
        raise ValueError(RESEND_FROM_EMAIL_NOT_CONFIGURED_MESSAGE)
    return from_email


EMAIL_VERIFICATION_TOKEN_PREFIX = "email-verify"


def generate_verification_token(email, nonce):
    signer = TimestampSigner()
    return signer.sign(f"{EMAIL_VERIFICATION_TOKEN_PREFIX}:{email}:{nonce}")


def decode_verification_token(token, max_age):
    signer = TimestampSigner()
    value = signer.unsign(token, max_age=max_age)
    prefix = f"{EMAIL_VERIFICATION_TOKEN_PREFIX}:"
    if not isinstance(value, str) or not value.startswith(prefix):
        raise BadSignature("Invalid token purpose.")

    payload = value[len(prefix):]
    email, separator, nonce = payload.rpartition(":")
    if not separator or not email or not nonce:
        raise BadSignature("Invalid token payload.")

    return email, nonce


def generate_password_reset_token(email):
    signer = TimestampSigner()
    return signer.sign(f"{PASSWORD_RESET_TOKEN_PREFIX}:{email}")


def decode_password_reset_token(token, max_age):
    signer = TimestampSigner()
    value = signer.unsign(token, max_age=max_age)
    prefix = f"{PASSWORD_RESET_TOKEN_PREFIX}:"
    if not isinstance(value, str) or not value.startswith(prefix):
        raise ValueError("Invalid token purpose.")
    return value[len(prefix):]


def generate_tokens(user_id, email, session_version: int = 1) -> TokenPayload:
    secret_key = getattr(settings, "JWT_SECRET_KEY", None)
    if not secret_key:
        raise ValueError("JWT_SECRET_KEY is not configured")

    now = timezone.now()
    now_ts = int(now.timestamp())

    token_user = SimpleNamespace(
        id=str(user_id),
        email=email,
        session_version=session_version,
    )

    access_payload = TokenObtainPairSerializer.build_access_payload(
        user=token_user,
        now_timestamp=now_ts,
        exp_timestamp=int((now + timedelta(hours=1)).timestamp()),
    )

    access_token = jwt.encode(access_payload, secret_key, algorithm="HS256")

    refresh_payload = TokenObtainPairSerializer.build_refresh_payload(
        user=token_user,
        now_timestamp=now_ts,
        exp_timestamp=int((now + timedelta(days=7)).timestamp()),
    )

    refresh_token = jwt.encode(refresh_payload, secret_key, algorithm="HS256")

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
    }


class LoginFailureTracker:
    """Track failed login attempts for rate limiting (5 attempts per 15 minutes)."""

    FAILURE_LIMIT = 5
    TIME_WINDOW = 15 * 60

    @staticmethod
    def get_cache_key(email: str) -> str:
        return f"login_failures:{email.lower().strip()}"

    @classmethod
    def get_cache_backend(cls) -> Any:
        return cache

    @classmethod
    def is_rate_limited(cls, email: str) -> bool:
        cache_key = cls.get_cache_key(email)
        cache_backend = cls.get_cache_backend()
        failures = cache_backend.get(cache_key, 0)
        return failures >= cls.FAILURE_LIMIT

    @classmethod
    def record_failure(cls, email: str) -> int:
        cache_key = cls.get_cache_key(email)
        cache_backend = cls.get_cache_backend()
        cache_backend.add(cache_key, 0, cls.TIME_WINDOW)

        try:
            return cache_backend.incr(cache_key)
        except ValueError:
            cache_backend.set(cache_key, 1, cls.TIME_WINDOW)
            return 1

    @classmethod
    def reset_failures(cls, email: str) -> None:
        cache_key = cls.get_cache_key(email)
        cache_backend = cls.get_cache_backend()
        cache_backend.delete(cache_key)


class LoginService:
    """Authenticate users with business rules isolated from the transport layer."""

    def __init__(
        self,
        user_gateway: UserLookupGateway | None = None,
        failure_tracker: type[FailureTrackerProtocol] = LoginFailureTracker,
        token_generator: Callable[[object, str], TokenPayload] = generate_tokens,
    ):
        self.user_gateway = user_gateway or DjangoUserLookupGateway()
        self.failure_tracker = failure_tracker
        self.token_generator = token_generator

    @staticmethod
    def normalize_email(email: str) -> str:
        return email.lower().strip()

    def authenticate(self, email: str, password: str) -> LoginResult:
        normalized_email = self.normalize_email(email)

        if self.failure_tracker.is_rate_limited(normalized_email):
            raise LoginRateLimitedError()

        try:
            user = self.user_gateway.get_by_email(normalized_email)
        except User.DoesNotExist as exc:
            logger.warning("Login failed for %s: user not found.", normalized_email)
            self.failure_tracker.record_failure(normalized_email)
            raise InvalidCredentialsError() from exc
        
        if user.status != "verified":
            logger.warning("Login failed for %s: email not verified.", normalized_email)
            self.failure_tracker.record_failure(normalized_email)
            raise EmailNotVerifiedError()

        if not user.check_password(password):
            logger.warning("Login failed for %s: incorrect password.", normalized_email)
            self.failure_tracker.record_failure(normalized_email)
            raise InvalidCredentialsError()

        token_data = self.token_generator(user.id, user.email, user.session_version)
        self.failure_tracker.reset_failures(normalized_email)

        tokens = TokenPair(
            access_token=token_data["access_token"],
            refresh_token=token_data["refresh_token"],
        )
        user_data = AuthenticatedUserDTO(
            id=str(user.id),
            email=user.email,
            name=user.name,
        )
        return LoginResult(tokens=tokens, user=user_data)


class RefreshTokenService:
    """Issue a new JWT pair from a valid refresh token."""

    algorithms = ["HS256"]

    def __init__(
        self,
        token_generator: Callable[[object, str], TokenPayload] = generate_tokens,
        token_blacklist_port: TokenBlacklistPort | None = None,
    ):
        self.token_generator = token_generator
        self.token_blacklist_port = token_blacklist_port or DjangoTokenBlacklistRepository()

    def refresh(self, refresh_token: str) -> TokenPayload:
        payload = self._decode_refresh_token(refresh_token)

        if payload.get("type") != "refresh":
            raise InvalidRefreshTokenError("Invalid token type.")

        user_id = payload.get("user_id")
        email = payload.get("email")
        if not user_id or not email:
            raise InvalidRefreshTokenError("Invalid token payload.")

        if self.token_blacklist_port and self.token_blacklist_port.is_blacklisted(refresh_token):
            raise BlacklistedRefreshTokenError("Refresh token is blacklisted.")

        # Ensure the refresh token still belongs to an existing verified user.
        user = User.objects.filter(
            id=user_id,
            email=email,
            status="verified",
        ).first()
        if user is None:
            raise InvalidRefreshTokenError("User is not valid for refresh.")

        return self.token_generator(user_id, email, user.session_version)

    def _decode_refresh_token(self, refresh_token: str):
        secret_key = getattr(settings, "JWT_SECRET_KEY", "")
        if not secret_key:
            raise InvalidRefreshTokenError("JWT secret is not configured.")

        try:
            return jwt.decode(refresh_token, secret_key, algorithms=self.algorithms)
        except jwt.ExpiredSignatureError as exc:
            raise RefreshTokenExpiredError("Token has expired.") from exc
        except jwt.InvalidTokenError as exc:
            raise InvalidRefreshTokenError("Invalid token.") from exc


def send_verification_email(email):
    user = User.objects.get(email=email)
    previous_nonce = user.email_verification_nonce
    user.email_verification_nonce = uuid.uuid4()
    user.save(update_fields=["email_verification_nonce"])

    token = generate_verification_token(user.email, str(user.email_verification_nonce))
    frontend_url = getattr(settings, "FRONTEND_URL", "http://localhost:3000")
    verification_url = f"{frontend_url}/auth/verify-email?token={quote(token, safe='')}"

    try:
        resend_api_key = getattr(settings, "RESEND_API_KEY", "")
        if resend_api_key:
            from_email = _require_resend_from_email()
            import resend
            resend.api_key = resend_api_key
            resend.Emails.send({
                "from": from_email,
                "to": user.email,
                "subject": "Verify Your Email",
                "html": f'<p>Click the link below to verify: <a href="{verification_url}">{verification_url}</a></p>',
            })
        else:
            logger.info("Verification link (RESEND_API_KEY not set): %s", verification_url)
    except Exception as exc:
        user.email_verification_nonce = previous_nonce
        user.save(update_fields=["email_verification_nonce"])
        logger.exception("Failed to send verification email to %s", user.email)
        raise exc


def send_password_reset_email(email):
    token = generate_password_reset_token(email)
    frontend_url = getattr(settings, "FRONTEND_URL", "http://localhost:3000")
    reset_url = f"{frontend_url}/auth/reset-password?token={quote(token, safe='')}"
    try:
        resend_api_key = getattr(settings, "RESEND_API_KEY", "")
        if resend_api_key:
            from_email = _require_resend_from_email()
            import resend

            resend.api_key = resend_api_key
            resend.Emails.send(
                {
                    "from": from_email,
                    "to": email,
                    "subject": "Reset Your Password",
                    "html": f'<p>Click the link below to reset your password: <a href="{reset_url}">{reset_url}</a></p>',
                }
            )
        else:
            logger.info(
                "Password reset requested for %s (RESEND_API_KEY not set; reset link not logged)",
                email,
            )
    except Exception:
        logger.exception("Failed to send password reset email to %s", email)
        raise


def send_password_changed_email(email):
    try:
        resend_api_key = getattr(settings, "RESEND_API_KEY", "")
        if resend_api_key:
            from_email = _require_resend_from_email()
            import resend

            resend.api_key = resend_api_key
            resend.Emails.send(
                {
                    "from": from_email,
                    "to": email,
                    "subject": "Your Password Was Changed",
                    "html": (
                        "<p>Your account password was changed successfully.</p>"
                        "<p>If this was not you, please contact support immediately.</p>"
                    ),
                }
            )
        else:
            logger.info(
                "Password changed notification (RESEND_API_KEY not set) for %s",
                email,
            )
    except Exception:
        logger.exception("Failed to send password changed email to %s", email)
        raise
