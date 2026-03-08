"""Tests for release version loading."""

from importlib.metadata import PackageNotFoundError
from pathlib import Path
from unittest.mock import patch

from preloop.config import _load_release_version


def test_load_release_version_uses_package_metadata_when_installed() -> None:
    """When installed via pip, version comes from package metadata."""
    with patch("preloop.config.version", return_value="0.8.0-beta.4"):
        assert _load_release_version() == "0.8.0-beta.4"


def test_load_release_version_reads_version_file_when_package_not_installed(
    tmp_path: Path,
) -> None:
    """When package metadata is unavailable, read the VERSION file (Docker/local dev)."""
    version_file = tmp_path / "VERSION"
    version_file.write_text("0.8.0-beta.1\n", encoding="utf-8")

    with patch("preloop.config.version", side_effect=PackageNotFoundError("preloop")):
        assert _load_release_version(version_file=version_file) == "0.8.0-beta.1"


def test_load_release_version_uses_fallback_when_both_unavailable(
    tmp_path: Path,
) -> None:
    """When metadata and file are both unavailable, use default."""
    missing_file = tmp_path / "VERSION"

    with patch("preloop.config.version", side_effect=PackageNotFoundError("preloop")):
        assert (
            _load_release_version(default="9.9.9", version_file=missing_file) == "9.9.9"
        )
