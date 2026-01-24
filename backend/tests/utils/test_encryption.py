"""Tests for encryption utility."""

import pytest
from unittest.mock import patch, MagicMock


class TestEncryption:
    """Test encryption utilities."""

    def setup_method(self):
        """Reset encryption cache before each test."""
        from preloop.utils.encryption import reset_encryption_cache

        reset_encryption_cache()

    def teardown_method(self):
        """Reset encryption cache after each test."""
        from preloop.utils.encryption import reset_encryption_cache

        reset_encryption_cache()

    def test_encrypt_decrypt_roundtrip_with_encryption_key(self):
        """Test that encrypt/decrypt roundtrip works with dedicated encryption key."""
        from cryptography.fernet import Fernet

        # Generate a valid Fernet key
        fernet_key = Fernet.generate_key().decode()

        mock_settings = MagicMock()
        mock_settings.security.encryption_key = fernet_key
        mock_settings.security.secret_key = "unused"

        with patch("preloop.config.settings", mock_settings):
            from preloop.utils.encryption import encrypt_value, decrypt_value

            original = "my-secret-api-token"
            encrypted = encrypt_value(original)

            # Encrypted value should be different from original
            assert encrypted != original
            assert len(encrypted) > 0

            # Decryption should return original value
            decrypted = decrypt_value(encrypted)
            assert decrypted == original

    def test_encrypt_decrypt_roundtrip_with_derived_key(self):
        """Test that encrypt/decrypt roundtrip works with key derived from secret_key."""
        mock_settings = MagicMock()
        mock_settings.security.encryption_key = ""
        mock_settings.security.secret_key = "my-jwt-secret-key-for-testing"

        with patch("preloop.config.settings", mock_settings):
            from preloop.utils.encryption import encrypt_value, decrypt_value

            original = "sensitive-oauth-token"
            encrypted = encrypt_value(original)

            # Encrypted value should be different from original
            assert encrypted != original

            # Decryption should return original value
            decrypted = decrypt_value(encrypted)
            assert decrypted == original

    def test_encrypt_empty_string_returns_empty(self):
        """Test that encrypting empty string returns empty string."""
        mock_settings = MagicMock()
        mock_settings.security.encryption_key = ""
        mock_settings.security.secret_key = "test-secret"

        with patch("preloop.config.settings", mock_settings):
            from preloop.utils.encryption import encrypt_value

            result = encrypt_value("")
            assert result == ""

    def test_decrypt_empty_string_returns_empty(self):
        """Test that decrypting empty string returns empty string."""
        mock_settings = MagicMock()
        mock_settings.security.encryption_key = ""
        mock_settings.security.secret_key = "test-secret"

        with patch("preloop.config.settings", mock_settings):
            from preloop.utils.encryption import decrypt_value

            result = decrypt_value("")
            assert result == ""

    def test_decrypt_invalid_token_raises_value_error(self):
        """Test that decrypting invalid token raises ValueError."""
        mock_settings = MagicMock()
        mock_settings.security.encryption_key = ""
        mock_settings.security.secret_key = "test-secret"

        with patch("preloop.config.settings", mock_settings):
            from preloop.utils.encryption import decrypt_value

            with pytest.raises(ValueError, match="Unable to decrypt value"):
                decrypt_value("not-a-valid-fernet-token")

    def test_decrypt_with_wrong_key_raises_value_error(self):
        """Test that decrypting with wrong key raises ValueError."""
        from cryptography.fernet import Fernet
        from preloop.utils.encryption import (
            encrypt_value,
            decrypt_value,
            reset_encryption_cache,
        )

        # Encrypt with one key
        key1 = Fernet.generate_key().decode()
        mock_settings1 = MagicMock()
        mock_settings1.security.encryption_key = key1
        mock_settings1.security.secret_key = ""

        with patch("preloop.config.settings", mock_settings1):
            encrypted = encrypt_value("secret-data")

        # Reset and use different key
        reset_encryption_cache()
        key2 = Fernet.generate_key().decode()
        mock_settings2 = MagicMock()
        mock_settings2.security.encryption_key = key2
        mock_settings2.security.secret_key = ""

        with patch("preloop.config.settings", mock_settings2):
            with pytest.raises(ValueError, match="Unable to decrypt value"):
                decrypt_value(encrypted)

    def test_no_encryption_key_raises_value_error(self):
        """Test that missing encryption key raises ValueError."""
        mock_settings = MagicMock()
        mock_settings.security.encryption_key = ""
        mock_settings.security.secret_key = ""

        with patch("preloop.config.settings", mock_settings):
            from preloop.utils.encryption import encrypt_value

            with pytest.raises(ValueError, match="No encryption key available"):
                encrypt_value("test")

    def test_encryption_key_priority_over_derived(self):
        """Test that dedicated encryption_key takes priority over derived key."""
        from cryptography.fernet import Fernet
        from preloop.utils.encryption import (
            encrypt_value,
            decrypt_value,
            reset_encryption_cache,
        )

        # Set both keys
        encryption_key = Fernet.generate_key().decode()
        mock_settings = MagicMock()
        mock_settings.security.encryption_key = encryption_key
        mock_settings.security.secret_key = "different-secret"

        with patch("preloop.config.settings", mock_settings):
            # Encrypt with encryption_key
            encrypted = encrypt_value("test-data")

            # Reset cache
            reset_encryption_cache()

            # Change secret_key but keep encryption_key
            mock_settings.security.secret_key = "completely-different-secret"

            # Should still decrypt because encryption_key is used
            decrypted = decrypt_value(encrypted)
            assert decrypted == "test-data"

    def test_derived_key_is_deterministic(self):
        """Test that derived key from same secret is deterministic."""
        from preloop.utils.encryption import (
            encrypt_value,
            decrypt_value,
            reset_encryption_cache,
        )

        mock_settings = MagicMock()
        mock_settings.security.encryption_key = ""
        mock_settings.security.secret_key = "consistent-secret-key"

        with patch("preloop.config.settings", mock_settings):
            # Encrypt with derived key
            encrypted = encrypt_value("deterministic-test")

            # Reset cache and decrypt again (should derive same key)
            reset_encryption_cache()

            decrypted = decrypt_value(encrypted)
            assert decrypted == "deterministic-test"

    def test_fernet_caching(self):
        """Test that Fernet instance is cached."""
        mock_settings = MagicMock()
        mock_settings.security.encryption_key = ""
        mock_settings.security.secret_key = "test-secret"

        with patch("preloop.config.settings", mock_settings):
            from preloop.utils.encryption import _get_fernet

            fernet1 = _get_fernet()
            fernet2 = _get_fernet()

            # Should be the same instance (cached)
            assert fernet1 is fernet2

    def test_reset_encryption_cache(self):
        """Test that reset_encryption_cache clears the cache."""
        mock_settings = MagicMock()
        mock_settings.security.encryption_key = ""
        mock_settings.security.secret_key = "test-secret"

        with patch("preloop.config.settings", mock_settings):
            from preloop.utils.encryption import _get_fernet, reset_encryption_cache

            fernet1 = _get_fernet()
            reset_encryption_cache()
            fernet2 = _get_fernet()

            # Should be different instances after reset
            assert fernet1 is not fernet2

    def test_encrypt_unicode_content(self):
        """Test that encryption handles unicode content correctly."""
        mock_settings = MagicMock()
        mock_settings.security.encryption_key = ""
        mock_settings.security.secret_key = "test-secret"

        with patch("preloop.config.settings", mock_settings):
            from preloop.utils.encryption import encrypt_value, decrypt_value

            # Test with various unicode characters
            original = "Hello 世界 🌍 émojis"
            encrypted = encrypt_value(original)
            decrypted = decrypt_value(encrypted)

            assert decrypted == original

    def test_encrypt_long_content(self):
        """Test that encryption handles long content."""
        mock_settings = MagicMock()
        mock_settings.security.encryption_key = ""
        mock_settings.security.secret_key = "test-secret"

        with patch("preloop.config.settings", mock_settings):
            from preloop.utils.encryption import encrypt_value, decrypt_value

            # Test with long content (e.g., an API token or private key)
            original = "x" * 10000
            encrypted = encrypt_value(original)
            decrypted = decrypt_value(encrypted)

            assert decrypted == original

    def test_encrypted_value_is_fernet_format(self):
        """Test that encrypted value is valid Fernet token format."""
        mock_settings = MagicMock()
        mock_settings.security.encryption_key = ""
        mock_settings.security.secret_key = "test-secret"

        with patch("preloop.config.settings", mock_settings):
            from preloop.utils.encryption import encrypt_value

            encrypted = encrypt_value("test-data")

            # Fernet tokens are base64 encoded and have specific characteristics
            # They should be decodable as base64 (with URL-safe encoding)
            import base64

            try:
                # Fernet tokens can be decoded with urlsafe_b64decode
                decoded = base64.urlsafe_b64decode(encrypted)
                # Fernet tokens have a specific structure (version byte + timestamp + IV + ciphertext + HMAC)
                # Minimum size is around 73 bytes
                assert len(decoded) >= 73
            except Exception:
                pytest.fail("Encrypted value is not valid Fernet format")
