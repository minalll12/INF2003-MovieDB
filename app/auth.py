import hashlib
import hmac
import secrets

ALGORITHM = "pbkdf2_sha256"
ITERATIONS = 200_000


def hash_password(password, salt=None, iterations=ITERATIONS):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), iterations)
    return f"{ALGORITHM}${iterations}${salt}${digest.hex()}"


def verify_password(password, stored):
    try:
        algorithm, iterations, salt, _ = stored.split("$")
    except (AttributeError, ValueError):
        return False
    if algorithm != ALGORITHM:
        return False
    candidate = hash_password(password, salt, int(iterations))
    return hmac.compare_digest(candidate, stored)
