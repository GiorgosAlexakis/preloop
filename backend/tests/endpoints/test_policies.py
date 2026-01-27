"""Tests for policies API endpoints."""

import uuid
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException, status

from preloop.api.endpoints import policies
from preloop.models.models.account import Account
from preloop.services.policy import (
    PolicyDocument,
    PolicyImportResult,
    PolicyValidationResult,
)

pytestmark = pytest.mark.asyncio


@pytest.fixture
def mock_account():
    """Create mock account for testing."""
    account = MagicMock(spec=Account)
    account.id = uuid.uuid4()
    account.username = "testuser"
    return account


@pytest.fixture
def mock_db():
    """Create mock database session."""
    return MagicMock()


@pytest.fixture
def valid_policy_yaml():
    """Return valid YAML policy content."""
    return """
version: "1.0"
metadata:
  name: "Test Policy"
  description: "A test policy for unit tests"

approval_policies:
  - name: "test-approval"
    timeout_seconds: 300
    require_reason: false
    approvals_required: 1

tools:
  - name: "bash"
    source: "mcp"
    enabled: true
    approval_policy: "test-approval"
    conditions:
      - expression: "args.command.contains('rm ')"
        action: "require_approval"
"""


@pytest.fixture
def invalid_yaml_syntax():
    """Return YAML with syntax error."""
    return """
version: "1.0"
metadata:
  name: "Test Policy
  description: Missing closing quote
"""


@pytest.fixture
def invalid_yaml_missing_field():
    """Return YAML missing required field."""
    return """
version: "1.0"
# Missing required metadata field
approval_policies:
  - name: "test-approval"
"""


@pytest.fixture
def mock_upload_file(valid_policy_yaml):
    """Create mock UploadFile for testing."""

    async def create_file(content: str, filename: str = "policy.yaml"):
        mock_file = MagicMock()
        mock_file.filename = filename
        mock_file.read = MagicMock(return_value=content.encode("utf-8"))

        # Make read() an async function
        async def async_read():
            return content.encode("utf-8")

        mock_file.read = async_read
        return mock_file

    return create_file


class TestValidatePolicy:
    """Test validate_policy endpoint."""

    async def test_validate_valid_yaml(
        self, mock_db, mock_account, valid_policy_yaml, mock_upload_file
    ):
        """Test validating a valid YAML policy file."""
        file = await mock_upload_file(valid_policy_yaml, "policy.yaml")

        result = await policies.validate_policy(
            file=file,
            account=mock_account,
            db=mock_db,
        )

        assert isinstance(result, PolicyValidationResult)
        assert result.is_valid is True
        assert len(result.errors) == 0

    async def test_validate_invalid_yaml_syntax(
        self, mock_db, mock_account, invalid_yaml_syntax, mock_upload_file
    ):
        """Test validating YAML with syntax errors."""
        file = await mock_upload_file(invalid_yaml_syntax, "policy.yaml")

        result = await policies.validate_policy(
            file=file,
            account=mock_account,
            db=mock_db,
        )

        assert isinstance(result, PolicyValidationResult)
        assert result.is_valid is False
        assert len(result.errors) > 0
        # Should contain YAML parsing error
        assert any("YAML" in e.message or "Invalid" in e.message for e in result.errors)

    async def test_validate_missing_required_field(
        self, mock_db, mock_account, invalid_yaml_missing_field, mock_upload_file
    ):
        """Test validating YAML missing required field."""
        file = await mock_upload_file(invalid_yaml_missing_field, "policy.yaml")

        result = await policies.validate_policy(
            file=file,
            account=mock_account,
            db=mock_db,
        )

        assert isinstance(result, PolicyValidationResult)
        assert result.is_valid is False
        assert len(result.errors) > 0
        # Should mention metadata field is required
        assert any("metadata" in e.path.lower() for e in result.errors)

    async def test_validate_non_utf8_file(self, mock_db, mock_account):
        """Test validating non-UTF8 encoded file."""
        mock_file = MagicMock()
        mock_file.filename = "policy.yaml"

        # Return bytes that aren't valid UTF-8
        async def async_read():
            return b"\xff\xfe invalid utf-8"

        mock_file.read = async_read

        with pytest.raises(HTTPException) as exc_info:
            await policies.validate_policy(
                file=mock_file,
                account=mock_account,
                db=mock_db,
            )

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "UTF-8" in exc_info.value.detail


class TestUploadPolicy:
    """Test upload_policy endpoint."""

    async def test_upload_valid_yaml_dry_run(
        self, mock_db, mock_account, valid_policy_yaml, mock_upload_file, mocker
    ):
        """Test uploading valid YAML with dry_run=True."""
        file = await mock_upload_file(valid_policy_yaml, "policy.yaml")

        # Mock the PolicyApplier
        mock_applier_instance = MagicMock()
        mock_applier_instance.apply.return_value = PolicyImportResult(
            success=True,
            policy_name="Test Policy",
            mcp_servers_created=0,
            mcp_servers_updated=0,
            policies_created=1,
            policies_updated=0,
            tools_created=1,
            tools_updated=0,
            warnings=[],
            errors=[],
        )

        mocker.patch(
            "preloop.api.endpoints.policies.PolicyApplier",
            return_value=mock_applier_instance,
        )

        result = await policies.upload_policy(
            file=file,
            dry_run=True,
            resolve_env=True,
            account=mock_account,
            db=mock_db,
        )

        assert isinstance(result, PolicyImportResult)
        assert result.success is True
        assert result.policy_name == "Test Policy"
        assert result.policies_created == 1
        assert result.tools_created == 1

        # Verify dry_run was passed
        mock_applier_instance.apply.assert_called_once()
        call_kwargs = mock_applier_instance.apply.call_args
        assert call_kwargs[1]["dry_run"] is True

    async def test_upload_valid_yaml_apply(
        self, mock_db, mock_account, valid_policy_yaml, mock_upload_file, mocker
    ):
        """Test uploading valid YAML with dry_run=False (actual apply)."""
        file = await mock_upload_file(valid_policy_yaml, "policy.yaml")

        # Mock the PolicyApplier
        mock_applier_instance = MagicMock()
        mock_applier_instance.apply.return_value = PolicyImportResult(
            success=True,
            policy_name="Test Policy",
            mcp_servers_created=0,
            mcp_servers_updated=0,
            policies_created=1,
            policies_updated=0,
            tools_created=1,
            tools_updated=0,
            warnings=[],
            errors=[],
        )

        mocker.patch(
            "preloop.api.endpoints.policies.PolicyApplier",
            return_value=mock_applier_instance,
        )

        result = await policies.upload_policy(
            file=file,
            dry_run=False,
            resolve_env=True,
            account=mock_account,
            db=mock_db,
        )

        assert isinstance(result, PolicyImportResult)
        assert result.success is True

        # Verify dry_run=False was passed
        mock_applier_instance.apply.assert_called_once()
        call_kwargs = mock_applier_instance.apply.call_args
        assert call_kwargs[1]["dry_run"] is False

    async def test_upload_invalid_yaml_returns_error(
        self, mock_db, mock_account, invalid_yaml_syntax, mock_upload_file
    ):
        """Test uploading invalid YAML returns HTTP 400 error."""
        file = await mock_upload_file(invalid_yaml_syntax, "policy.yaml")

        with pytest.raises(HTTPException) as exc_info:
            await policies.upload_policy(
                file=file,
                dry_run=True,
                resolve_env=True,
                account=mock_account,
                db=mock_db,
            )

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "validation failed" in str(exc_info.value.detail).lower()

    async def test_upload_apply_failure_returns_error(
        self, mock_db, mock_account, valid_policy_yaml, mock_upload_file, mocker
    ):
        """Test uploading when apply fails returns HTTP 500 error."""
        file = await mock_upload_file(valid_policy_yaml, "policy.yaml")

        # Mock the PolicyApplier to return failure
        mock_applier_instance = MagicMock()
        mock_applier_instance.apply.return_value = PolicyImportResult(
            success=False,
            policy_name="Test Policy",
            errors=["Database connection failed"],
            warnings=[],
        )

        mocker.patch(
            "preloop.api.endpoints.policies.PolicyApplier",
            return_value=mock_applier_instance,
        )

        with pytest.raises(HTTPException) as exc_info:
            await policies.upload_policy(
                file=file,
                dry_run=False,
                resolve_env=True,
                account=mock_account,
                db=mock_db,
            )

        assert exc_info.value.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


class TestExportPolicy:
    """Test export_policy endpoint."""

    async def test_export_yaml(self, mock_db, mock_account, mocker):
        """Test exporting current configuration as YAML."""
        from preloop.services.policy import (
            PolicyMetadata,
            PolicyVersion,
        )

        # Create a minimal policy document for export
        mock_policy = PolicyDocument(
            version=PolicyVersion.V1_0,
            metadata=PolicyMetadata(
                name="Exported Policy",
                description="Exported from current configuration",
            ),
        )

        mocker.patch(
            "preloop.api.endpoints.policies.export_current_policy",
            return_value=mock_policy,
        )

        result = await policies.export_policy(
            format="yaml",
            policy_name="My Export",
            account=mock_account,
            db=mock_db,
        )

        assert result.media_type == "application/x-yaml"
        assert 'filename="policy.yaml"' in result.headers["Content-Disposition"]

    async def test_export_json(self, mock_db, mock_account, mocker):
        """Test exporting current configuration as JSON."""
        from preloop.services.policy import (
            PolicyMetadata,
            PolicyVersion,
        )

        mock_policy = PolicyDocument(
            version=PolicyVersion.V1_0,
            metadata=PolicyMetadata(
                name="Exported Policy",
                description="Exported from current configuration",
            ),
        )

        mocker.patch(
            "preloop.api.endpoints.policies.export_current_policy",
            return_value=mock_policy,
        )

        result = await policies.export_policy(
            format="json",
            policy_name="My Export",
            account=mock_account,
            db=mock_db,
        )

        assert result.media_type == "application/json"
        assert 'filename="policy.json"' in result.headers["Content-Disposition"]


class TestDiffPolicy:
    """Test diff_policy endpoint."""

    async def test_diff_shows_additions(
        self, mock_db, mock_account, valid_policy_yaml, mock_upload_file, mocker
    ):
        """Test diff shows additions when uploading new policy."""
        file = await mock_upload_file(valid_policy_yaml, "policy.yaml")

        from preloop.services.policy import (
            PolicyDiffResult,
            PolicyMetadata,
            PolicyVersion,
        )

        # Mock current policy (empty)
        mock_current = PolicyDocument(
            version=PolicyVersion.V1_0,
            metadata=PolicyMetadata(name="Current Configuration"),
        )

        mocker.patch(
            "preloop.api.endpoints.policies.export_current_policy",
            return_value=mock_current,
        )

        # Mock compute_policy_diff to return expected diff
        mock_diff = PolicyDiffResult(
            has_changes=True,
            changes=[],
            summary="1 addition(s)",
        )

        mocker.patch(
            "preloop.api.endpoints.policies.compute_policy_diff",
            return_value=mock_diff,
        )

        result = await policies.diff_policy(
            file=file,
            account=mock_account,
            db=mock_db,
        )

        assert isinstance(result, PolicyDiffResult)
        assert result.has_changes is True

    async def test_diff_invalid_yaml_returns_error(
        self, mock_db, mock_account, invalid_yaml_syntax, mock_upload_file
    ):
        """Test diff with invalid YAML returns HTTP 400 error."""
        file = await mock_upload_file(invalid_yaml_syntax, "policy.yaml")

        with pytest.raises(HTTPException) as exc_info:
            await policies.diff_policy(
                file=file,
                account=mock_account,
                db=mock_db,
            )

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST


class TestGetPolicySchema:
    """Test get_policy_schema endpoint."""

    async def test_returns_json_schema(self):
        """Test that endpoint returns valid JSON schema."""
        result = await policies.get_policy_schema()

        assert isinstance(result, dict)
        assert "$schema" in result
        assert "title" in result
        assert result["title"] == "Preloop Policy Schema"
        # Should have definitions/properties for PolicyDocument
        assert "properties" in result or "$defs" in result


class TestPolicyValidationWithConditions:
    """Test policy validation with various condition expressions."""

    async def test_validate_policy_with_complex_conditions(
        self, mock_db, mock_account, mock_upload_file
    ):
        """Test validating policy with complex CEL conditions."""
        yaml_content = """
version: "1.0"
metadata:
  name: "Complex Policy"
  description: "Policy with complex conditions"

approval_policies:
  - name: "complex-approval"
    timeout_seconds: 600
    require_reason: true
    approvals_required: 2

tools:
  - name: "bash"
    source: "mcp"
    enabled: true
    approval_policy: "complex-approval"
    conditions:
      - expression: "args.command.contains('rm ') || args.command.contains('sudo ')"
        action: "require_approval"
        description: "Destructive or privileged commands"
      - expression: "args.command.startsWith('/etc/')"
        action: "deny"
        description: "System config access"
"""
        file = await mock_upload_file(yaml_content, "complex.yaml")

        result = await policies.validate_policy(
            file=file,
            account=mock_account,
            db=mock_db,
        )

        assert result.is_valid is True
        assert len(result.errors) == 0

    async def test_validate_policy_with_invalid_reference(
        self, mock_db, mock_account, mock_upload_file
    ):
        """Test validating policy with invalid approval_policy reference."""
        yaml_content = """
version: "1.0"
metadata:
  name: "Invalid Reference Policy"

tools:
  - name: "bash"
    source: "mcp"
    enabled: true
    approval_policy: "nonexistent-policy"  # This policy doesn't exist
"""
        file = await mock_upload_file(yaml_content, "invalid_ref.yaml")

        result = await policies.validate_policy(
            file=file,
            account=mock_account,
            db=mock_db,
        )

        assert result.is_valid is False
        assert len(result.errors) > 0
        # Should mention the unknown policy
        assert any("nonexistent-policy" in e.message for e in result.errors)
