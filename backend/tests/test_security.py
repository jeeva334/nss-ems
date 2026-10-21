from app.core.security import (generate_token, hash_password, hash_token,
                               password_policy_errors, verify_password)


def test_argon2id_hash_and_verify():
    h = hash_password("CorrectHorse42Battery")
    assert h.startswith("$argon2id$") and "CorrectHorse" not in h
    assert verify_password(h, "CorrectHorse42Battery")
    assert not verify_password(h, "wrong")
    assert not verify_password("not-a-hash", "x")


def test_tokens_unique_and_hashed():
    a, b = generate_token(), generate_token()
    assert a != b and len(a) >= 40
    assert hash_token(a) != a and len(hash_token(a)) == 64


def test_password_policy():
    assert password_policy_errors("short1")
    assert password_policy_errors("onlyletterslongenough")
    assert not password_policy_errors("ValidPassword123")
