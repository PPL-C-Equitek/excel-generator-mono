import logging
import json
import jwt
from datetime import timedelta
from django.conf import settings
from django.core.signing import TimestampSigner
logger = logging.getLogger(__name__)
from django.utils import timezone


def generate_verification_token(email):
    signer = TimestampSigner()
    return signer.sign(email)


def generate_tokens(user_id, email):
    secret_key = settings.SECRET_KEY
    now = timezone.now()

    # Access Token — expires in 1 hour
    access_payload = {
        "user_id": str(user_id),
        "email": email,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(hours=1),
        "iss": "excel-generator",
    }
    access_token = jwt.encode(access_payload, secret_key, algorithm="HS256")

    # Refresh Token — expires in 7 days
    refresh_payload = {
        "user_id": str(user_id),
        "email": email,
        "type": "refresh",
        "iat": now,
        "exp": now + timedelta(days=7),
    }
    refresh_token = jwt.encode(refresh_payload, secret_key, algorithm="HS256")

    return {
        "accessToken": access_token,
        "refreshToken": refresh_token,
    }


def send_verification_email(email):
    token = generate_verification_token(email)
    frontend_url = getattr(settings, "FRONTEND_URL", "http://localhost:3000")
    verification_url = f"{frontend_url}/auth/verify-email?token={token}"

    try:
        resend_api_key = getattr(settings, "RESEND_API_KEY", "")
        if resend_api_key:
            import resend
            resend.api_key = resend_api_key
            resend.Emails.send({
                "from": getattr(settings, "RESEND_FROM_EMAIL", "noreply@example.com"),
                "to": email,
                "subject": "Verifikasi Email Anda",
                "html": f'<p>Klik link berikut untuk verifikasi: <a href="{verification_url}">{verification_url}</a></p>',
            })
        else:
            print(f"\n--- VERIFICATION LINK ---\n{verification_url}\n-------------------------\n")
    except Exception:
        logger.exception("Failed to send verification email to %s", email)
        raise
