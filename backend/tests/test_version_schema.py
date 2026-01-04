"""Tests for version Pydantic schemas."""

import pytest
from pydantic import ValidationError

from preloop.schemas.version import VersionInfo


class TestVersionInfo:
    """Test VersionInfo schema."""

    def test_create_with_all_fields(self):
        """Test creating VersionInfo with all required fields."""
        version = VersionInfo(
            server_version="1.2.3",
            min_client_version="1.0.0",
            max_client_version="2.0.0",
        )

        assert version.server_version == "1.2.3"
        assert version.min_client_version == "1.0.0"
        assert version.max_client_version == "2.0.0"

    def test_required_fields_validation(self):
        """Test that all fields are required."""
        with pytest.raises(ValidationError) as exc_info:
            VersionInfo()

        errors = exc_info.value.errors()
        error_fields = {error["loc"][0] for error in errors}

        # Check that all required fields are in the error
        required_fields = {"server_version", "min_client_version", "max_client_version"}
        assert required_fields == error_fields

    def test_partial_fields_validation(self):
        """Test that partial fields fail validation."""
        with pytest.raises(ValidationError) as exc_info:
            VersionInfo(server_version="1.0.0")

        errors = exc_info.value.errors()
        error_fields = {error["loc"][0] for error in errors}

        # Missing fields should be in errors
        assert "min_client_version" in error_fields
        assert "max_client_version" in error_fields

    def test_semantic_versioning_format(self):
        """Test that various version formats are accepted."""
        # Standard semantic versioning
        version1 = VersionInfo(
            server_version="1.0.0",
            min_client_version="0.9.0",
            max_client_version="1.1.0",
        )
        assert version1.server_version == "1.0.0"

        # Pre-release versions
        version2 = VersionInfo(
            server_version="2.0.0-beta.1",
            min_client_version="1.9.0",
            max_client_version="2.0.0",
        )
        assert version2.server_version == "2.0.0-beta.1"

        # Build metadata
        version3 = VersionInfo(
            server_version="3.0.0+20210101",
            min_client_version="2.0.0",
            max_client_version="3.0.0",
        )
        assert version3.server_version == "3.0.0+20210101"

    def test_field_types_are_strings(self):
        """Test that version fields accept strings."""
        version = VersionInfo(
            server_version="latest",
            min_client_version="v1.0",
            max_client_version="v2.0",
        )

        assert isinstance(version.server_version, str)
        assert isinstance(version.min_client_version, str)
        assert isinstance(version.max_client_version, str)

    def test_empty_strings_accepted(self):
        """Test that empty strings are accepted (no min_length constraint)."""
        version = VersionInfo(
            server_version="",
            min_client_version="",
            max_client_version="",
        )

        assert version.server_version == ""
        assert version.min_client_version == ""
        assert version.max_client_version == ""
