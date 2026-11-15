import base64
import hashlib
from typing import Optional
from cryptography.fernet import Fernet
from app.core.config import settings


def _get_fernet_key() -> bytes:
    """Derives or returns a valid 32-byte URL-safe base64 key for Fernet symmetric encryption."""
    custom_key = settings.GITHUB_TOKEN_ENCRYPTION_KEY.strip()
    if custom_key:
        try:
            # Validate if it's already a valid Fernet key
            Fernet(custom_key.encode())
            return custom_key.encode()
        except Exception:
            # If not valid Fernet format, hash it to 32 bytes and base64-encode
            hashed = hashlib.sha256(custom_key.encode()).digest()
            return base64.urlsafe_b64encode(hashed)
    else:
        # Deterministically derive 32-byte key from JWT_SECRET
        hashed = hashlib.sha256(settings.JWT_SECRET.encode()).digest()
        return base64.urlsafe_b64encode(hashed)


def encrypt_secret(plain_text: str) -> str:
    """Encrypts plaintext string into an authenticated Fernet ciphertext."""
    if not plain_text:
        return ""
    f = Fernet(_get_fernet_key())
    encrypted = f.encrypt(plain_text.encode("utf-8"))
    return encrypted.decode("utf-8")


def decrypt_secret(cipher_text: str) -> Optional[str]:
    """Decrypts ciphertext string back into plaintext. Returns None if decryption fails."""
    if not cipher_text:
        return None
    try:
        f = Fernet(_get_fernet_key())
        decrypted = f.decrypt(cipher_text.encode("utf-8"))
        return decrypted.decode("utf-8")
    except Exception:
        return None

