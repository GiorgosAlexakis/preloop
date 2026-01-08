"""Tests for flow preset loading functionality."""

from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from preloop.flow_presets import (
    _extract_order,
    _load_yaml_file,
    load_flow_presets,
)


class TestExtractOrder:
    """Tests for _extract_order helper function."""

    def test_numeric_prefix(self):
        """Test extraction of numeric prefix from filename."""
        assert _extract_order("01-issue-triage") == 1
        assert _extract_order("10-pr-reviewer") == 10
        assert _extract_order("99-custom-flow") == 99

    def test_no_numeric_prefix(self):
        """Test fallback when no numeric prefix exists."""
        assert _extract_order("issue-triage") == 9999
        assert _extract_order("custom") == 9999

    def test_invalid_prefix(self):
        """Test fallback for non-numeric prefix."""
        assert _extract_order("abc-flow") == 9999


class TestLoadYamlFile:
    """Tests for _load_yaml_file helper function."""

    def test_valid_yaml(self, tmp_path: Path):
        """Test loading a valid YAML file."""
        yaml_file = tmp_path / "test.yml"
        yaml_file.write_text(
            """
name: Test Flow
description: A test flow
trigger_event_type: push
"""
        )
        result = _load_yaml_file(yaml_file)
        assert result["name"] == "Test Flow"
        assert result["description"] == "A test flow"
        assert result["is_preset"] is True  # Default added

    def test_is_preset_default(self, tmp_path: Path):
        """Test that is_preset defaults to True."""
        yaml_file = tmp_path / "test.yml"
        yaml_file.write_text("name: Test\n")
        result = _load_yaml_file(yaml_file)
        assert result["is_preset"] is True

    def test_is_preset_explicit_false(self, tmp_path: Path):
        """Test that explicit is_preset: false is preserved."""
        yaml_file = tmp_path / "test.yml"
        yaml_file.write_text("name: Test\nis_preset: false\n")
        result = _load_yaml_file(yaml_file)
        assert result["is_preset"] is False

    def test_invalid_yaml_syntax(self, tmp_path: Path):
        """Test error handling for invalid YAML syntax."""
        yaml_file = tmp_path / "invalid.yml"
        yaml_file.write_text("name: [unclosed bracket")
        with pytest.raises(ValueError, match="Failed to parse preset file"):
            _load_yaml_file(yaml_file)

    def test_non_mapping_yaml(self, tmp_path: Path):
        """Test error handling when YAML is not a mapping."""
        yaml_file = tmp_path / "list.yml"
        yaml_file.write_text("- item1\n- item2\n")
        with pytest.raises(ValueError, match="must define a mapping"):
            _load_yaml_file(yaml_file)


class TestLoadFlowPresets:
    """Tests for load_flow_presets function."""

    def test_empty_presets_dir(self, tmp_path: Path):
        """Test that empty presets directory returns empty list."""
        presets_dir = tmp_path / "presets"
        presets_dir.mkdir()

        with patch("preloop.flow_presets.PRESETS_DIR", presets_dir):
            # Clear the lru_cache
            load_flow_presets.cache_clear()
            result = load_flow_presets()
            assert result == []

    def test_missing_presets_dir(self, tmp_path: Path):
        """Test that missing presets directory returns empty list (open source default)."""
        nonexistent_dir = tmp_path / "nonexistent"

        with patch("preloop.flow_presets.PRESETS_DIR", nonexistent_dir):
            load_flow_presets.cache_clear()
            result = load_flow_presets()
            assert result == []

    def test_loads_yaml_files(self, tmp_path: Path):
        """Test that YAML files are loaded correctly."""
        presets_dir = tmp_path / "presets"
        presets_dir.mkdir()

        # Create test preset files
        (presets_dir / "01-first.yml").write_text("name: First Flow\n")
        (presets_dir / "02-second.yaml").write_text("name: Second Flow\n")

        with patch("preloop.flow_presets.PRESETS_DIR", presets_dir):
            load_flow_presets.cache_clear()
            result = load_flow_presets()

            assert len(result) == 2
            assert result[0]["name"] == "First Flow"
            assert result[1]["name"] == "Second Flow"

    def test_ordering_by_numeric_prefix(self, tmp_path: Path):
        """Test that presets are ordered by numeric prefix."""
        presets_dir = tmp_path / "presets"
        presets_dir.mkdir()

        # Create files in non-sequential order
        (presets_dir / "10-last.yml").write_text("name: Last\n")
        (presets_dir / "01-first.yml").write_text("name: First\n")
        (presets_dir / "05-middle.yml").write_text("name: Middle\n")

        with patch("preloop.flow_presets.PRESETS_DIR", presets_dir):
            load_flow_presets.cache_clear()
            result = load_flow_presets()

            assert len(result) == 3
            assert result[0]["name"] == "First"
            assert result[1]["name"] == "Middle"
            assert result[2]["name"] == "Last"


class TestFlowPresetSchema:
    """Tests to validate flow preset schema requirements."""

    # Required keys that every flow preset should have
    REQUIRED_KEYS = {"name"}

    # Optional but recommended keys
    RECOMMENDED_KEYS = {
        "description",
        "trigger_event_type",
        "prompt_template",
        "agent_type",
    }

    def test_presets_have_required_keys(self, tmp_path: Path):
        """Test that all presets have required keys."""
        presets_dir = tmp_path / "presets"
        presets_dir.mkdir()

        # Create a valid preset
        valid_preset = {
            "name": "Test Flow",
            "description": "A test flow",
            "trigger_event_type": "push",
            "prompt_template": "Do something",
            "agent_type": "codex",
        }
        (presets_dir / "01-test.yml").write_text(yaml.dump(valid_preset))

        with patch("preloop.flow_presets.PRESETS_DIR", presets_dir):
            load_flow_presets.cache_clear()
            presets = load_flow_presets()

            for preset in presets:
                for key in self.REQUIRED_KEYS:
                    assert key in preset, f"Preset missing required key: {key}"

    def test_actual_presets_directory(self):
        """Test that actual presets directory (if exists) has valid presets.

        This test validates the real presets in the codebase.
        For open source, the directory may be empty which is acceptable.
        """
        load_flow_presets.cache_clear()
        presets = load_flow_presets()

        # Open source may have no presets - that's OK
        # But if presets exist, they must be valid
        for preset in presets:
            # Every preset must have a name
            assert "name" in preset, f"Preset missing 'name' key: {preset}"

            # is_preset should be True (set by default or explicitly)
            assert preset.get("is_preset", True) is True or preset.get("is_preset"), (
                f"Preset should have is_preset=True: {preset.get('name')}"
            )
