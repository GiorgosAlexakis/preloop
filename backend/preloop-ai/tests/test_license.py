"""Tests for license and feature flag system."""

import pytest
from fastapi import HTTPException

from preloop_ai.license import (
    OPEN_SOURCE_FEATURES,
    PROPRIETARY_FEATURES,
    Feature,
    get_available_features,
    get_feature_info,
    has_feature,
    is_feature_available,
    require_feature,
)


class TestFeatureFlags:
    """Tests for feature flag system."""

    def test_open_source_features_available(self):
        """Test that open source features are available."""
        for feature in OPEN_SOURCE_FEATURES:
            assert is_feature_available(feature) is True
            assert has_feature(feature) is True

    def test_proprietary_features_not_available(self):
        """Test that proprietary features are not available in Phase 0."""
        for feature in PROPRIETARY_FEATURES:
            assert is_feature_available(feature) is False
            assert has_feature(feature) is False

    def test_open_source_features_with_account_id(self):
        """Test that open source features work with account_id parameter."""
        for feature in OPEN_SOURCE_FEATURES:
            assert is_feature_available(feature, "test-account") is True
            assert has_feature(feature, "test-account") is True

    def test_proprietary_features_with_account_id(self):
        """Test that proprietary features are not available even with account_id."""
        for feature in PROPRIETARY_FEATURES:
            assert is_feature_available(feature, "test-account") is False
            assert has_feature(feature, "test-account") is False

    def test_get_available_features(self):
        """Test getting list of available features."""
        features = get_available_features()

        # All open source features should be in the list
        for feature in OPEN_SOURCE_FEATURES:
            assert feature.value in features

        # No proprietary features should be in the list
        for feature in PROPRIETARY_FEATURES:
            assert feature.value not in features

    def test_get_available_features_with_account(self):
        """Test getting available features with account_id."""
        features = get_available_features("test-account")

        # All open source features should be in the list
        for feature in OPEN_SOURCE_FEATURES:
            assert feature.value in features

        # No proprietary features should be in the list
        for feature in PROPRIETARY_FEATURES:
            assert feature.value not in features

    def test_get_feature_info_open_source(self):
        """Test getting info for open source feature."""
        feature = Feature.APPROVAL_RULES
        info = get_feature_info(feature)

        assert info["name"] == feature.value
        assert info["is_open_source"] is True
        assert info["is_proprietary"] is False
        assert info["is_available"] is True

    def test_get_feature_info_proprietary(self):
        """Test getting info for proprietary feature."""
        feature = Feature.MULTI_STAGE_APPROVAL
        info = get_feature_info(feature)

        assert info["name"] == feature.value
        assert info["is_open_source"] is False
        assert info["is_proprietary"] is True
        assert info["is_available"] is False


class TestRequireFeatureDecorator:
    """Tests for require_feature decorator."""

    @pytest.mark.asyncio
    async def test_async_decorator_with_available_feature(self):
        """Test decorator with available feature on async function."""

        @require_feature(Feature.APPROVAL_RULES)
        async def test_endpoint():
            return {"success": True}

        result = await test_endpoint()
        assert result == {"success": True}

    @pytest.mark.asyncio
    async def test_async_decorator_with_unavailable_feature(self):
        """Test decorator raises error for unavailable feature on async function."""

        @require_feature(Feature.MULTI_STAGE_APPROVAL)
        async def test_endpoint():
            return {"success": True}

        with pytest.raises(HTTPException) as exc_info:
            await test_endpoint()

        assert exc_info.value.status_code == 403
        assert "feature_not_available" in str(exc_info.value.detail)

    def test_sync_decorator_with_available_feature(self):
        """Test decorator with available feature on sync function."""

        @require_feature(Feature.APPROVAL_RULES)
        def test_endpoint():
            return {"success": True}

        result = test_endpoint()
        assert result == {"success": True}

    def test_sync_decorator_with_unavailable_feature(self):
        """Test decorator raises error for unavailable feature on sync function."""

        @require_feature(Feature.MULTI_STAGE_APPROVAL)
        def test_endpoint():
            return {"success": True}

        with pytest.raises(HTTPException) as exc_info:
            test_endpoint()

        assert exc_info.value.status_code == 403
        assert "feature_not_available" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_decorator_with_account_id_kwarg(self):
        """Test decorator extracts account_id from kwargs."""

        @require_feature(Feature.APPROVAL_RULES)
        async def test_endpoint(account_id: str):
            return {"account_id": account_id}

        result = await test_endpoint(account_id="test-account")
        assert result == {"account_id": "test-account"}

    @pytest.mark.asyncio
    async def test_decorator_preserves_function_metadata(self):
        """Test decorator preserves function name and docstring."""

        @require_feature(Feature.APPROVAL_RULES)
        async def test_endpoint():
            """Test endpoint docstring."""
            return {"success": True}

        assert test_endpoint.__name__ == "test_endpoint"
        assert test_endpoint.__doc__ == "Test endpoint docstring."


class TestFeatureEnums:
    """Tests for Feature enum."""

    def test_all_features_categorized(self):
        """Test that all features are either open source or proprietary."""
        for feature in Feature:
            assert (feature in OPEN_SOURCE_FEATURES) or (
                feature in PROPRIETARY_FEATURES
            )

    def test_no_feature_overlap(self):
        """Test that no feature is both open source and proprietary."""
        overlap = OPEN_SOURCE_FEATURES & PROPRIETARY_FEATURES
        assert len(overlap) == 0

    def test_feature_values_are_strings(self):
        """Test that all feature values are strings."""
        for feature in Feature:
            assert isinstance(feature.value, str)
            assert len(feature.value) > 0
