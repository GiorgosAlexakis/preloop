"""
Tests for tracker utility functions.
"""

import pytest
from unittest.mock import Mock, patch

from preloop.sync.trackers.utils import (
    is_http_error,
    is_not_found_error,
    is_authentication_error,
    is_conflict_error,
    async_retry,
    extract_repo_name_from_url,
    normalize_datetime_string,
    safe_dict_get,
    truncate_description,
)


class TestHttpErrorDetection:
    """Test HTTP error detection functions."""

    def test_is_http_error_with_string_representation(self):
        """Test error detection via string representation."""
        error = Exception("404 Not Found")
        assert is_http_error(error, 404)
        assert not is_http_error(error, 401)

    def test_is_http_error_with_response_code_attribute(self):
        """Test error detection via response_code attribute (python-gitlab style)."""
        error = Mock()
        error.response_code = 404
        assert is_http_error(error, 404)
        assert not is_http_error(error, 401)

    def test_is_http_error_with_status_code_attribute(self):
        """Test error detection via status_code attribute (requests style)."""
        error = Mock()
        error.status_code = 404
        assert is_http_error(error, 404)
        assert not is_http_error(error, 401)

    def test_is_http_error_with_response_status_code(self):
        """Test error detection via response.status_code (httpx style)."""
        error = Mock()
        error.response = Mock()
        error.response.status_code = 404
        assert is_http_error(error, 404)
        assert not is_http_error(error, 401)

    def test_is_not_found_error(self):
        """Test 404 error detection."""
        error = Exception("404 Not Found")
        assert is_not_found_error(error)

        error = Exception("401 Unauthorized")
        assert not is_not_found_error(error)

    def test_is_authentication_error(self):
        """Test 401 error detection."""
        error = Exception("401 Unauthorized")
        assert is_authentication_error(error)

        error = Exception("404 Not Found")
        assert not is_authentication_error(error)

    def test_is_conflict_error(self):
        """Test 409 error detection."""
        error = Exception("409 Conflict")
        assert is_conflict_error(error)

        error = Exception("404 Not Found")
        assert not is_conflict_error(error)


class TestAsyncRetry:
    """Test async retry decorator."""

    @pytest.mark.asyncio
    async def test_async_retry_success_on_first_attempt(self):
        """Test successful execution on first attempt."""
        call_count = 0

        @async_retry(max_attempts=3)
        async def test_func():
            nonlocal call_count
            call_count += 1
            return "success"

        result = await test_func()
        assert result == "success"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_async_retry_success_after_failures(self):
        """Test successful execution after initial failures."""
        call_count = 0

        @async_retry(max_attempts=3, delay=0.01)
        async def test_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Temporary failure")
            return "success"

        result = await test_func()
        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_async_retry_max_attempts_exceeded(self):
        """Test failure when max attempts exceeded."""
        call_count = 0

        @async_retry(max_attempts=2, delay=0.01)
        async def test_func():
            nonlocal call_count
            call_count += 1
            raise Exception("Persistent failure")

        with pytest.raises(Exception, match="Persistent failure"):
            await test_func()
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_async_retry_with_specific_exceptions(self):
        """Test retry with specific exception types."""
        call_count = 0

        @async_retry(max_attempts=3, delay=0.01, exceptions=ValueError)
        async def test_func():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("Retryable error")
            elif call_count == 2:
                raise RuntimeError("Non-retryable error")
            return "success"

        with pytest.raises(RuntimeError, match="Non-retryable error"):
            await test_func()
        assert call_count == 2


class TestUtilityFunctions:
    """Test general utility functions."""

    def test_extract_repo_name_from_url_github_https(self):
        """Test GitHub HTTPS URL extraction."""
        url = "https://github.com/owner/repo.git"
        assert extract_repo_name_from_url(url) == "owner/repo"

        url = "https://github.com/owner/repo"
        assert extract_repo_name_from_url(url) == "owner/repo"

    def test_extract_repo_name_from_url_gitlab_https(self):
        """Test GitLab HTTPS URL extraction."""
        url = "https://gitlab.com/owner/repo.git"
        assert extract_repo_name_from_url(url) == "owner/repo"

        url = "https://gitlab.com/owner/repo"
        assert extract_repo_name_from_url(url) == "owner/repo"

    def test_extract_repo_name_from_url_invalid(self):
        """Test invalid URL handling."""
        url = "https://example.com/invalid"
        assert extract_repo_name_from_url(url) is None

    def test_normalize_datetime_string_github_format(self):
        """Test GitHub datetime format normalization."""
        dt_str = "2023-12-01T10:30:45.123Z"
        result = normalize_datetime_string(dt_str)
        assert "2023-12-01T10:30:45.123000" in result

    def test_normalize_datetime_string_jira_format(self):
        """Test Jira datetime format normalization."""
        dt_str = "2023-12-01T10:30:45.123+0000"
        result = normalize_datetime_string(dt_str)
        assert "2023-12-01T10:30:45.123000" in result

    def test_normalize_datetime_string_invalid(self):
        """Test invalid datetime string handling."""
        dt_str = "invalid-date"
        result = normalize_datetime_string(dt_str)
        assert result == "invalid-date"

    def test_safe_dict_get_success(self):
        """Test successful nested dictionary navigation."""
        data = {"user": {"profile": {"name": "John Doe"}}}
        result = safe_dict_get(data, ["user", "profile", "name"])
        assert result == "John Doe"

    def test_safe_dict_get_missing_key(self):
        """Test navigation with missing key."""
        data = {"user": {"profile": {}}}
        result = safe_dict_get(data, ["user", "profile", "name"], default="Unknown")
        assert result == "Unknown"

    def test_safe_dict_get_non_dict_value(self):
        """Test navigation with non-dict intermediate value."""
        data = {"user": "not_a_dict"}
        result = safe_dict_get(data, ["user", "profile", "name"], default="Unknown")
        assert result == "Unknown"

    def test_truncate_description_no_truncation(self):
        """Test description that doesn't need truncation."""
        desc = "Short description"
        result = truncate_description(desc, 100)
        assert result == desc

    def test_truncate_description_with_truncation(self):
        """Test description truncation."""
        desc = "A" * 100
        result = truncate_description(desc, 50)
        assert len(result) == 50
        assert result.endswith("... [content truncated]")

    def test_truncate_description_empty(self):
        """Test empty description handling."""
        result = truncate_description("", 50)
        assert result == ""

    def test_truncate_description_none(self):
        """Test None description handling."""
        result = truncate_description(None, 50)
        assert result is None


class TestDependencyParsing:
    """Test dependency parsing functionality."""

    @pytest.mark.asyncio
    async def test_github_dependency_parsing(self):
        """Test GitHub dependency parsing."""
        # We'll need to import and test the GitHub tracker's _parse_dependencies method
        from preloop.sync.trackers.github import GitHubTracker

        tracker = GitHubTracker("test-id", "test-key", {})

        content = "This closes #123 and fixes owner/repo#456"
        repo = "owner/current-repo"

        dependencies = await tracker._parse_dependencies(content, repo)

        assert len(dependencies) == 2
        assert dependencies[0]["target_key"] == "owner/current-repo#123"
        assert dependencies[0]["type"] == "closes"
        assert dependencies[1]["target_key"] == "owner/repo#456"
        assert dependencies[1]["type"] == "closes"

    @pytest.mark.asyncio
    async def test_github_dependency_parsing_related(self):
        """Test GitHub dependency parsing for related issues."""
        from preloop.sync.trackers.github import GitHubTracker

        tracker = GitHubTracker("test-id", "test-key", {})

        content = "This relates to #789 and is blocked by #101"
        repo = "owner/repo"

        dependencies = await tracker._parse_dependencies(content, repo)

        assert len(dependencies) == 2
        assert dependencies[0]["target_key"] == "owner/repo#789"
        assert dependencies[0]["type"] == "related"
        assert dependencies[1]["target_key"] == "owner/repo#101"
        assert dependencies[1]["type"] == "is blocked by"

    @pytest.mark.asyncio
    async def test_gitlab_dependency_parsing(self):
        """Test GitLab dependency parsing."""
        from preloop.sync.trackers.gitlab import GitLabTracker

        # Mock the GitLab client and connection details
        connection_details = {"url": "https://gitlab.com"}

        with patch("gitlab.Gitlab"):
            tracker = GitLabTracker("test-id", "test-key", connection_details)

            # Mock issue links
            mock_links = [
                Mock(project_id=1, iid=123, link_type="relates_to"),
                Mock(project_id=2, iid=456, link_type="blocks"),
            ]

            # Mock the project get calls
            mock_project1 = Mock()
            mock_project1.path_with_namespace = "group/project1"
            mock_project2 = Mock()
            mock_project2.path_with_namespace = "group/project2"

            with patch.object(tracker, "_make_request") as mock_request:
                mock_request.side_effect = [mock_project1, mock_project2]

                dependencies = await tracker._parse_dependencies(mock_links)

                assert len(dependencies) == 2
                assert dependencies[0]["target_key"] == "group/project1#123"
                assert dependencies[0]["type"] == "relates to"
                assert dependencies[1]["target_key"] == "group/project2#456"
                assert dependencies[1]["type"] == "blocks"
