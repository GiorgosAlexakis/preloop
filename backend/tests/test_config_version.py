"""Tests for release version loading."""

from pathlib import Path

from preloop.config import _load_release_version


def test_load_release_version_reads_canonical_version_file(tmp_path: Path) -> None:
    """The helper should read the canonical VERSION file when present."""
    version_file = tmp_path / "VERSION"
    version_file.write_text("0.8.0-beta.1\n", encoding="utf-8")

    assert _load_release_version(version_file=version_file) == "0.8.0-beta.1"


def test_load_release_version_uses_fallback_when_file_missing(tmp_path: Path) -> None:
    """Missing version files should fall back cleanly."""
    missing_file = tmp_path / "VERSION"

    assert _load_release_version(default="9.9.9", version_file=missing_file) == "9.9.9"
