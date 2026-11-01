"""Password hashing - identical format to app/auth.py so MySQL, MongoDB and the UI share one users.csv:
pbkdf2_sha256$<iterations>$<salt hex>$<digest hex>   (salt is hex-decoded before hashing)."""
import hashlib
import hmac
import secrets

ALGORITHM = "pbkdf2_sha256"
ITERATIONS = 200_000


def hash_password(password: str, salt: str = None, iterations: int = ITERATIONS) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), iterations)
    return f"{ALGORITHM}${iterations}${salt}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, iterations, salt, _ = stored.split("$")
    except (AttributeError, ValueError):
        return False
    if algorithm != ALGORITHM:
        return False
    return hmac.compare_digest(hash_password(password, salt, int(iterations)), stored)
