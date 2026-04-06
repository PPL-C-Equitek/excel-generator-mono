import logging
import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from google.auth.transport import requests
from google.oauth2 import id_token

from authentication.models import User
from authentication.services import generate_tokens

logger = logging.getLogger(__name__)


class GoogleOAuthService:
    def __init__(self, google_client_id: str):
        self.google_client_id = google_client_id

    def _fetch_json(self, url: str, headers: dict | None = None) -> dict:
        request = Request(url, headers=headers or {})

        try:
            with urlopen(request, timeout=10) as response:
                body = response.read().decode("utf-8")
                return json.loads(body)
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            logger.error("Failed to fetch Google OAuth endpoint: %s", exc)
            raise ValueError("Invalid Google token") from exc

    def _verify_id_token(self, token: str) -> dict:
        idinfo = id_token.verify_oauth2_token(
            token,
            requests.Request(),
            self.google_client_id,
        )

        return {
            "email": idinfo.get("email"),
            "name": idinfo.get("name"),
            "picture": idinfo.get("picture"),
        }

    def _verify_access_token(self, token: str) -> dict:
        token_info_url = (
            "https://www.googleapis.com/oauth2/v3/tokeninfo?"
            + urlencode({"access_token": token})
        )
        token_info = self._fetch_json(token_info_url)

        audience = token_info.get("aud")
        authorized_party = token_info.get("azp")
        if audience != self.google_client_id and authorized_party != self.google_client_id:
            raise ValueError("Google token audience mismatch")

        user_info = self._fetch_json(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={"Authorization": f"Bearer {token}"},
        )

        email = user_info.get("email")
        if not email:
            raise ValueError("Google account email not available")

        return {
            "email": email,
            "name": user_info.get("name"),
            "picture": user_info.get("picture"),
        }

    def verify_token(self, token: str) -> dict:
        try:
            if token.count(".") == 2:
                return self._verify_id_token(token)

            return self._verify_access_token(token)
        except ValueError as e:
            logger.error(f"Invalid Google token: {e}")
            raise ValueError("Invalid Google token") from e
    
    def authenticate_or_create_user(self, token: str) -> dict:
        user_info = self.verify_token(token)
        email = user_info["email"].lower().strip()
        google_name = user_info.get("name")
        if not isinstance(google_name, str) or not google_name.strip():
            google_name = email.split("@")[0]
        else:
            google_name = google_name.strip()
        
        # Get or create user
        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                "name": google_name,
                "status": "verified",
            }
        )
        
        # Update name jika user sudah ada tapi name berbeda
        if not created and user.name != google_name:
            user.name = google_name
            user.save(update_fields=["name"])
        
        # Mark as verified jika belum
        if user.status != "verified":
            user.status = "verified"
            user.save(update_fields=["status"])
        
        # Generate JWT tokens
        tokens = generate_tokens(user.id, user.email)
        
        return {
            "user": user,
            "tokens": tokens,
        }