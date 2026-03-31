import logging
import json
from datetime import timedelta
from django.conf import settings
from django.core.signing import TimestampSigner
logger = logging.getLogger(__name__)
from django.utils import timezone


def generate_verification_token(email):
    signer = TimestampSigner()
    return signer.sign(email)


def generate_tokens(user_id, email):
    """Generate access and refresh tokens for the user"""
    signer = TimestampSigner()
    
    # Create Access Token with 1 hour expiration
    access_payload = {
        "user_id": str(user_id),
        "email": email,
        "type": "access",
        "exp": timezone.now() + timedelta(hours=1),
    }
    access_token = signer.sign(json.dumps(access_payload))
    
    # Create Refresh Token with 7 days expiration
    refresh_payload = {
        "user_id": str(user_id),
        "email": email,
        "type": "refresh",
        "exp": timezone.now() + timedelta(days=7),
    }
    refresh_token = signer.sign(json.dumps(refresh_payload))
    
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
