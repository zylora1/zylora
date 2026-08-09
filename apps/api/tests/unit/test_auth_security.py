from __future__ import annotations

import pytest
from zylora_api.modules.auth.security import AuthCrypto, InvalidEmailError


def test_argon2id_passwords_are_salted_verified_and_reject_wrong_values() -> None:
    crypto = AuthCrypto("test-auth-secret-with-more-than-thirty-two-characters")
    first = crypto.hash_password("Correct-Horse-42!")
    second = crypto.hash_password("Correct-Horse-42!")

    assert first.startswith("$argon2id$")
    assert first != second
    assert crypto.verify_password(first, "Correct-Horse-42!") is True
    assert crypto.verify_password(first, "Wrong-Horse-42!") is False
    assert crypto.verify_password(None, "Wrong-Horse-42!") is False


@pytest.mark.parametrize(
    "password",
    ["Short-1!", "all-lowercase-1!", "ALL-UPPERCASE-1!", "NoNumbersHere!", "NoSymbolsHere42"],
)
def test_password_policy_rejects_weak_values(password: str) -> None:
    crypto = AuthCrypto("test-auth-secret-with-more-than-thirty-two-characters")

    with pytest.raises(ValueError, match="password"):
        crypto.hash_password(password)


def test_super_admin_password_policy_requires_at_least_sixteen_characters() -> None:
    crypto = AuthCrypto("test-auth-secret-with-more-than-thirty-two-characters")

    with pytest.raises(ValueError, match="password"):
        crypto.hash_password("Strong-User1!", admin=True)
    assert crypto.hash_password("Admin-Very-Strong-42!", admin=True).startswith("$argon2id$")


def test_email_normalization_and_invalid_address_handling() -> None:
    crypto = AuthCrypto("test-auth-secret-with-more-than-thirty-two-characters")

    assert crypto.normalize_email(" Person@Example.COM ") == (
        "person@example.com",
        "Person@example.com",
    )
    with pytest.raises(InvalidEmailError):
        crypto.normalize_email("not-an-email")


def test_tokens_digests_pkce_and_encryption_are_purpose_bound() -> None:
    crypto = AuthCrypto("test-auth-secret-with-more-than-thirty-two-characters")
    value = crypto.token()
    ciphertext = crypto.encrypt(value, purpose="oauth-pkce")

    assert value.encode() not in ciphertext
    assert crypto.decrypt(ciphertext, purpose="oauth-pkce") == value
    assert crypto.digest(value, purpose="one") != crypto.digest(value, purpose="two")
    assert "=" not in crypto.pkce_challenge(value)
    assert len(crypto.verification_code()) == 6
