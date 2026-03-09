"""Unit tests for API common compliance helpers."""

import tempfile
from pathlib import Path

import yaml

from preloop.api.common import (
    get_compliance_prompts_from_config,
    load_compliance_prompts_config,
)


class TestGetCompliancePromptsFromConfig:
    """Tests for get_compliance_prompts_from_config."""

    def test_returns_empty_when_file_missing(self):
        """Returns empty list when config file does not exist."""
        result = get_compliance_prompts_from_config("/nonexistent/path.yaml")
        assert result == []

    def test_returns_empty_when_no_compliance_section(self):
        """Returns empty list when file has no compliance section."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump({"other": "data"}, f)
            path = f.name
        try:
            result = get_compliance_prompts_from_config(path)
            assert result == []
        finally:
            Path(path).unlink(missing_ok=True)

    def test_returns_prompts_metadata(self):
        """Returns list of CompliancePromptMetadata from compliance section."""
        config = {
            "compliance": {
                "prompt1": {
                    "name": "Prompt One",
                    "short_name": "P1",
                },
                "prompt2": {
                    "name": "Prompt Two",
                    "short_name": "P2",
                },
            }
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config, f)
            path = f.name
        try:
            result = get_compliance_prompts_from_config(path)
            assert len(result) == 2
            ids = [p.id for p in result]
            assert "prompt1" in ids
            assert "prompt2" in ids
            by_id = {p.id: p for p in result}
            assert by_id["prompt1"].name == "Prompt One"
            assert by_id["prompt1"].short_name == "P1"
        finally:
            Path(path).unlink(missing_ok=True)

    def test_uses_defaults_for_missing_fields(self):
        """Uses default values when name/short_name are missing."""
        config = {"compliance": {"minimal": {}}}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config, f)
            path = f.name
        try:
            result = get_compliance_prompts_from_config(path)
            assert len(result) == 1
            assert result[0].id == "minimal"
            assert result[0].name == "Unnamed Prompt"
            assert result[0].short_name == "N/A"
        finally:
            Path(path).unlink(missing_ok=True)


class TestLoadCompliancePromptsConfig:
    """Tests for load_compliance_prompts_config."""

    def test_returns_empty_when_file_missing(self):
        """Returns empty dict when config file does not exist."""
        result = load_compliance_prompts_config("/nonexistent/path.yaml")
        assert result == {}

    def test_returns_empty_when_no_compliance_section(self):
        """Returns empty dict when file has no compliance section."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump({"other": "data"}, f)
            path = f.name
        try:
            result = load_compliance_prompts_config(path)
            assert result == {}
        finally:
            Path(path).unlink(missing_ok=True)

    def test_returns_compliance_section_dict(self):
        """Returns the compliance section as a dict."""
        config = {
            "compliance": {
                "prompt1": {"name": "P1", "evaluate": {"system": "x", "user": "y"}},
            }
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config, f)
            path = f.name
        try:
            result = load_compliance_prompts_config(path)
            assert "prompt1" in result
            assert result["prompt1"]["name"] == "P1"
        finally:
            Path(path).unlink(missing_ok=True)
