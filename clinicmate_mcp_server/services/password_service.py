# password_service.py
# Hashes and checks passwords with scrypt (Python standard library). Only the hash is stored, never the password.

import hashlib
import hmac
import secrets

# scrypt settings: slow on purpose, so guessing passwords from a stolen hash takes very long
SCRYPT_N = 2 ** 14
SCRYPT_R = 8
SCRYPT_P = 1


def make_digest(password: str, salt: bytes) -> bytes:
    return hashlib.scrypt(password.encode("utf-8"), salt=salt, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P)


def hash_password(password: str) -> str:
    """'scrypt$<salt>$<hash>'. A new random salt each time, so two equal passwords get different hashes."""
    salt = secrets.token_bytes(16)
    return f"scrypt${salt.hex()}${make_digest(password, salt).hex()}"


def check_password(password: str, stored_hash: str | None) -> bool:
    if not stored_hash:
        return False
    try:
        _, salt_hex, digest_hex = stored_hash.split("$")
    except ValueError:
        return False
    digest = make_digest(password, bytes.fromhex(salt_hex))
    # compare_digest takes the same time for every wrong password, so timing gives nothing away
    return hmac.compare_digest(digest.hex(), digest_hex)