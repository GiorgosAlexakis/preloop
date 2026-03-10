"""Tests for hashing utility."""

from preloop.utils.hashing import compute_content_hash


class TestComputeContentHash:
    """Test compute_content_hash function."""

    def test_hash_string(self):
        """String content produces consistent 16-char hash."""
        content = "hello world"
        result = compute_content_hash(content)
        assert isinstance(result, str)
        assert len(result) == 16
        assert result == compute_content_hash(content)

    def test_hash_dict(self):
        """Dict content serializes to JSON and hashes."""
        content = {"a": 1, "b": 2}
        result = compute_content_hash(content)
        assert isinstance(result, str)
        assert len(result) == 16
        assert result == compute_content_hash(content)

    def test_hash_dict_sorted_keys(self):
        """Dict with different key order produces same hash."""
        dict1 = {"b": 2, "a": 1}
        dict2 = {"a": 1, "b": 2}
        assert compute_content_hash(dict1) == compute_content_hash(dict2)

    def test_hash_list(self):
        """List content serializes and hashes."""
        content = ["tool1", "tool2"]
        result = compute_content_hash(content)
        assert isinstance(result, str)
        assert len(result) == 16

    def test_different_content_different_hash(self):
        """Different content produces different hashes."""
        h1 = compute_content_hash("prompt one")
        h2 = compute_content_hash("prompt two")
        assert h1 != h2

    def test_empty_string(self):
        """Empty string produces valid hash."""
        result = compute_content_hash("")
        assert isinstance(result, str)
        assert len(result) == 16

    def test_empty_list(self):
        """Empty list produces valid hash."""
        result = compute_content_hash([])
        assert isinstance(result, str)
        assert len(result) == 16

    def test_unicode_string(self):
        """Unicode content hashes correctly."""
        content = "Hello 世界 🌍"
        result = compute_content_hash(content)
        assert result == compute_content_hash(content)
