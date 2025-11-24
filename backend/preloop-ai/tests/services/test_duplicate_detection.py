"""Tests for duplicate detection service."""

import pytest

from preloop_ai.services.duplicate_detection import DuplicateDetector

pytestmark = pytest.mark.asyncio


class TestDuplicateDetector:
    """Test DuplicateDetector class."""

    async def test_check_duplicates_with_empty_list(self):
        """Test check_duplicates with empty potential duplicates list."""
        detector = DuplicateDetector()
        result = await detector.check_duplicates(
            new_title="New Issue",
            new_description="This is a new issue description",
            potential_duplicates=[],
        )

        assert result == {"status": "not_duplicate"}
        assert isinstance(result, dict)
        assert "status" in result

    async def test_check_duplicates_with_populated_list(self):
        """Test check_duplicates with potential duplicates."""
        detector = DuplicateDetector()
        potential_duplicates = [
            {
                "id": "issue-1",
                "title": "Similar Issue",
                "description": "Similar description",
            },
            {
                "id": "issue-2",
                "title": "Another Similar Issue",
                "description": "Another similar description",
            },
        ]

        result = await detector.check_duplicates(
            new_title="New Issue",
            new_description="This is a new issue description",
            potential_duplicates=potential_duplicates,
        )

        # Currently returns not_duplicate as it's a placeholder
        assert result == {"status": "not_duplicate"}

    async def test_check_duplicates_with_empty_strings(self):
        """Test check_duplicates with empty title and description."""
        detector = DuplicateDetector()
        result = await detector.check_duplicates(
            new_title="",
            new_description="",
            potential_duplicates=[],
        )

        assert result == {"status": "not_duplicate"}

    async def test_check_duplicates_with_special_characters(self):
        """Test check_duplicates with special characters in title and description."""
        detector = DuplicateDetector()
        result = await detector.check_duplicates(
            new_title="Bug: [CRITICAL] System crashes on startup @#$%",
            new_description="Description with <html> tags & special chars: émojis 🚀",
            potential_duplicates=[
                {
                    "id": "issue-3",
                    "title": "System crashes",
                    "description": "Crash on startup",
                }
            ],
        )

        assert result == {"status": "not_duplicate"}

    async def test_check_duplicates_with_long_inputs(self):
        """Test check_duplicates with very long title and description."""
        detector = DuplicateDetector()
        long_title = "A" * 1000
        long_description = "B" * 10000

        result = await detector.check_duplicates(
            new_title=long_title,
            new_description=long_description,
            potential_duplicates=[],
        )

        assert result == {"status": "not_duplicate"}

    async def test_check_duplicates_return_type(self):
        """Test that check_duplicates returns correct type."""
        detector = DuplicateDetector()
        result = await detector.check_duplicates(
            new_title="Test",
            new_description="Test",
            potential_duplicates=[],
        )

        assert isinstance(result, dict)
        assert isinstance(result.get("status"), str)

    async def test_check_duplicates_multiple_calls(self):
        """Test that multiple calls to check_duplicates work correctly."""
        detector = DuplicateDetector()

        result1 = await detector.check_duplicates(
            new_title="Issue 1",
            new_description="Description 1",
            potential_duplicates=[],
        )

        result2 = await detector.check_duplicates(
            new_title="Issue 2",
            new_description="Description 2",
            potential_duplicates=[{"id": "issue-x", "title": "Existing"}],
        )

        assert result1 == {"status": "not_duplicate"}
        assert result2 == {"status": "not_duplicate"}
        assert result1 == result2

    async def test_check_duplicates_with_unicode(self):
        """Test check_duplicates with unicode characters."""
        detector = DuplicateDetector()
        result = await detector.check_duplicates(
            new_title="问题标题 (Chinese title)",
            new_description="Описание проблемы (Russian description) 日本語",
            potential_duplicates=[],
        )

        assert result == {"status": "not_duplicate"}
