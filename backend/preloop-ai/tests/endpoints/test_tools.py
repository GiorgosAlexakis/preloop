"""Tests for tools API endpoints."""

import uuid
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException, status

from preloop_ai.api.endpoints import tools
from preloop_ai.schemas.auth import UserResponse
from preloop_models.models.account import Account
from preloop_models.models.mcp_server import MCPServer
from preloop_models.models.mcp_tool import MCPTool
from preloop_models.models.tool_configuration import ApprovalPolicy, ToolConfiguration
from preloop_models.schemas.tool_configuration import (
    ApprovalPolicyCreate,
    ApprovalPolicyResponse,
    ApprovalPolicyUpdate,
    ToolConfigurationCreate,
    ToolConfigurationResponse,
    ToolConfigurationUpdate,
)

pytestmark = pytest.mark.asyncio


@pytest.fixture
def mock_user():
    """Create mock user for testing."""
    return UserResponse(
        username="testuser",
        email="test@example.com",
        email_verified=True,
        full_name="Test User",
    )


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


class TestListAllTools:
    """Test list_all_tools endpoint."""

    async def test_list_tools_with_no_configs(
        self, mock_db, mock_user, mock_account, mocker
    ):
        """Test listing tools when no configurations exist."""
        # Mock CRUD operations
        mocker.patch(
            "preloop_ai.api.endpoints.tools.crud_tool_configuration.get_multi_by_account",
            return_value=[],
        )
        mocker.patch(
            "preloop_ai.api.endpoints.tools.crud_mcp_server.get_active_by_account",
            return_value=[],
        )

        result = await tools.list_all_tools(account=mock_account, db=mock_db)

        # Should return all builtin tools with defaults
        assert len(result) == len(tools.BUILTIN_TOOLS)
        assert all(tool["source"] == "builtin" for tool in result)
        assert all(tool["is_enabled"] is True for tool in result)

    async def test_list_tools_with_configs(
        self, mock_db, mock_user, mock_account, mocker
    ):
        """Test listing tools with existing configurations."""
        # Create mock tool configuration
        policy_id = uuid.uuid4()
        config = MagicMock(spec=ToolConfiguration)
        config.id = uuid.uuid4()
        config.tool_name = "get_issue"
        config.tool_source = "builtin"
        config.mcp_server_id = None
        config.is_enabled = False
        config.approval_policy_id = policy_id

        # Mock CRUD operations
        mocker.patch(
            "preloop_ai.api.endpoints.tools.crud_tool_configuration.get_multi_by_account",
            return_value=[config],
        )
        mocker.patch(
            "preloop_ai.api.endpoints.tools.crud_mcp_server.get_active_by_account",
            return_value=[],
        )

        result = await tools.list_all_tools(account=mock_account, db=mock_db)

        # Find the configured tool
        get_issue_tool = next(t for t in result if t["name"] == "get_issue")
        assert get_issue_tool["is_enabled"] is False
        assert get_issue_tool["approval_policy_id"] == str(policy_id)

    async def test_list_tools_with_mcp_servers(
        self, mock_db, mock_user, mock_account, mocker
    ):
        """Test listing tools including MCP server tools."""
        # Create mock MCP server and tools
        server_id = uuid.uuid4()
        mcp_server = MagicMock(spec=MCPServer)
        mcp_server.id = server_id
        mcp_server.name = "Test MCP Server"
        mcp_server.status = "active"

        mcp_tool = MagicMock(spec=MCPTool)
        mcp_tool.name = "custom_tool"
        mcp_tool.description = "A custom MCP tool"
        mcp_tool.input_schema = {"type": "object", "properties": {}}

        # Mock CRUD operations
        mocker.patch(
            "preloop_ai.api.endpoints.tools.crud_tool_configuration.get_multi_by_account",
            return_value=[],
        )
        mocker.patch(
            "preloop_ai.api.endpoints.tools.crud_mcp_server.get_active_by_account",
            return_value=[mcp_server],
        )
        mocker.patch(
            "preloop_ai.api.endpoints.tools.crud_mcp_tool.get_by_server",
            return_value=[mcp_tool],
        )

        result = await tools.list_all_tools(account=mock_account, db=mock_db)

        # Should have builtin tools + MCP tool
        assert len(result) == len(tools.BUILTIN_TOOLS) + 1

        # Check MCP tool is included
        custom_tool = next(t for t in result if t["name"] == "custom_tool")
        assert custom_tool["source"] == "mcp"
        assert custom_tool["source_id"] == str(server_id)
        assert custom_tool["source_name"] == "Test MCP Server"
        assert custom_tool["description"] == "A custom MCP tool"


class TestToolConfigurationEndpoints:
    """Test tool configuration CRUD endpoints."""

    async def test_create_tool_configuration_success(
        self, mock_db, mock_user, mock_account, mocker
    ):
        """Test creating a new tool configuration."""
        config_data = ToolConfigurationCreate(
            tool_name="get_issue",
            tool_source="builtin",
            account_id=str(mock_account.id),
            is_enabled=False,
        )

        # Mock no existing config
        mocker.patch(
            "preloop_ai.api.endpoints.tools.crud_tool_configuration.get_multi_by_account",
            return_value=[],
        )

        # Mock db.refresh to set database-generated fields
        def mock_refresh(obj):
            obj.id = uuid.uuid4()
            from datetime import datetime, UTC

            obj.created_at = datetime.now(UTC)
            obj.updated_at = datetime.now(UTC)

        mock_db.refresh.side_effect = mock_refresh

        result = await tools.create_tool_configuration(
            config_data=config_data,
            account=mock_account,
            db=mock_db,
        )

        assert isinstance(result, ToolConfigurationResponse)
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    async def test_create_tool_configuration_already_exists(
        self, mock_db, mock_user, mock_account, mocker
    ):
        """Test creating tool configuration that already exists."""
        config_data = ToolConfigurationCreate(
            tool_name="get_issue",
            tool_source="builtin",
            account_id=str(mock_account.id),
        )

        # Mock existing config
        existing_config = MagicMock(spec=ToolConfiguration)
        existing_config.tool_name = "get_issue"
        existing_config.tool_source = "builtin"
        existing_config.mcp_server_id = None

        mocker.patch(
            "preloop_ai.api.endpoints.tools.crud_tool_configuration.get_multi_by_account",
            return_value=[existing_config],
        )

        with pytest.raises(HTTPException) as exc_info:
            await tools.create_tool_configuration(
                config_data=config_data,
                account=mock_account,
                db=mock_db,
            )

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "already exists" in exc_info.value.detail

    async def test_create_tool_configuration_race_condition(
        self, mock_db, mock_user, mock_account, mocker
    ):
        """Test creating tool configuration with race condition (IntegrityError).

        The endpoint should be idempotent - if a race condition causes IntegrityError,
        it should fetch and return the existing config instead of failing.
        """
        from sqlalchemy.exc import IntegrityError

        config_data = ToolConfigurationCreate(
            tool_name="get_issue",
            tool_source="builtin",
            account_id=str(mock_account.id),
        )

        # Mock no existing config in the pre-check
        mocker.patch(
            "preloop_ai.api.endpoints.tools.crud_tool_configuration.get_multi_by_account",
            return_value=[],
        )

        # Create mock existing config that will be returned after IntegrityError
        mock_existing_config = MagicMock()
        mock_existing_config.id = uuid.uuid4()
        mock_existing_config.account_id = mock_account.id
        mock_existing_config.tool_name = "get_issue"
        mock_existing_config.tool_source = "builtin"
        mock_existing_config.is_enabled = True
        mock_existing_config.mcp_server_id = None
        mock_existing_config.http_endpoint_id = None
        mock_existing_config.approval_policy_id = None
        mock_existing_config.tool_description = None
        mock_existing_config.tool_schema = None
        mock_existing_config.custom_config = None

        # Mock IntegrityError on commit (race condition)
        mock_db.commit.side_effect = IntegrityError(
            "statement", "params", "orig", connection_invalidated=False
        )

        # Mock the fetch of existing config after IntegrityError
        mocker.patch(
            "preloop_ai.api.endpoints.tools.crud_tool_configuration.get_by_tool_name_and_source",
            return_value=mock_existing_config,
        )

        # Should succeed and return existing config (idempotent)
        result = await tools.create_tool_configuration(
            config_data=config_data,
            account=mock_account,
            db=mock_db,
        )

        # Verify idempotent behavior - should return existing config
        assert result.tool_name == "get_issue"
        mock_db.rollback.assert_called_once()

    async def test_get_tool_configuration_success(
        self, mock_db, mock_user, mock_account, mocker
    ):
        """Test getting a tool configuration."""
        config_id = uuid.uuid4()
        config = MagicMock(spec=ToolConfiguration)
        config.id = config_id
        config.account_id = str(mock_account.id)
        config.tool_name = "get_issue"
        config.tool_source = "builtin"
        config.mcp_server_id = None
        config.http_endpoint_id = None
        config.approval_policy_id = None
        config.is_enabled = True
        config.tool_description = None
        config.tool_schema = None
        config.custom_config = None
        from datetime import datetime, UTC

        config.created_at = datetime.now(UTC)
        config.updated_at = datetime.now(UTC)

        mocker.patch(
            "preloop_ai.api.endpoints.tools.crud_tool_configuration.get",
            return_value=config,
        )

        result = await tools.get_tool_configuration(
            config_id=config_id,
            account=mock_account,
            db=mock_db,
        )

        assert isinstance(result, ToolConfigurationResponse)

    async def test_get_tool_configuration_not_found(
        self, mock_db, mock_user, mock_account, mocker
    ):
        """Test getting non-existent tool configuration."""
        config_id = uuid.uuid4()

        mocker.patch(
            "preloop_ai.api.endpoints.tools.crud_tool_configuration.get",
            return_value=None,
        )

        with pytest.raises(HTTPException) as exc_info:
            await tools.get_tool_configuration(
                config_id=config_id,
                account=mock_account,
                db=mock_db,
            )

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND

    async def test_update_tool_configuration_success(
        self, mock_db, mock_user, mock_account, mocker
    ):
        """Test updating a tool configuration."""
        config_id = uuid.uuid4()
        config = MagicMock(spec=ToolConfiguration)
        config.id = config_id
        config.account_id = str(mock_account.id)
        config.tool_name = "get_issue"
        config.tool_source = "builtin"
        config.mcp_server_id = None
        config.http_endpoint_id = None
        config.approval_policy_id = None
        config.is_enabled = True
        config.tool_description = None
        config.tool_schema = None
        config.custom_config = None
        from datetime import datetime, UTC

        config.created_at = datetime.now(UTC)
        config.updated_at = datetime.now(UTC)

        mocker.patch(
            "preloop_ai.api.endpoints.tools.crud_tool_configuration.get",
            return_value=config,
        )

        update_data = ToolConfigurationUpdate(is_enabled=False)

        result = await tools.update_tool_configuration(
            config_id=config_id,
            config_update=update_data,
            account=mock_account,
            db=mock_db,
        )

        assert isinstance(result, ToolConfigurationResponse)
        mock_db.commit.assert_called_once()

    async def test_delete_tool_configuration_success(
        self, mock_db, mock_user, mock_account, mocker
    ):
        """Test deleting a tool configuration."""
        config_id = uuid.uuid4()
        config = MagicMock(spec=ToolConfiguration)

        mocker.patch(
            "preloop_ai.api.endpoints.tools.crud_tool_configuration.get",
            return_value=config,
        )

        result = await tools.delete_tool_configuration(
            config_id=config_id,
            account=mock_account,
            db=mock_db,
        )

        assert "message" in result
        mock_db.delete.assert_called_once_with(config)
        mock_db.commit.assert_called_once()


class TestApprovalPolicyEndpoints:
    """Test approval policy CRUD endpoints."""

    async def test_list_approval_policies(
        self, mock_db, mock_user, mock_account, mocker
    ):
        """Test listing approval policies."""
        policy = MagicMock(spec=ApprovalPolicy)
        policy.id = uuid.uuid4()
        policy.account_id = str(mock_account.id)
        policy.name = "Test Policy"
        policy.description = "Test description"
        policy.approval_type = "slack"
        policy.channel = "#approvals"
        policy.user = None
        policy.approval_config = {}
        policy.timeout_seconds = 300
        policy.require_reason = False
        policy.is_default = False
        policy.workflow_type = "simple"
        policy.workflow_config = None
        policy.approver_user_ids = None
        policy.approver_team_ids = None
        policy.approvals_required = 1
        policy.escalation_user_ids = None
        policy.escalation_team_ids = None
        policy.notification_channels = ["email"]
        policy.channel_configs = None
        from datetime import datetime, UTC

        policy.created_at = datetime.now(UTC)
        policy.updated_at = datetime.now(UTC)

        mocker.patch(
            "preloop_ai.api.endpoints.tools.crud_approval_policy.get_multi_by_account",
            return_value=[policy],
        )

        result = await tools.list_approval_policies(
            account=mock_account,
            db=mock_db,
        )

        assert isinstance(result, list)
        assert len(result) == 1

    async def test_create_approval_policy_success(
        self, mock_db, mock_user, mock_account, mocker
    ):
        """Test creating an approval policy."""
        policy_data = ApprovalPolicyCreate(
            name="Test Policy",
            approval_type="slack",
            channel="#approvals",
        )

        # Mock no existing policy with same name
        mocker.patch(
            "preloop_ai.api.endpoints.tools.crud_approval_policy.get_by_name",
            return_value=None,
        )

        # Mock the created policy
        created_policy = MagicMock(spec=ApprovalPolicy)
        created_policy.id = uuid.uuid4()
        created_policy.account_id = str(mock_account.id)
        created_policy.name = policy_data.name
        created_policy.description = None
        created_policy.approval_type = policy_data.approval_type
        created_policy.channel = policy_data.channel
        created_policy.user = None
        created_policy.approval_config = None
        created_policy.timeout_seconds = 300
        created_policy.require_reason = False
        created_policy.is_default = True  # First policy becomes default
        created_policy.workflow_type = "simple"
        created_policy.workflow_config = None
        created_policy.approver_user_ids = None
        created_policy.approver_team_ids = None
        created_policy.approvals_required = 1
        created_policy.escalation_user_ids = None
        created_policy.escalation_team_ids = None
        created_policy.notification_channels = ["email"]
        created_policy.channel_configs = None
        from datetime import datetime, UTC

        created_policy.created_at = datetime.now(UTC)
        created_policy.updated_at = datetime.now(UTC)

        # Mock crud_approval_policy.create
        mocker.patch(
            "preloop_ai.api.endpoints.tools.crud_approval_policy.create",
            return_value=created_policy,
        )

        result = await tools.create_approval_policy(
            policy_data=policy_data,
            account=mock_account,
            db=mock_db,
        )

        assert isinstance(result, ApprovalPolicyResponse)
        assert result.name == policy_data.name
        assert result.is_default

    async def test_create_approval_policy_duplicate_name(
        self, mock_db, mock_user, mock_account, mocker
    ):
        """Test creating approval policy with duplicate name."""
        policy_data = ApprovalPolicyCreate(
            name="Test Policy",
            approval_type="slack",
            channel="#approvals",
        )

        # Mock existing policy
        existing_policy = MagicMock(spec=ApprovalPolicy)

        mocker.patch(
            "preloop_ai.api.endpoints.tools.crud_approval_policy.get_by_name",
            return_value=existing_policy,
        )

        with pytest.raises(HTTPException) as exc_info:
            await tools.create_approval_policy(
                policy_data=policy_data,
                account=mock_account,
                db=mock_db,
            )

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
        assert "already exists" in exc_info.value.detail

    async def test_get_approval_policy_success(
        self, mock_db, mock_user, mock_account, mocker
    ):
        """Test getting an approval policy."""
        policy_id = uuid.uuid4()
        policy = MagicMock(spec=ApprovalPolicy)
        policy.id = policy_id
        policy.account_id = str(mock_account.id)
        policy.name = "Test Policy"
        policy.description = "Test description"
        policy.approval_type = "slack"
        policy.channel = "#approvals"
        policy.user = None
        policy.approval_config = {}
        policy.timeout_seconds = 300
        policy.require_reason = False
        policy.is_default = False
        policy.workflow_type = "simple"
        policy.workflow_config = None
        policy.approver_user_ids = None
        policy.approver_team_ids = None
        policy.approvals_required = 1
        policy.escalation_user_ids = None
        policy.escalation_team_ids = None
        policy.notification_channels = ["email"]
        policy.channel_configs = None
        from datetime import datetime, UTC

        policy.created_at = datetime.now(UTC)
        policy.updated_at = datetime.now(UTC)

        mocker.patch(
            "preloop_ai.api.endpoints.tools.crud_approval_policy.get",
            return_value=policy,
        )

        result = await tools.get_approval_policy(
            policy_id=policy_id,
            account=mock_account,
            db=mock_db,
        )

        assert isinstance(result, ApprovalPolicyResponse)

    async def test_update_approval_policy_success(
        self, mock_db, mock_user, mock_account, mocker
    ):
        """Test updating an approval policy."""
        policy_id = uuid.uuid4()
        policy = MagicMock(spec=ApprovalPolicy)
        policy.id = policy_id
        policy.account_id = str(mock_account.id)
        policy.name = "Old Name"
        policy.description = "Test description"
        policy.approval_type = "slack"
        policy.channel = "#approvals"
        policy.user = None
        policy.approval_config = {}
        policy.timeout_seconds = 300
        policy.require_reason = False
        policy.is_default = False
        policy.workflow_type = "simple"
        policy.workflow_config = None
        policy.approver_user_ids = None
        policy.approver_team_ids = None
        policy.approvals_required = 1
        policy.escalation_user_ids = None
        policy.escalation_team_ids = None
        policy.notification_channels = ["email"]
        policy.channel_configs = None
        from datetime import datetime, UTC

        policy.created_at = datetime.now(UTC)
        policy.updated_at = datetime.now(UTC)

        # Mock the get method to return policy
        mocker.patch(
            "preloop_ai.api.endpoints.tools.crud_approval_policy.get",
            return_value=policy,
        )

        # Mock the get_by_name method for duplicate check (no duplicate with new name)
        mocker.patch(
            "preloop_ai.api.endpoints.tools.crud_approval_policy.get_by_name",
            return_value=None,
        )

        # Mock the update method to return the updated policy
        mocker.patch(
            "preloop_ai.api.endpoints.tools.crud_approval_policy.update",
            return_value=policy,
        )

        update_data = ApprovalPolicyUpdate(name="New Name")

        result = await tools.update_approval_policy(
            policy_id=policy_id,
            policy_update=update_data,
            account=mock_account,
            db=mock_db,
        )

        assert isinstance(result, ApprovalPolicyResponse)

    async def test_delete_approval_policy_success(
        self, mock_db, mock_user, mock_account, mocker
    ):
        """Test deleting an approval policy."""
        policy_id = uuid.uuid4()
        policy = MagicMock(spec=ApprovalPolicy)
        policy.id = policy_id

        # Mock policy lookup
        mocker.patch(
            "preloop_ai.api.endpoints.tools.crud_approval_policy.get",
            return_value=policy,
        )

        # Mock tool count query
        mocker.patch(
            "preloop_ai.api.endpoints.tools.crud_tool_configuration.count_by_policy",
            return_value=2,
        )

        # Mock crud_approval_policy.remove (which handles the actual deletion)
        mocker.patch(
            "preloop_ai.api.endpoints.tools.crud_approval_policy.remove",
            return_value=policy,
        )

        result = await tools.delete_approval_policy(
            policy_id=policy_id,
            account=mock_account,
            db=mock_db,
        )

        assert "message" in result
        assert "2 tool(s)" in result["message"]
