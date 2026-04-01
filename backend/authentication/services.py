import logging
import jwt
from datetime import timedelta
from urllib.parse import quote

from dataclasses import dataclass
from typing import Any, Callable, Protocol, TypedDict
from django.conf import settings
from django.core.cache import cache
from django.core.signing import TimestampSigner
from django.utils import timezone

from authentication.models import User

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TokenPair:
    accessToken: str
    refreshToken: str


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


class UserLookupGateway(Protocol):
    def get_by_email(self, email: str) -> User:
        ...


class DjangoUserLookupGateway:
    def get_by_email(self, email: str) -> User:
        return User.objects.get(email=email)


class TokenPayload(TypedDict):
    accessToken: str
    refreshToken: str


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


def generate_verification_token(email):
    signer = TimestampSigner()
    return signer.sign(email)


def generate_tokens(user_id, email) -> TokenPayload:
    secret_key = getattr(settings, "JWT_SECRET_KEY", None)
    if not secret_key:
        raise ValueError("JWT_SECRET_KEY is not configured")

    now = timezone.now()

    access_payload = {
        "user_id": str(user_id),
        "email": email,
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=1)).timestamp()),
        "iss": "excel-generator",
    }

    access_token = jwt.encode(access_payload, secret_key, algorithm="HS256")

    refresh_payload = {
        "user_id": str(user_id),
        "email": email,
        "type": "refresh",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(days=7)).timestamp()),
    }

    refresh_token = jwt.encode(refresh_payload, secret_key, algorithm="HS256")

    return {
        "accessToken": access_token,
        "refreshToken": refresh_token,
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
            self.failure_tracker.record_failure(normalized_email)
            raise InvalidCredentialsError() from exc

        if not user.check_password(password):
            self.failure_tracker.record_failure(normalized_email)
            raise InvalidCredentialsError()

        if user.status != "verified":
            self.failure_tracker.record_failure(normalized_email)
            raise EmailNotVerifiedError()

        token_data = self.token_generator(user.id, user.email)
        self.failure_tracker.reset_failures(normalized_email)

        tokens = TokenPair(
            accessToken=token_data["accessToken"],
            refreshToken=token_data["refreshToken"],
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

    def __init__(self, token_generator: Callable[[object, str], TokenPayload] = generate_tokens):
        self.token_generator = token_generator

    def refresh(self, refresh_token: str) -> TokenPayload:
        payload = self._decode_refresh_token(refresh_token)

        if payload.get("type") != "refresh":
            raise InvalidRefreshTokenError("Invalid token type.")

        user_id = payload.get("user_id")
        email = payload.get("email")
        if not user_id or not email:
            raise InvalidRefreshTokenError("Invalid token payload.")

        return self.token_generator(user_id, email)

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
    token = generate_verification_token(email)
    frontend_url = getattr(settings, "FRONTEND_URL", "http://localhost:3000")
    verification_url = f"{frontend_url}/auth/verify-email?token={quote(token, safe='')}"

    try:
        resend_api_key = getattr(settings, "RESEND_API_KEY", "")
        if resend_api_key:
            import resend
            resend.api_key = resend_api_key
            resend.Emails.send({
                "from": getattr(settings, "RESEND_FROM_EMAIL", "noreply@excelprojectequitek.my.id"),
                "to": email,
                "subject": "Verify Your Email",
                "html": f'<p>Click the link below to verify: <a href="{verification_url}">{verification_url}</a></p>',
            })
        else:
            print(f"\n--- VERIFICATION LINK ---\n{verification_url}\n-------------------------\n")
    except Exception:
        logger.exception("Failed to send verification email to %s", email)
        raise
