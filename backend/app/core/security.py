import hashlib
import re
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.core.errors import AppError

_hasher = PasswordHasher()  # argon2-cffi default type is Argon2id
DUMMY_HASH = _hasher.hash("timing-equalisation-dummy")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(stored_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(stored_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def needs_rehash(stored_hash: str) -> bool:
    return _hasher.check_needs_rehash(stored_hash)


def generate_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def password_policy_errors(password: str) -> list[str]:
    errs = []
    if len(password) < 12:
        errs.append("Password must be at least 12 characters.")
    if len(password) > 128:
        errs.append("Password must be at most 128 characters.")
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        errs.append("Password must contain letters and digits.")
    return errs


def enforce_password_policy(password: str) -> None:
    errs = password_policy_errors(password)
    if errs:
        raise AppError(422, "weak_password", errs[0], {"errors": errs})
