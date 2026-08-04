import base64

from app.core.config import settings


def encrypt_secret(value: str) -> str:
    if not value:
        return ""
    salt = settings.secret_key.encode("utf-8")
    raw = value.encode("utf-8")
    mixed = bytes(raw[i] ^ salt[i % len(salt)] for i in range(len(raw)))
    return base64.urlsafe_b64encode(mixed).decode("ascii")


def decrypt_secret(value: str) -> str:
    if not value:
        return ""
    salt = settings.secret_key.encode("utf-8")
    raw = base64.urlsafe_b64decode(value.encode("ascii"))
    plain = bytes(raw[i] ^ salt[i % len(salt)] for i in range(len(raw)))
    return plain.decode("utf-8")


def mask_secret(value: str) -> str:
    if not value:
        return ""
    plain = decrypt_secret(value)
    if len(plain) <= 8:
        return "****"
    return f"{plain[:4]}****{plain[-4:]}"

