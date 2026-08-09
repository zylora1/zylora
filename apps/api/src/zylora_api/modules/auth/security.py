from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from dataclasses import dataclass

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from email_validator import EmailNotValidError, validate_email


class InvalidEmailError(ValueError):
    pass


@dataclass(frozen=True)
class PasswordPolicy:
    minimum_length: int = 12
    maximum_length: int = 128

    def validate(self, password: str) -> None:
        if not self.minimum_length <= len(password) <= self.maximum_length:
            raise ValueError("password must contain between 12 and 128 characters")
        if password.casefold() == password or password.upper() == password:
            raise ValueError("password must include uppercase and lowercase letters")
        if not any(character.isdigit() for character in password):
            raise ValueError("password must include a number")
        if not any(not character.isalnum() for character in password):
            raise ValueError("password must include a symbol")


class AuthCrypto:
    """Central cryptographic boundary for credentials, tokens, and redacted identifiers."""

    def __init__(self, secret: str) -> None:
        self._key = hashlib.sha256(secret.encode("utf-8")).digest()
        self._passwords = PasswordHasher(
            time_cost=3,
            memory_cost=65_536,
            parallelism=4,
            hash_len=32,
            salt_len=16,
        )
        self.password_policy = PasswordPolicy()
        self.admin_password_policy = PasswordPolicy(minimum_length=16)

    @staticmethod
    def normalize_email(raw_email: str) -> tuple[str, str]:
        try:
            result = validate_email(raw_email.strip(), check_deliverability=False)
        except EmailNotValidError as error:
            raise InvalidEmailError("email address is invalid") from error
        normalized = result.normalized.casefold()
        return normalized, result.normalized

    def hash_password(self, password: str, *, admin: bool = False) -> str:
        policy = self.admin_password_policy if admin else self.password_policy
        policy.validate(password)
        return self._passwords.hash(password)

    def verify_password(self, password_hash: str | None, candidate: str) -> bool:
        if password_hash is None:
            self._passwords.hash(candidate)
            return False
        try:
            return self._passwords.verify(password_hash, candidate)
        except (VerificationError, InvalidHashError):
            return False

    def password_needs_rehash(self, password_hash: str) -> bool:
        return self._passwords.check_needs_rehash(password_hash)

    def digest(self, value: str, *, purpose: str) -> bytes:
        return hmac.new(self._key, f"{purpose}:{value}".encode(), hashlib.sha256).digest()

    @staticmethod
    def token(byte_count: int = 32) -> str:
        return secrets.token_urlsafe(byte_count)

    @staticmethod
    def verification_code() -> str:
        return f"{secrets.randbelow(1_000_000):06d}"

    @staticmethod
    def pkce_challenge(verifier: str) -> str:
        digest = hashlib.sha256(verifier.encode()).digest()
        return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()

    def encrypt(self, plaintext: str, *, purpose: str) -> bytes:
        nonce = secrets.token_bytes(12)
        associated_data = purpose.encode()
        ciphertext = AESGCM(self._key).encrypt(nonce, plaintext.encode(), associated_data)
        return nonce + ciphertext

    def decrypt(self, ciphertext: bytes, *, purpose: str) -> str:
        plaintext = AESGCM(self._key).decrypt(ciphertext[:12], ciphertext[12:], purpose.encode())
        return plaintext.decode()

    @staticmethod
    def constant_time_equal(left: bytes, right: bytes) -> bool:
        return hmac.compare_digest(left, right)
