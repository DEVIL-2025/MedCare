import bcrypt
import jwt
import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any

from backend.app.config import settings


class AuthService:
    """
    Production-grade Authentication and Password Security Service.
    Uses bcrypt for one-way hashing and PyJWT for signed HMAC-SHA256 session tokens.
    """

    @staticmethod
    def hash_password(password: str) -> str:
        """Hashes a plaintext password using bcrypt with automated salt generation."""
        pwd_bytes = password.encode('utf-8')
        salt = bcrypt.gensalt(rounds=12)
        return bcrypt.hashpw(pwd_bytes, salt).decode('utf-8')

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verifies a plaintext password against a stored bcrypt hash in constant time."""
        try:
            return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
        except Exception:
            return False

    @staticmethod
    def create_access_token(payload_data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
        """Creates a cryptographically signed JWT access token."""
        to_encode = payload_data.copy()
        now_utc = datetime.now(timezone.utc)
        if expires_delta:
            expire = now_utc + expires_delta
        else:
            expire = now_utc + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        
        to_encode.update({
            "exp": int(expire.timestamp()),
            "iat": int(now_utc.timestamp()),
            "iss": "MedCarePharmaControlTower"
        })
        encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
        return encoded_jwt

    @staticmethod
    def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
        """Decodes and validates a JWT token signature and expiration."""
        try:
            decoded = jwt.decode(
                token,
                settings.JWT_SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM],
                options={"verify_exp": True}
            )
            return decoded
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
            return None

    @staticmethod
    def generate_temporary_password(length: int = 12) -> str:
        """Generates a high-entropy temporary password containing uppercase, lowercase, digits, and symbols."""
        alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
        # Ensure at least one upper, lower, digit, and symbol
        pwd = [
            secrets.choice(string.ascii_uppercase),
            secrets.choice(string.ascii_lowercase),
            secrets.choice(string.digits),
            secrets.choice("!@#$%^&*")
        ]
        pwd += [secrets.choice(alphabet) for _ in range(length - 4)]
        secrets.SystemRandom().shuffle(pwd)
        return "".join(pwd)
