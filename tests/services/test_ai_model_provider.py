"""Tests for AI model provider service."""

import sys
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from spacebridge.services.ai_model_provider import (
    get_available_models_for_provider,
    _get_openai_models,
    _get_anthropic_models,
    _get_google_models,
    _get_qwen_models,
    _get_deepseek_models,
)


class TestGetAvailableModelsForProvider:
    """Test get_available_models_for_provider function."""

    @pytest.mark.asyncio
    async def test_get_openai_models(self):
        """Test routing to OpenAI provider."""
        with patch(
            "spacebridge.services.ai_model_provider._get_openai_models"
        ) as mock_get:
            mock_get.return_value = ["gpt-4o", "gpt-4-turbo"]
            result = await get_available_models_for_provider("openai", "test_key")
            assert result == ["gpt-4o", "gpt-4-turbo"]
            mock_get.assert_called_once_with("test_key")

    @pytest.mark.asyncio
    async def test_get_anthropic_models(self):
        """Test routing to Anthropic provider."""
        with patch(
            "spacebridge.services.ai_model_provider._get_anthropic_models"
        ) as mock_get:
            mock_get.return_value = ["claude-sonnet-4-5-20250929"]
            result = await get_available_models_for_provider("anthropic", "test_key")
            assert result == ["claude-sonnet-4-5-20250929"]
            mock_get.assert_called_once_with("test_key")

    @pytest.mark.asyncio
    async def test_get_google_models(self):
        """Test routing to Google provider."""
        with patch(
            "spacebridge.services.ai_model_provider._get_google_models"
        ) as mock_get:
            mock_get.return_value = ["gemini-2.5-pro-exp"]
            result = await get_available_models_for_provider("google", "test_key")
            assert result == ["gemini-2.5-pro-exp"]
            mock_get.assert_called_once_with("test_key")

    @pytest.mark.asyncio
    async def test_get_qwen_models(self):
        """Test routing to Qwen provider."""
        with patch(
            "spacebridge.services.ai_model_provider._get_qwen_models"
        ) as mock_get:
            mock_get.return_value = ["qwen-plus", "qwen-turbo"]
            result = await get_available_models_for_provider("qwen", "test_key")
            assert result == ["qwen-plus", "qwen-turbo"]
            mock_get.assert_called_once_with("test_key")

    @pytest.mark.asyncio
    async def test_get_deepseek_models(self):
        """Test routing to DeepSeek provider."""
        with patch(
            "spacebridge.services.ai_model_provider._get_deepseek_models"
        ) as mock_get:
            mock_get.return_value = ["deepseek-chat", "deepseek-reasoner"]
            result = await get_available_models_for_provider("deepseek", "test_key")
            assert result == ["deepseek-chat", "deepseek-reasoner"]
            mock_get.assert_called_once_with("test_key")

    @pytest.mark.asyncio
    async def test_get_custom_provider_returns_empty(self):
        """Test that custom/unknown providers return empty list."""
        result = await get_available_models_for_provider("custom_provider")
        assert result == []


class TestGetOpenAIModels:
    """Test _get_openai_models function."""

    @pytest.mark.asyncio
    async def test_get_openai_models_success(self):
        """Test successful retrieval of OpenAI models."""
        mock_model_1 = MagicMock()
        mock_model_1.id = "gpt-4o"
        mock_model_2 = MagicMock()
        mock_model_2.id = "gpt-4-turbo"
        mock_model_3 = MagicMock()
        mock_model_3.id = "gpt-3.5-turbo"
        mock_model_4 = MagicMock()
        mock_model_4.id = "gpt-4-instruct"  # Should be filtered out

        mock_response = MagicMock()
        mock_response.data = [mock_model_1, mock_model_2, mock_model_3, mock_model_4]

        with patch("openai.AsyncOpenAI") as mock_client:
            mock_instance = MagicMock()
            mock_instance.models.list = AsyncMock(return_value=mock_response)
            mock_client.return_value = mock_instance

            result = await _get_openai_models("test_key")

            assert len(result) <= 10
            assert "gpt-4o" in result
            assert "gpt-4-turbo" in result
            assert "gpt-3.5-turbo" in result
            assert "gpt-4-instruct" not in result  # Filtered out

    @pytest.mark.asyncio
    async def test_get_openai_models_filters_non_chat_models(self):
        """Test that non-chat models are filtered."""
        mock_models = []
        for model_id in [
            "gpt-4o",
            "gpt-4-audio-preview",  # Should be filtered
            "gpt-3.5-turbo-instruct",  # Should be filtered
            "text-similarity-ada-001",  # Should be filtered
            "text-search-ada-doc-001",  # Should be filtered
            "gpt-4-turbo",
        ]:
            mock_model = MagicMock()
            mock_model.id = model_id
            mock_models.append(mock_model)

        mock_response = MagicMock()
        mock_response.data = mock_models

        with patch("openai.AsyncOpenAI") as mock_client:
            mock_instance = MagicMock()
            mock_instance.models.list = AsyncMock(return_value=mock_response)
            mock_client.return_value = mock_instance

            result = await _get_openai_models("test_key")

            assert "gpt-4o" in result
            assert "gpt-4-turbo" in result
            assert "gpt-4-audio-preview" not in result
            assert "gpt-3.5-turbo-instruct" not in result
            assert "text-similarity-ada-001" not in result

    @pytest.mark.asyncio
    async def test_get_openai_models_authentication_error(self):
        """Test handling of authentication errors."""
        from openai import AuthenticationError

        with patch("openai.AsyncOpenAI") as mock_client:
            mock_instance = MagicMock()
            mock_instance.models.list = AsyncMock(
                side_effect=AuthenticationError(
                    message="Invalid API key",
                    response=MagicMock(),
                    body=None,
                )
            )
            mock_client.return_value = mock_instance

            with pytest.raises(ValueError, match="Invalid OpenAI API key"):
                await _get_openai_models("invalid_key")

    @pytest.mark.asyncio
    async def test_get_openai_models_network_error_returns_fallback(self):
        """Test that network errors return fallback list."""
        with patch("openai.AsyncOpenAI") as mock_client:
            mock_instance = MagicMock()
            mock_instance.models.list = AsyncMock(
                side_effect=Exception("Network error")
            )
            mock_client.return_value = mock_instance

            result = await _get_openai_models("test_key")

            # Should return fallback list
            assert "gpt-4o" in result
            assert "gpt-4-turbo" in result
            assert "gpt-3.5-turbo" in result

    @pytest.mark.asyncio
    async def test_get_openai_models_without_api_key(self):
        """Test retrieval without providing API key."""
        mock_model = MagicMock()
        mock_model.id = "gpt-4o"
        mock_response = MagicMock()
        mock_response.data = [mock_model]

        with patch("openai.AsyncOpenAI") as mock_client:
            mock_instance = MagicMock()
            mock_instance.models.list = AsyncMock(return_value=mock_response)
            mock_client.return_value = mock_instance

            result = await _get_openai_models(None)

            # Should call AsyncOpenAI without api_key parameter
            mock_client.assert_called_once_with()
            assert "gpt-4o" in result


class TestGetAnthropicModels:
    """Test _get_anthropic_models function."""

    @pytest.mark.asyncio
    async def test_get_anthropic_models_without_key(self):
        """Test getting Anthropic models without API key."""
        result = await _get_anthropic_models(None)
        assert "claude-sonnet-4-5-20250929" in result
        assert "claude-haiku-4-5-20251001" in result

    @pytest.mark.asyncio
    async def test_get_anthropic_models_with_valid_key(self):
        """Test validation with valid API key."""
        with patch("anthropic.AsyncAnthropic") as mock_client:
            mock_instance = MagicMock()
            mock_instance.messages.create = AsyncMock(return_value=MagicMock())
            mock_client.return_value = mock_instance

            result = await _get_anthropic_models("valid_key")

            assert "claude-sonnet-4-5-20250929" in result
            mock_instance.messages.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_anthropic_models_authentication_error(self):
        """Test handling of authentication errors."""
        with patch("anthropic.AsyncAnthropic") as mock_client:
            mock_instance = MagicMock()
            mock_instance.messages.create = AsyncMock(
                side_effect=Exception("401 unauthorized")
            )
            mock_client.return_value = mock_instance

            with pytest.raises(ValueError, match="Invalid Anthropic API key"):
                await _get_anthropic_models("invalid_key")

    @pytest.mark.asyncio
    async def test_get_anthropic_models_import_error(self):
        """Test handling when Anthropic package not installed."""
        with patch(
            "anthropic.AsyncAnthropic",
            side_effect=ImportError("No module named 'anthropic'"),
        ):
            result = await _get_anthropic_models("test_key")
            # Should return known models even if package not installed
            assert "claude-sonnet-4-5-20250929" in result

    @pytest.mark.asyncio
    async def test_get_anthropic_models_network_error(self):
        """Test handling of non-authentication errors."""
        with patch("anthropic.AsyncAnthropic") as mock_client:
            mock_instance = MagicMock()
            mock_instance.messages.create = AsyncMock(
                side_effect=Exception("Network timeout")
            )
            mock_client.return_value = mock_instance

            result = await _get_anthropic_models("test_key")
            # Should return known models even on network error
            assert "claude-sonnet-4-5-20250929" in result


class TestGetGoogleModels:
    """Test _get_google_models function."""

    @pytest.mark.asyncio
    async def test_get_google_models_without_key(self):
        """Test getting Google models without API key."""
        result = await _get_google_models(None)
        assert "gemini-2.5-pro-exp" in result
        assert "gemini-2.5-flash-preview" in result

    @pytest.mark.asyncio
    async def test_get_google_models_with_valid_key(self):
        """Test validation with valid API key."""
        # Mock both the google and google.generativeai modules
        mock_google = MagicMock()
        mock_genai = MagicMock()
        mock_model = MagicMock()
        mock_model.generate_content = MagicMock(return_value=MagicMock())
        mock_genai.GenerativeModel.return_value = mock_model
        mock_genai.GenerationConfig = MagicMock
        mock_google.generativeai = mock_genai

        with patch.dict(
            sys.modules,
            {"google": mock_google, "google.generativeai": mock_genai},
            clear=False,
        ):
            result = await _get_google_models("valid_key")

            assert "gemini-2.5-pro-exp" in result
            mock_genai.configure.assert_called_once_with(api_key="valid_key")

    @pytest.mark.asyncio
    async def test_get_google_models_authentication_error(self):
        """Test handling of authentication errors."""
        # Mock both the google and google.generativeai modules
        mock_google = MagicMock()
        mock_genai = MagicMock()
        mock_model = MagicMock()
        mock_model.generate_content = MagicMock(
            side_effect=Exception("403 permission denied")
        )
        mock_genai.GenerativeModel.return_value = mock_model
        mock_genai.GenerationConfig = MagicMock
        mock_google.generativeai = mock_genai

        with patch.dict(
            sys.modules,
            {"google": mock_google, "google.generativeai": mock_genai},
            clear=False,
        ):
            with pytest.raises(ValueError, match="Invalid Google API key"):
                await _get_google_models("invalid_key")

    @pytest.mark.asyncio
    async def test_get_google_models_import_error(self):
        """Test handling when Google package not installed."""
        # Ensure google.generativeai is not in sys.modules
        genai_module = sys.modules.pop("google.generativeai", None)
        try:
            # Mock the import to raise ImportError
            import builtins

            original_import = builtins.__import__

            def mock_import(name, *args, **kwargs):
                if name == "google.generativeai":
                    raise ImportError("No module named 'google.generativeai'")
                return original_import(name, *args, **kwargs)

            with patch("builtins.__import__", side_effect=mock_import):
                result = await _get_google_models("test_key")
                # Should return known models even if package not installed
                assert "gemini-2.5-pro-exp" in result
        finally:
            # Restore google.generativeai if it was there
            if genai_module is not None:
                sys.modules["google.generativeai"] = genai_module

    @pytest.mark.asyncio
    async def test_get_google_models_network_error(self):
        """Test handling of non-authentication errors."""
        mock_genai = MagicMock()
        mock_model = MagicMock()
        mock_model.generate_content = MagicMock(
            side_effect=Exception("Connection reset")
        )
        mock_genai.GenerativeModel.return_value = mock_model
        mock_genai.GenerationConfig = MagicMock

        with patch.dict(sys.modules, {"google.generativeai": mock_genai}):
            result = await _get_google_models("test_key")
            # Should return known models even on network error
            assert "gemini-2.5-pro-exp" in result


class TestGetQwenModels:
    """Test _get_qwen_models function."""

    @pytest.mark.asyncio
    async def test_get_qwen_models_without_key(self):
        """Test getting Qwen models without API key."""
        result = await _get_qwen_models(None)
        assert "qwen-plus" in result
        assert "qwen-turbo" in result
        assert "qwen-max" in result

    @pytest.mark.asyncio
    async def test_get_qwen_models_with_valid_key(self):
        """Test validation with valid API key."""
        with patch("openai.AsyncOpenAI") as mock_client:
            mock_instance = MagicMock()
            mock_instance.models.list = AsyncMock(return_value=MagicMock())
            mock_client.return_value = mock_instance

            result = await _get_qwen_models("valid_key")

            assert "qwen-plus" in result
            mock_client.assert_called_once()
            # Verify it's using Qwen's base URL
            call_kwargs = mock_client.call_args[1]
            assert (
                call_kwargs["base_url"]
                == "https://dashscope.aliyuncs.com/compatible-mode/v1"
            )

    @pytest.mark.asyncio
    async def test_get_qwen_models_authentication_error(self):
        """Test handling of authentication errors."""
        from openai import AuthenticationError

        with patch("openai.AsyncOpenAI") as mock_client:
            mock_instance = MagicMock()
            mock_instance.models.list = AsyncMock(
                side_effect=AuthenticationError(
                    message="Invalid API key",
                    response=MagicMock(),
                    body=None,
                )
            )
            mock_client.return_value = mock_instance

            with pytest.raises(ValueError, match="Invalid Qwen API key"):
                await _get_qwen_models("invalid_key")

    @pytest.mark.asyncio
    async def test_get_qwen_models_network_error(self):
        """Test handling of non-authentication errors."""
        with patch("openai.AsyncOpenAI") as mock_client:
            mock_instance = MagicMock()
            mock_instance.models.list = AsyncMock(
                side_effect=Exception("Network error")
            )
            mock_client.return_value = mock_instance

            result = await _get_qwen_models("test_key")
            # Should return known models even on network error
            assert "qwen-plus" in result


class TestGetDeepSeekModels:
    """Test _get_deepseek_models function."""

    @pytest.mark.asyncio
    async def test_get_deepseek_models_without_key(self):
        """Test getting DeepSeek models without API key."""
        result = await _get_deepseek_models(None)
        assert "deepseek-chat" in result
        assert "deepseek-reasoner" in result

    @pytest.mark.asyncio
    async def test_get_deepseek_models_with_valid_key(self):
        """Test validation with valid API key."""
        with patch("openai.AsyncOpenAI") as mock_client:
            mock_instance = MagicMock()
            mock_instance.models.list = AsyncMock(return_value=MagicMock())
            mock_client.return_value = mock_instance

            result = await _get_deepseek_models("valid_key")

            assert "deepseek-chat" in result
            mock_client.assert_called_once()
            # Verify it's using DeepSeek's base URL
            call_kwargs = mock_client.call_args[1]
            assert call_kwargs["base_url"] == "https://api.deepseek.com/v1"

    @pytest.mark.asyncio
    async def test_get_deepseek_models_authentication_error(self):
        """Test handling of authentication errors."""
        from openai import AuthenticationError

        with patch("openai.AsyncOpenAI") as mock_client:
            mock_instance = MagicMock()
            mock_instance.models.list = AsyncMock(
                side_effect=AuthenticationError(
                    message="Invalid API key",
                    response=MagicMock(),
                    body=None,
                )
            )
            mock_client.return_value = mock_instance

            with pytest.raises(ValueError, match="Invalid DeepSeek API key"):
                await _get_deepseek_models("invalid_key")

    @pytest.mark.asyncio
    async def test_get_deepseek_models_network_error(self):
        """Test handling of non-authentication errors."""
        with patch("openai.AsyncOpenAI") as mock_client:
            mock_instance = MagicMock()
            mock_instance.models.list = AsyncMock(
                side_effect=Exception("Network error")
            )
            mock_client.return_value = mock_instance

            result = await _get_deepseek_models("test_key")
            # Should return known models even on network error
            assert "deepseek-chat" in result
