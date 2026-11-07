from datetime import timedelta

import pytest

from app.core.security import (
    TokenSecurityError,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)

# Isolated test secret (not exposing or relying on environment production secrets)
TEST_SECRET_KEY = "test-isolated-dummy-secret-key-for-testing-12345678"


def test_password_hashing_returns_different_string():
    """Verify password hashing returns a non-empty hash distinct from plaintext."""
    raw_password = "SecureTestingPassword123!"
    hashed = hash_password(raw_password)

    assert hashed != raw_password
    assert len(hashed) > 20
    assert hashed.startswith("$argon2id$")


def test_password_verification_success():
    """Verify correct plaintext password successfully matches the Argon2 hash."""
    raw_password = "CorrectHorseBatteryStaple!"
    hashed = hash_password(raw_password)

    assert verify_password(raw_password, hashed) is True


def test_password_verification_failure():
    """Verify incorrect passwords fail verification safely."""
    raw_password = "CorrectPassword123!"
    hashed = hash_password(raw_password)

    assert verify_password("IncorrectPassword456!", hashed) is False
    assert verify_password("", hashed) is False
    assert verify_password(raw_password, "") is False


def test_password_hashes_are_salted():
    """Verify unique cryptographic salts produce different hashes for identical passwords."""
    password = "IdenticalPassword789!"
    hash1 = hash_password(password)
    hash2 = hash_password(password)

    assert hash1 != hash2
    assert verify_password(password, hash1) is True
    assert verify_password(password, hash2) is True


def test_create_and_decode_valid_access_token():
    """Verify generating and decoding a valid JWT access token."""
    user_id = 101
    token = create_access_token(user_id=user_id, secret_key=TEST_SECRET_KEY)

    decoded = decode_access_token(token, secret_key=TEST_SECRET_KEY)
    assert decoded["sub"] == "101"
    assert "iat" in decoded
    assert "exp" in decoded
    assert decoded["exp"] > decoded["iat"]


def test_token_contains_string_subject():
    """Verify the subject claim (sub) is always a string matching user ID."""
    user_id = 999
    token = create_access_token(user_id=user_id, secret_key=TEST_SECRET_KEY)

    decoded = decode_access_token(token, secret_key=TEST_SECRET_KEY)
    assert isinstance(decoded["sub"], str)
    assert decoded["sub"] == str(user_id)


def test_expired_token_is_rejected():
    """Verify tokens past their expiration timestamp are rejected."""
    user_id = 42
    expired_token = create_access_token(
        user_id=user_id,
        expires_delta=timedelta(seconds=-10),
        secret_key=TEST_SECRET_KEY,
    )

    with pytest.raises(TokenSecurityError, match="expired"):
        decode_access_token(expired_token, secret_key=TEST_SECRET_KEY)


def test_tampered_token_is_rejected():
    """Verify corrupted tokens or tokens signed with mismatched keys are rejected."""
    user_id = 77
    token = create_access_token(user_id=user_id, secret_key=TEST_SECRET_KEY)

    # Corrupted signature string
    tampered_token = token[:-4] + "abcd"
    with pytest.raises(TokenSecurityError):
        decode_access_token(tampered_token, secret_key=TEST_SECRET_KEY)

    # Token decoded with wrong key
    wrong_key = "different-test-secret-key-that-does-not-match-12345"
    with pytest.raises(TokenSecurityError):
        decode_access_token(token, secret_key=wrong_key)


def test_missing_required_claims_rejected():
    """Verify tokens missing sub, iat, or exp claims are rejected."""
    import jwt

    # Token missing 'sub'
    token_no_sub = jwt.encode({"iat": 1000000, "exp": 2000000}, TEST_SECRET_KEY, algorithm="HS256")
    with pytest.raises(TokenSecurityError):
        decode_access_token(token_no_sub, secret_key=TEST_SECRET_KEY)

    # Token missing 'iat'
    token_no_iat = jwt.encode({"sub": "1", "exp": 2000000}, TEST_SECRET_KEY, algorithm="HS256")
    with pytest.raises(TokenSecurityError):
        decode_access_token(token_no_iat, secret_key=TEST_SECRET_KEY)

    # Token missing 'exp'
    token_no_exp = jwt.encode({"sub": "1", "iat": 1000000}, TEST_SECRET_KEY, algorithm="HS256")
    with pytest.raises(TokenSecurityError):
        decode_access_token(token_no_exp, secret_key=TEST_SECRET_KEY)
