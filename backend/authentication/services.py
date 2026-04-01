import logging

from django.conf import settings
from django.core.signing import TimestampSigner

logger = logging.getLogger(__name__)


def generate_verification_token(email):
    signer = TimestampSigner()
    return signer.sign(email)


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
