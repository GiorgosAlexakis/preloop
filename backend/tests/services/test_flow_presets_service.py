"""Tests for flow presets service."""

import uuid
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from preloop.services.flow_presets_service import (
    PresetSyncResult,
    apply_preset_update_to_flow,
    compute_content_hash,
    create_default_presets_for_account,
    create_default_presets_for_account_background,
    dismiss_preset_update,
    ensure_global_presets_exist,
    ensure_global_presets_exist_background,
    get_preset_by_name,
    get_preset_names,
    sync_all_presets,
    sync_all_presets_background,
    sync_preset_to_derived_flows,
)


class TestComputeContentHash:
    """Tests for compute_content_hash function."""

    def test_hash_string(self):
        """Test hashing a string returns consistent 16-char hash."""
        content = "This is a test prompt"
        result = compute_content_hash(content)

        assert isinstance(result, str)
        assert len(result) == 16
        # Hash should be consistent
        assert compute_content_hash(content) == result

    def test_hash_different_strings_different_hashes(self):
        """Test different strings produce different hashes."""
        hash1 = compute_content_hash("prompt one")
        hash2 = compute_content_hash("prompt two")

        assert hash1 != hash2

    def test_hash_list(self):
        """Test hashing a list."""
        content = ["tool1", "tool2", "tool3"]
        result = compute_content_hash(content)

        assert isinstance(result, str)
        assert len(result) == 16

    def test_hash_dict(self):
        """Test hashing a dictionary."""
        content = {"key1": "value1", "key2": 123}
        result = compute_content_hash(content)

        assert isinstance(result, str)
        assert len(result) == 16

    def test_hash_dict_order_independent(self):
        """Test that dict hash is consistent regardless of key order."""
        dict1 = {"a": 1, "b": 2}
        dict2 = {"b": 2, "a": 1}

        assert compute_content_hash(dict1) == compute_content_hash(dict2)

    def test_hash_empty_list(self):
        """Test hashing an empty list."""
        result = compute_content_hash([])

        assert isinstance(result, str)
        assert len(result) == 16

    def test_hash_empty_string(self):
        """Test hashing an empty string."""
        result = compute_content_hash("")

        assert isinstance(result, str)
        assert len(result) == 16


class TestGetPresetNames:
    """Tests for get_preset_names function."""

    @patch("preloop.services.flow_presets_service.FLOW_PRESETS")
    def test_get_preset_names_returns_names(self, mock_presets):
        """Test that preset names are returned correctly."""
        mock_presets.__iter__ = lambda self: iter(
            [
                {"name": "Preset One", "description": "desc1"},
                {"name": "Preset Two", "description": "desc2"},
            ]
        )

        result = get_preset_names()

        assert result == ["Preset One", "Preset Two"]

    @patch("preloop.services.flow_presets_service.FLOW_PRESETS", [])
    def test_get_preset_names_empty(self):
        """Test getting names when no presets exist."""
        result = get_preset_names()

        assert result == []


class TestGetPresetByName:
    """Tests for get_preset_by_name function."""

    @patch("preloop.services.flow_presets_service.FLOW_PRESETS")
    def test_get_preset_by_name_found(self, mock_presets):
        """Test getting a preset that exists."""
        preset_data = {"name": "Test Preset", "prompt_template": "Hello {{name}}"}
        mock_presets.__iter__ = lambda self: iter([preset_data])

        result = get_preset_by_name("Test Preset")

        assert result is not None
        assert result["name"] == "Test Preset"
        assert result["prompt_template"] == "Hello {{name}}"

    @patch("preloop.services.flow_presets_service.FLOW_PRESETS")
    def test_get_preset_by_name_not_found(self, mock_presets):
        """Test getting a preset that doesn't exist."""
        mock_presets.__iter__ = lambda self: iter(
            [
                {"name": "Other Preset", "prompt_template": "test"},
            ]
        )

        result = get_preset_by_name("Nonexistent Preset")

        assert result is None

    @patch("preloop.services.flow_presets_service.FLOW_PRESETS")
    def test_get_preset_by_name_returns_copy(self, mock_presets):
        """Test that get_preset_by_name returns a copy, not the original."""
        original_preset = {"name": "Test Preset", "data": "value"}
        mock_presets.__iter__ = lambda self: iter([original_preset])

        result = get_preset_by_name("Test Preset")
        result["data"] = "modified"

        # Original should be unchanged
        assert original_preset["data"] == "value"


class TestEnsureGlobalPresetsExist:
    """Tests for ensure_global_presets_exist function."""

    @patch("preloop.services.flow_presets_service.schemas.FlowCreate")
    @patch("preloop.services.flow_presets_service.crud_flow")
    @patch("preloop.services.flow_presets_service.FLOW_PRESETS")
    def test_ensure_global_presets_creates_missing(
        self, mock_presets, mock_crud, mock_flow_create
    ):
        """Test that missing presets are created."""
        mock_db = MagicMock(spec=Session)
        mock_presets.__iter__ = lambda self: iter(
            [
                {
                    "name": "New Preset",
                    "prompt_template": "test prompt",
                    "agent_config": {},
                },
            ]
        )

        # Preset doesn't exist yet
        mock_crud.get_global_preset_by_name.return_value = None

        # Mock flow creation
        mock_flow = MagicMock()
        mock_flow.name = "New Preset"
        mock_crud.create.return_value = mock_flow

        result = ensure_global_presets_exist(mock_db)

        assert len(result) == 1
        assert mock_crud.create.called

    @patch("preloop.services.flow_presets_service.crud_flow")
    @patch("preloop.services.flow_presets_service.FLOW_PRESETS")
    def test_ensure_global_presets_skips_existing(self, mock_presets, mock_crud):
        """Test that existing presets are skipped."""
        mock_db = MagicMock(spec=Session)
        mock_presets.__iter__ = lambda self: iter(
            [
                {"name": "Existing Preset", "prompt_template": "test"},
            ]
        )

        # Preset already exists
        existing_flow = MagicMock()
        existing_flow.name = "Existing Preset"
        mock_crud.get_global_preset_by_name.return_value = existing_flow

        result = ensure_global_presets_exist(mock_db)

        assert len(result) == 0
        assert not mock_crud.create.called

    @patch("preloop.services.flow_presets_service.schemas.FlowCreate")
    @patch("preloop.services.flow_presets_service.crud_flow")
    @patch("preloop.services.flow_presets_service.FLOW_PRESETS")
    def test_ensure_global_presets_handles_creation_error(
        self, mock_presets, mock_crud, mock_flow_create
    ):
        """Test that creation errors are handled gracefully."""
        mock_db = MagicMock(spec=Session)
        mock_presets.__iter__ = lambda self: iter(
            [
                {"name": "Preset 1", "prompt_template": "test1", "agent_config": {}},
                {"name": "Preset 2", "prompt_template": "test2", "agent_config": {}},
            ]
        )

        mock_crud.get_global_preset_by_name.return_value = None

        # First creation fails, second succeeds
        mock_flow = MagicMock()
        mock_flow.name = "Preset 2"
        mock_crud.create.side_effect = [Exception("DB Error"), mock_flow]

        result = ensure_global_presets_exist(mock_db)

        # Should still return the successful one
        assert len(result) == 1

    @patch("preloop.services.flow_presets_service.schemas.FlowCreate")
    @patch("preloop.services.flow_presets_service.crud_flow")
    @patch("preloop.services.flow_presets_service.FLOW_PRESETS")
    def test_ensure_global_presets_sets_is_preset_flag(
        self, mock_presets, mock_crud, mock_flow_create
    ):
        """Test that created presets have is_preset=True."""
        mock_db = MagicMock(spec=Session)
        mock_presets.__iter__ = lambda self: iter(
            [
                {"name": "Test Preset", "prompt_template": "test", "agent_config": {}},
            ]
        )

        mock_crud.get_global_preset_by_name.return_value = None
        mock_flow = MagicMock()
        mock_crud.create.return_value = mock_flow

        ensure_global_presets_exist(mock_db)

        # Check that FlowCreate was called with is_preset=True
        assert mock_flow_create.called
        call_kwargs = mock_flow_create.call_args[1]
        assert call_kwargs.get("is_preset") is True
        assert call_kwargs.get("is_enabled") is False


class TestCreateDefaultPresetsForAccount:
    """Tests for deprecated create_default_presets_for_account function."""

    @patch("preloop.services.flow_presets_service.ensure_global_presets_exist")
    def test_calls_ensure_global_presets(self, mock_ensure):
        """Test that it calls ensure_global_presets_exist."""
        mock_db = MagicMock(spec=Session)
        account_id = uuid.uuid4()
        mock_ensure.return_value = []

        result = create_default_presets_for_account(mock_db, account_id)

        mock_ensure.assert_called_once_with(mock_db)
        assert result == []


class TestEnsureGlobalPresetsExistBackground:
    """Tests for ensure_global_presets_exist_background function."""

    @patch("preloop.services.flow_presets_service.get_session_factory")
    @patch("preloop.services.flow_presets_service.ensure_global_presets_exist")
    def test_creates_own_session(self, mock_ensure, mock_get_factory):
        """Test that it creates its own database session."""
        mock_session = MagicMock(spec=Session)
        mock_factory = MagicMock()
        mock_factory.return_value = mock_session
        mock_get_factory.return_value = mock_factory
        mock_ensure.return_value = []

        ensure_global_presets_exist_background()

        mock_factory.assert_called_once()
        mock_ensure.assert_called_once_with(db=mock_session)
        mock_session.commit.assert_called_once()
        mock_session.close.assert_called_once()

    @patch("preloop.services.flow_presets_service.get_session_factory")
    @patch("preloop.services.flow_presets_service.ensure_global_presets_exist")
    def test_handles_error_with_rollback(self, mock_ensure, mock_get_factory):
        """Test that errors are handled with rollback."""
        mock_session = MagicMock(spec=Session)
        mock_factory = MagicMock()
        mock_factory.return_value = mock_session
        mock_get_factory.return_value = mock_factory
        mock_ensure.side_effect = Exception("DB Error")

        ensure_global_presets_exist_background()

        mock_session.rollback.assert_called_once()
        mock_session.close.assert_called_once()


class TestCreateDefaultPresetsForAccountBackground:
    """Tests for deprecated create_default_presets_for_account_background function."""

    @patch(
        "preloop.services.flow_presets_service.ensure_global_presets_exist_background"
    )
    def test_calls_ensure_global_presets_background(self, mock_ensure):
        """Test that it calls ensure_global_presets_exist_background."""
        account_id = uuid.uuid4()

        create_default_presets_for_account_background(account_id)

        mock_ensure.assert_called_once()


class TestSyncPresetToDerivedFlows:
    """Tests for sync_preset_to_derived_flows function."""

    @patch("preloop.services.flow_presets_service.crud_flow")
    def test_raises_error_if_preset_not_found(self, mock_crud):
        """Test that error is raised if preset doesn't exist."""
        mock_db = MagicMock(spec=Session)
        preset_id = uuid.uuid4()
        mock_crud.get.return_value = None

        with pytest.raises(ValueError, match="not found"):
            sync_preset_to_derived_flows(mock_db, preset_id)

    @patch("preloop.services.flow_presets_service.crud_flow")
    def test_raises_error_if_not_preset(self, mock_crud):
        """Test that error is raised if flow is not a preset."""
        mock_db = MagicMock(spec=Session)
        preset_id = uuid.uuid4()

        mock_flow = MagicMock()
        mock_flow.is_preset = False
        mock_crud.get.return_value = mock_flow

        with pytest.raises(ValueError, match="not found or is not a preset"):
            sync_preset_to_derived_flows(mock_db, preset_id)

    @patch("preloop.services.flow_presets_service.crud_flow")
    def test_sync_auto_updates_non_customized_flows(self, mock_crud):
        """Test that non-customized flows are auto-updated."""
        mock_db = MagicMock(spec=Session)
        preset_id = uuid.uuid4()

        # Create mock preset
        mock_preset = MagicMock()
        mock_preset.id = preset_id
        mock_preset.name = "Test Preset"
        mock_preset.is_preset = True
        mock_preset.prompt_template = "New prompt"
        mock_preset.allowed_mcp_tools = ["tool1", "tool2"]
        mock_crud.get.return_value = mock_preset

        # Create mock derived flow that needs update
        mock_flow = MagicMock()
        mock_flow.id = uuid.uuid4()
        mock_flow.name = "Derived Flow"
        mock_flow.source_prompt_hash = "old_hash"
        mock_flow.source_tools_hash = "old_hash"
        mock_flow.prompt_customized = False
        mock_flow.tools_customized = False

        # Mock query for derived flows
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_flow]

        result = sync_preset_to_derived_flows(mock_db, preset_id)

        assert isinstance(result, PresetSyncResult)
        assert result.preset_id == preset_id
        assert result.preset_name == "Test Preset"
        assert result.auto_updated == 1
        assert result.skipped == 0
        assert result.notified == 0
        mock_db.commit.assert_called_once()

    @patch("preloop.services.flow_presets_service.crud_flow")
    def test_sync_notifies_customized_flows(self, mock_crud):
        """Test that customized flows get notifications."""
        mock_db = MagicMock(spec=Session)
        preset_id = uuid.uuid4()

        mock_preset = MagicMock()
        mock_preset.id = preset_id
        mock_preset.name = "Test Preset"
        mock_preset.is_preset = True
        mock_preset.prompt_template = "New prompt"
        mock_preset.allowed_mcp_tools = []
        mock_crud.get.return_value = mock_preset

        # Customized flow
        mock_flow = MagicMock()
        mock_flow.id = uuid.uuid4()
        mock_flow.name = "Customized Flow"
        mock_flow.source_prompt_hash = "old_hash"
        mock_flow.source_tools_hash = compute_content_hash([])  # Tools up to date
        mock_flow.prompt_customized = True
        mock_flow.tools_customized = False
        mock_flow.preset_update_available = False

        mock_db.query.return_value.filter.return_value.all.return_value = [mock_flow]

        result = sync_preset_to_derived_flows(mock_db, preset_id)

        assert result.notified == 1
        assert mock_flow.preset_update_available is True

    @patch("preloop.services.flow_presets_service.crud_flow")
    def test_sync_skips_up_to_date_flows(self, mock_crud):
        """Test that up-to-date flows are skipped."""
        mock_db = MagicMock(spec=Session)
        preset_id = uuid.uuid4()

        mock_preset = MagicMock()
        mock_preset.id = preset_id
        mock_preset.name = "Test Preset"
        mock_preset.is_preset = True
        mock_preset.prompt_template = "Current prompt"
        mock_preset.allowed_mcp_tools = ["tool1"]
        mock_crud.get.return_value = mock_preset

        # Flow already in sync
        prompt_hash = compute_content_hash("Current prompt")
        tools_hash = compute_content_hash(["tool1"])

        mock_flow = MagicMock()
        mock_flow.id = uuid.uuid4()
        mock_flow.source_prompt_hash = prompt_hash
        mock_flow.source_tools_hash = tools_hash

        mock_db.query.return_value.filter.return_value.all.return_value = [mock_flow]

        result = sync_preset_to_derived_flows(mock_db, preset_id)

        assert result.skipped == 1
        assert result.auto_updated == 0

    @patch("preloop.services.flow_presets_service.crud_flow")
    def test_sync_counts_errors(self, mock_crud):
        """Test that errors during sync are counted."""
        mock_db = MagicMock(spec=Session)
        preset_id = uuid.uuid4()

        mock_preset = MagicMock()
        mock_preset.id = preset_id
        mock_preset.name = "Test Preset"
        mock_preset.is_preset = True
        mock_preset.prompt_template = "test"
        mock_preset.allowed_mcp_tools = []
        mock_crud.get.return_value = mock_preset

        # Flow that raises error when accessing attributes
        mock_flow = MagicMock()
        mock_flow.id = uuid.uuid4()
        type(mock_flow).source_prompt_hash = property(
            lambda s: (_ for _ in ()).throw(Exception("Error"))
        )

        mock_db.query.return_value.filter.return_value.all.return_value = [mock_flow]

        result = sync_preset_to_derived_flows(mock_db, preset_id)

        assert result.errors == 1


class TestSyncAllPresets:
    """Tests for sync_all_presets function."""

    @patch("preloop.services.flow_presets_service.sync_preset_to_derived_flows")
    def test_syncs_all_global_presets(self, mock_sync):
        """Test that all global presets are synced."""
        mock_db = MagicMock(spec=Session)

        # Create mock presets
        preset1 = MagicMock()
        preset1.id = uuid.uuid4()
        preset1.name = "Preset 1"

        preset2 = MagicMock()
        preset2.id = uuid.uuid4()
        preset2.name = "Preset 2"

        mock_db.query.return_value.filter.return_value.all.return_value = [
            preset1,
            preset2,
        ]

        mock_sync.return_value = PresetSyncResult(
            preset_id=preset1.id,
            preset_name="test",
            auto_updated=0,
            notified=0,
            skipped=0,
            errors=0,
        )

        results = sync_all_presets(mock_db)

        assert len(results) == 2
        assert mock_sync.call_count == 2

    @patch("preloop.services.flow_presets_service.sync_preset_to_derived_flows")
    def test_handles_sync_errors(self, mock_sync):
        """Test that errors during sync are handled."""
        mock_db = MagicMock(spec=Session)

        preset1 = MagicMock()
        preset1.id = uuid.uuid4()
        preset1.name = "Preset 1"

        mock_db.query.return_value.filter.return_value.all.return_value = [preset1]
        mock_sync.side_effect = Exception("Sync failed")

        results = sync_all_presets(mock_db)

        # Should return empty list when all fail
        assert len(results) == 0


class TestSyncAllPresetsBackground:
    """Tests for sync_all_presets_background function."""

    @patch("preloop.services.flow_presets_service.get_session_factory")
    @patch("preloop.services.flow_presets_service.sync_all_presets")
    def test_creates_own_session(self, mock_sync, mock_get_factory):
        """Test that it creates its own database session."""
        mock_session = MagicMock(spec=Session)
        mock_factory = MagicMock()
        mock_factory.return_value = mock_session
        mock_get_factory.return_value = mock_factory
        mock_sync.return_value = []

        sync_all_presets_background()

        mock_factory.assert_called_once()
        mock_sync.assert_called_once_with(mock_session)
        mock_session.close.assert_called_once()

    @patch("preloop.services.flow_presets_service.get_session_factory")
    @patch("preloop.services.flow_presets_service.sync_all_presets")
    def test_handles_error_with_rollback(self, mock_sync, mock_get_factory):
        """Test that errors are handled with rollback."""
        mock_session = MagicMock(spec=Session)
        mock_factory = MagicMock()
        mock_factory.return_value = mock_session
        mock_get_factory.return_value = mock_factory
        mock_sync.side_effect = Exception("Sync error")

        results = sync_all_presets_background()

        mock_session.rollback.assert_called_once()
        mock_session.close.assert_called_once()
        assert results == []


class TestApplyPresetUpdateToFlow:
    """Tests for apply_preset_update_to_flow function."""

    @patch("preloop.services.flow_presets_service.crud_flow")
    def test_raises_error_if_flow_not_found(self, mock_crud):
        """Test that error is raised if flow doesn't exist."""
        mock_db = MagicMock(spec=Session)
        flow_id = uuid.uuid4()
        mock_crud.get.return_value = None

        with pytest.raises(ValueError, match="not found"):
            apply_preset_update_to_flow(mock_db, flow_id)

    @patch("preloop.services.flow_presets_service.crud_flow")
    def test_raises_error_if_no_source_preset(self, mock_crud):
        """Test that error is raised if flow has no source preset."""
        mock_db = MagicMock(spec=Session)
        flow_id = uuid.uuid4()

        mock_flow = MagicMock()
        mock_flow.source_preset_id = None
        mock_crud.get.return_value = mock_flow

        with pytest.raises(ValueError, match="not linked to a preset"):
            apply_preset_update_to_flow(mock_db, flow_id)

    @patch("preloop.services.flow_presets_service.crud_flow")
    def test_raises_error_if_source_preset_not_found(self, mock_crud):
        """Test that error is raised if source preset doesn't exist."""
        mock_db = MagicMock(spec=Session)
        flow_id = uuid.uuid4()
        preset_id = uuid.uuid4()

        mock_flow = MagicMock()
        mock_flow.source_preset_id = preset_id

        # First call returns flow, second returns None for preset
        mock_crud.get.side_effect = [mock_flow, None]

        with pytest.raises(ValueError, match="Source preset .* not found"):
            apply_preset_update_to_flow(mock_db, flow_id)

    @patch("preloop.services.flow_presets_service.crud_flow")
    def test_raises_error_if_source_is_not_preset(self, mock_crud):
        """Test that error is raised if source flow is not a preset."""
        mock_db = MagicMock(spec=Session)
        flow_id = uuid.uuid4()
        preset_id = uuid.uuid4()

        mock_flow = MagicMock()
        mock_flow.source_preset_id = preset_id
        mock_flow.account_id = uuid.uuid4()

        mock_not_preset = MagicMock()
        mock_not_preset.id = preset_id
        mock_not_preset.is_preset = False  # Not a preset
        mock_not_preset.account_id = None

        mock_crud.get.side_effect = [mock_flow, mock_not_preset]

        with pytest.raises(ValueError, match="is not a preset"):
            apply_preset_update_to_flow(mock_db, flow_id)

    @patch("preloop.services.flow_presets_service.crud_flow")
    def test_raises_error_if_preset_from_different_account(self, mock_crud):
        """Test that error is raised if preset belongs to different account."""
        mock_db = MagicMock(spec=Session)
        flow_id = uuid.uuid4()
        preset_id = uuid.uuid4()
        flow_account_id = uuid.uuid4()
        preset_account_id = uuid.uuid4()  # Different account

        mock_flow = MagicMock()
        mock_flow.source_preset_id = preset_id
        mock_flow.account_id = flow_account_id

        mock_preset = MagicMock()
        mock_preset.id = preset_id
        mock_preset.is_preset = True
        mock_preset.account_id = preset_account_id  # Different account

        mock_crud.get.side_effect = [mock_flow, mock_preset]

        with pytest.raises(ValueError, match="not accessible to this account"):
            apply_preset_update_to_flow(mock_db, flow_id)

    @patch("preloop.services.flow_presets_service.crud_flow")
    def test_allows_same_account_preset(self, mock_crud):
        """Test that preset from same account is allowed."""
        mock_db = MagicMock(spec=Session)
        flow_id = uuid.uuid4()
        preset_id = uuid.uuid4()
        account_id = uuid.uuid4()  # Same account for both

        mock_flow = MagicMock()
        mock_flow.id = flow_id
        mock_flow.name = "Test Flow"
        mock_flow.source_preset_id = preset_id
        mock_flow.account_id = account_id

        mock_preset = MagicMock()
        mock_preset.id = preset_id
        mock_preset.prompt_template = "Updated prompt"
        mock_preset.allowed_mcp_tools = ["tool"]
        mock_preset.name = "Source Preset"
        mock_preset.is_preset = True
        mock_preset.account_id = account_id  # Same account

        mock_crud.get.side_effect = [mock_flow, mock_preset]

        result = apply_preset_update_to_flow(mock_db, flow_id)

        assert result == mock_flow
        mock_db.commit.assert_called_once()

    @patch("preloop.services.flow_presets_service.crud_flow")
    def test_applies_update_successfully(self, mock_crud):
        """Test that preset update is applied correctly."""
        mock_db = MagicMock(spec=Session)
        flow_id = uuid.uuid4()
        preset_id = uuid.uuid4()
        account_id = uuid.uuid4()

        mock_flow = MagicMock()
        mock_flow.id = flow_id
        mock_flow.name = "Test Flow"
        mock_flow.source_preset_id = preset_id
        mock_flow.account_id = account_id
        mock_flow.prompt_customized = True
        mock_flow.tools_customized = True
        mock_flow.preset_update_available = True

        mock_preset = MagicMock()
        mock_preset.id = preset_id
        mock_preset.prompt_template = "Updated prompt"
        mock_preset.allowed_mcp_tools = ["new_tool"]
        mock_preset.name = "Source Preset"
        mock_preset.is_preset = True
        mock_preset.account_id = None  # Global preset

        mock_crud.get.side_effect = [mock_flow, mock_preset]

        result = apply_preset_update_to_flow(mock_db, flow_id)

        assert result == mock_flow
        assert mock_flow.prompt_template == "Updated prompt"
        assert mock_flow.allowed_mcp_tools == ["new_tool"]
        assert mock_flow.prompt_customized is False
        assert mock_flow.tools_customized is False
        assert mock_flow.preset_update_available is False
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once_with(mock_flow)


class TestDismissPresetUpdate:
    """Tests for dismiss_preset_update function."""

    @patch("preloop.services.flow_presets_service.crud_flow")
    def test_raises_error_if_flow_not_found(self, mock_crud):
        """Test that error is raised if flow doesn't exist."""
        mock_db = MagicMock(spec=Session)
        flow_id = uuid.uuid4()
        mock_crud.get.return_value = None

        with pytest.raises(ValueError, match="not found"):
            dismiss_preset_update(mock_db, flow_id)

    @patch("preloop.services.flow_presets_service.crud_flow")
    def test_dismisses_update_successfully(self, mock_crud):
        """Test that update notification is dismissed."""
        mock_db = MagicMock(spec=Session)
        flow_id = uuid.uuid4()

        mock_flow = MagicMock()
        mock_flow.id = flow_id
        mock_flow.preset_update_available = True
        mock_crud.get.return_value = mock_flow

        result = dismiss_preset_update(mock_db, flow_id)

        assert result == mock_flow
        assert mock_flow.preset_update_available is False
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once_with(mock_flow)


class TestComputeContentHashEdgeCases:
    """Additional edge case tests for compute_content_hash function."""

    def test_hash_none_value(self):
        """Test hashing None value."""
        result = compute_content_hash(None)
        assert isinstance(result, str)
        assert len(result) == 16

    def test_hash_nested_dict(self):
        """Test hashing a nested dictionary."""
        content = {
            "level1": {
                "level2": {
                    "level3": "value",
                }
            }
        }
        result = compute_content_hash(content)
        assert isinstance(result, str)
        assert len(result) == 16

    def test_hash_list_of_dicts(self):
        """Test hashing a list of dictionaries."""
        content = [
            {"name": "tool1", "enabled": True},
            {"name": "tool2", "enabled": False},
        ]
        result = compute_content_hash(content)
        assert isinstance(result, str)
        assert len(result) == 16

    def test_hash_with_numeric_values(self):
        """Test hashing content with numeric values."""
        content = {"int": 42, "float": 3.14, "negative": -10}
        result = compute_content_hash(content)
        assert isinstance(result, str)
        assert len(result) == 16

    def test_hash_with_boolean_values(self):
        """Test hashing content with boolean values."""
        content = {"enabled": True, "disabled": False}
        result = compute_content_hash(content)
        assert isinstance(result, str)
        assert len(result) == 16

    def test_hash_unicode_string(self):
        """Test hashing a unicode string."""
        content = "Hello, 世界! 🌍"
        result = compute_content_hash(content)
        assert isinstance(result, str)
        assert len(result) == 16

    def test_hash_very_long_string(self):
        """Test hashing a very long string."""
        content = "x" * 100000
        result = compute_content_hash(content)
        assert isinstance(result, str)
        assert len(result) == 16

    def test_hash_whitespace_sensitivity(self):
        """Test that whitespace differences produce different hashes."""
        hash1 = compute_content_hash("hello world")
        hash2 = compute_content_hash("hello  world")
        hash3 = compute_content_hash("hello\tworld")
        hash4 = compute_content_hash("hello\nworld")

        # All should be different
        assert len({hash1, hash2, hash3, hash4}) == 4


class TestSyncPresetToDerivedFlowsEdgeCases:
    """Additional edge case tests for sync_preset_to_derived_flows function."""

    @patch("preloop.services.flow_presets_service.crud_flow")
    def test_sync_with_no_derived_flows(self, mock_crud):
        """Test syncing a preset with no derived flows."""
        mock_db = MagicMock(spec=Session)
        preset_id = uuid.uuid4()

        mock_preset = MagicMock()
        mock_preset.id = preset_id
        mock_preset.name = "Test Preset"
        mock_preset.is_preset = True
        mock_preset.prompt_template = "test"
        mock_preset.allowed_mcp_tools = []
        mock_crud.get.return_value = mock_preset

        # No derived flows
        mock_db.query.return_value.filter.return_value.all.return_value = []

        result = sync_preset_to_derived_flows(mock_db, preset_id)

        assert result.auto_updated == 0
        assert result.notified == 0
        assert result.skipped == 0
        assert result.errors == 0
        mock_db.commit.assert_called_once()

    @patch("preloop.services.flow_presets_service.crud_flow")
    def test_sync_updates_prompt_only(self, mock_crud):
        """Test syncing when only prompt needs update."""
        mock_db = MagicMock(spec=Session)
        preset_id = uuid.uuid4()

        mock_preset = MagicMock()
        mock_preset.id = preset_id
        mock_preset.name = "Test Preset"
        mock_preset.is_preset = True
        mock_preset.prompt_template = "New prompt"
        mock_preset.allowed_mcp_tools = ["tool1"]
        mock_crud.get.return_value = mock_preset

        # Flow with outdated prompt but up-to-date tools
        tools_hash = compute_content_hash(["tool1"])
        mock_flow = MagicMock()
        mock_flow.id = uuid.uuid4()
        mock_flow.name = "Derived Flow"
        mock_flow.source_prompt_hash = "old_hash"
        mock_flow.source_tools_hash = tools_hash
        mock_flow.prompt_customized = False
        mock_flow.tools_customized = False

        mock_db.query.return_value.filter.return_value.all.return_value = [mock_flow]

        result = sync_preset_to_derived_flows(mock_db, preset_id)

        assert result.auto_updated == 1
        assert mock_flow.prompt_template == "New prompt"

    @patch("preloop.services.flow_presets_service.crud_flow")
    def test_sync_updates_tools_only(self, mock_crud):
        """Test syncing when only tools need update."""
        mock_db = MagicMock(spec=Session)
        preset_id = uuid.uuid4()

        mock_preset = MagicMock()
        mock_preset.id = preset_id
        mock_preset.name = "Test Preset"
        mock_preset.is_preset = True
        mock_preset.prompt_template = "Current prompt"
        mock_preset.allowed_mcp_tools = ["new_tool"]
        mock_crud.get.return_value = mock_preset

        # Flow with up-to-date prompt but outdated tools
        prompt_hash = compute_content_hash("Current prompt")
        mock_flow = MagicMock()
        mock_flow.id = uuid.uuid4()
        mock_flow.name = "Derived Flow"
        mock_flow.source_prompt_hash = prompt_hash
        mock_flow.source_tools_hash = "old_hash"
        mock_flow.prompt_customized = False
        mock_flow.tools_customized = False

        mock_db.query.return_value.filter.return_value.all.return_value = [mock_flow]

        result = sync_preset_to_derived_flows(mock_db, preset_id)

        assert result.auto_updated == 1
        assert mock_flow.allowed_mcp_tools == ["new_tool"]

    @patch("preloop.services.flow_presets_service.crud_flow")
    def test_sync_mixed_flows(self, mock_crud):
        """Test syncing with a mix of different flow states."""
        mock_db = MagicMock(spec=Session)
        preset_id = uuid.uuid4()

        mock_preset = MagicMock()
        mock_preset.id = preset_id
        mock_preset.name = "Test Preset"
        mock_preset.is_preset = True
        mock_preset.prompt_template = "New prompt"
        mock_preset.allowed_mcp_tools = ["new_tool"]
        mock_crud.get.return_value = mock_preset

        # Flow 1: Up to date (should be skipped)
        prompt_hash = compute_content_hash("New prompt")
        tools_hash = compute_content_hash(["new_tool"])
        flow1 = MagicMock()
        flow1.id = uuid.uuid4()
        flow1.source_prompt_hash = prompt_hash
        flow1.source_tools_hash = tools_hash

        # Flow 2: Needs update, not customized (should be auto-updated)
        flow2 = MagicMock()
        flow2.id = uuid.uuid4()
        flow2.name = "Flow 2"
        flow2.source_prompt_hash = "old_hash"
        flow2.source_tools_hash = "old_hash"
        flow2.prompt_customized = False
        flow2.tools_customized = False

        # Flow 3: Needs update, customized prompt (should be notified)
        flow3 = MagicMock()
        flow3.id = uuid.uuid4()
        flow3.name = "Flow 3"
        flow3.source_prompt_hash = "old_hash"
        flow3.source_tools_hash = tools_hash
        flow3.prompt_customized = True
        flow3.tools_customized = False
        flow3.preset_update_available = False

        mock_db.query.return_value.filter.return_value.all.return_value = [
            flow1,
            flow2,
            flow3,
        ]

        result = sync_preset_to_derived_flows(mock_db, preset_id)

        assert result.skipped == 1
        assert result.auto_updated == 1
        assert result.notified == 1


class TestApplyPresetUpdateToFlowEdgeCases:
    """Additional edge case tests for apply_preset_update_to_flow function."""

    @patch("preloop.services.flow_presets_service.crud_flow")
    def test_apply_update_with_none_allowed_mcp_tools(self, mock_crud):
        """Test applying update when allowed_mcp_tools is None."""
        mock_db = MagicMock(spec=Session)
        flow_id = uuid.uuid4()
        preset_id = uuid.uuid4()
        account_id = uuid.uuid4()

        mock_flow = MagicMock()
        mock_flow.id = flow_id
        mock_flow.name = "Test Flow"
        mock_flow.source_preset_id = preset_id
        mock_flow.account_id = account_id

        mock_preset = MagicMock()
        mock_preset.id = preset_id
        mock_preset.prompt_template = "Updated prompt"
        mock_preset.allowed_mcp_tools = None  # None instead of list
        mock_preset.name = "Source Preset"
        mock_preset.is_preset = True
        mock_preset.account_id = None  # Global preset

        mock_crud.get.side_effect = [mock_flow, mock_preset]

        result = apply_preset_update_to_flow(mock_db, flow_id)

        assert result == mock_flow
        assert mock_flow.allowed_mcp_tools is None

    @patch("preloop.services.flow_presets_service.crud_flow")
    def test_apply_update_clears_customization_flags(self, mock_crud):
        """Test that applying update clears all customization flags."""
        mock_db = MagicMock(spec=Session)
        flow_id = uuid.uuid4()
        preset_id = uuid.uuid4()
        account_id = uuid.uuid4()

        mock_flow = MagicMock()
        mock_flow.id = flow_id
        mock_flow.name = "Test Flow"
        mock_flow.source_preset_id = preset_id
        mock_flow.account_id = account_id
        mock_flow.prompt_customized = True
        mock_flow.tools_customized = True
        mock_flow.preset_update_available = True

        mock_preset = MagicMock()
        mock_preset.id = preset_id
        mock_preset.prompt_template = "Updated prompt"
        mock_preset.allowed_mcp_tools = ["tool"]
        mock_preset.name = "Source Preset"
        mock_preset.is_preset = True
        mock_preset.account_id = None  # Global preset

        mock_crud.get.side_effect = [mock_flow, mock_preset]

        apply_preset_update_to_flow(mock_db, flow_id)

        # All flags should be cleared
        assert mock_flow.prompt_customized is False
        assert mock_flow.tools_customized is False
        assert mock_flow.preset_update_available is False


class TestEnsureGlobalPresetsExistEdgeCases:
    """Additional edge case tests for ensure_global_presets_exist function."""

    @patch("preloop.services.flow_presets_service.FLOW_PRESETS", [])
    def test_ensure_global_presets_with_empty_presets_list(self):
        """Test with empty presets list."""
        mock_db = MagicMock(spec=Session)

        result = ensure_global_presets_exist(mock_db)

        assert result == []

    @patch("preloop.services.flow_presets_service.schemas.FlowCreate")
    @patch("preloop.services.flow_presets_service.crud_flow")
    @patch("preloop.services.flow_presets_service.FLOW_PRESETS")
    def test_ensure_global_presets_removes_account_id(
        self, mock_presets, mock_crud, mock_flow_create
    ):
        """Test that account_id is removed from preset config."""
        mock_db = MagicMock(spec=Session)
        mock_presets.__iter__ = lambda self: iter(
            [
                {
                    "name": "Preset With Account",
                    "prompt_template": "test",
                    "account_id": uuid.uuid4(),  # This should be removed
                    "agent_config": {},
                },
            ]
        )

        mock_crud.get_global_preset_by_name.return_value = None
        mock_flow = MagicMock()
        mock_crud.create.return_value = mock_flow

        ensure_global_presets_exist(mock_db)

        # FlowCreate should not receive account_id
        call_kwargs = mock_flow_create.call_args[1]
        assert "account_id" not in call_kwargs
