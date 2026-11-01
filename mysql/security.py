"""PBKDF2 format shared with app/auth.py; independent of the application import path."""
import hashlib
import hmac
import secrets


def hash_password(password, salt=None, iterations=200_000):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), iterations)
    return f"pbkdf2_sha256${iterations}${salt}${digest.hex()}"


def verify_password(password, stored):
    try:
        algorithm, iterations, salt, _ = stored.split("$")
        return algorithm == "pbkdf2_sha256" and hmac.compare_digest(
            hash_password(password, salt, int(iterations)), stored)
    except (AttributeError, TypeError, ValueError, OverflowError):
        return False
