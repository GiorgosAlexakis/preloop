"""Service for fetching available models from AI providers."""

import logging
from typing import List, Optional

logger = logging.getLogger(__name__)


async def get_available_models_for_provider(
    provider: str, api_key: Optional[str] = None
) -> List[str]:
    """
    Fetch available models from the specified AI provider.

    Args:
        provider: The provider name (openai, anthropic, google, qwen, deepseek)
        api_key: Optional API key for authentication

    Returns:
        List of model identifiers/names
    """
    if provider == "openai":
        return await _get_openai_models(api_key)
    elif provider == "anthropic":
        return await _get_anthropic_models(api_key)
    elif provider == "google":
        return await _get_google_models(api_key)
    elif provider == "qwen":
        return await _get_qwen_models(api_key)
    elif provider == "deepseek":
        return await _get_deepseek_models(api_key)
    else:
        # For custom providers, return empty list
        return []


async def _get_openai_models(api_key: Optional[str] = None) -> List[str]:
    """Fetch available models from OpenAI API."""
    try:
        from openai import AsyncOpenAI, AuthenticationError

        # Use provided API key or fall back to environment variable
        client = AsyncOpenAI(api_key=api_key) if api_key else AsyncOpenAI()

        models_response = await client.models.list()
        models = models_response.data

        # Filter for chat models (gpt-*) and sort by ID
        chat_models = [
            model.id
            for model in models
            if model.id.startswith("gpt-")
            and not any(
                x in model.id
                for x in [
                    "instruct",
                    "search",
                    "similarity",
                    "edit",
                    "insert",
                    "audio",
                    "realtime",
                ]
            )
        ]

        # Sort with newer models first
        chat_models.sort(reverse=True)

        return chat_models[:10]  # Return top 10 most recent models
    except AuthenticationError as e:
        logger.warning(f"OpenAI authentication failed: {e}")
        # Re-raise authentication errors so the user knows their API key is invalid
        raise ValueError(
            "Invalid OpenAI API key. Please check your API key and try again."
        )
    except Exception as e:
        logger.warning(f"Failed to fetch OpenAI models: {e}")
        # Return fallback list for other errors (network issues, etc.)
        return [
            "gpt-4o",
            "gpt-4o-mini",
            "gpt-4-turbo",
            "gpt-4",
            "gpt-3.5-turbo",
        ]


async def _get_anthropic_models(api_key: Optional[str] = None) -> List[str]:
    """Return list of known Anthropic Claude models and validate API key if provided."""

    # List of known Anthropic models (as of January 2025)
    known_models = [
        "claude-sonnet-4-5-20250929",
        "claude-haiku-4-5-20251001",
    ]

    # If API key is provided, validate it by making a minimal API call
    if api_key:
        try:
            try:
                from anthropic import AsyncAnthropic
            except ImportError:
                logger.warning("Anthropic package not installed, skipping validation")
                # If package not installed, we can't validate - return the list
                return known_models

            client = AsyncAnthropic(api_key=api_key)

            # Make a minimal request to validate the key
            # Use a very short max_tokens to minimize cost
            await client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=1,
                messages=[{"role": "user", "content": "Hi"}],
            )

            logger.info("Anthropic API key validated successfully")
        except Exception as e:
            logger.warning(f"Anthropic validation exception: {type(e).__name__}: {e}")
            error_msg = str(e).lower()
            error_type = type(e).__name__.lower()

            logger.debug(f"Error message: {error_msg}")
            logger.debug(f"Error type: {error_type}")

            # Check for authentication errors by message content and exception type
            if any(
                keyword in error_msg
                for keyword in [
                    "401",
                    "unauthorized",
                    "authentication",
                    "invalid_api_key",
                    "api_key",
                ]
            ) or any(
                keyword in error_type
                for keyword in ["authentication", "permission", "unauthorized"]
            ):
                logger.error("Detected authentication error, raising ValueError")
                raise ValueError(
                    "Invalid Anthropic API key. Please check your API key and try again."
                )
            else:
                # For other errors (network, import, etc.), log but don't fail - just return the list
                logger.error(f"Non-authentication error, returning default list: {e}")

    return known_models


async def _get_google_models(api_key: Optional[str] = None) -> List[str]:
    """Return list of known Google Gemini models and validate API key if provided."""

    # List of known Google Gemini models (as of January 2025)
    known_models = [
        "gemini-2.5-pro-exp",
        "gemini-2.5-flash-preview",
    ]

    # If API key is provided, validate it
    if api_key:
        try:
            try:
                import google.generativeai as genai
            except ImportError:
                logger.warning(
                    "Google GenerativeAI package not installed, skipping validation"
                )
                # If package not installed, we can't validate - return the list
                return known_models

            genai.configure(api_key=api_key)

            # Make a minimal request to validate the key
            # Use the cheapest/fastest model with minimal tokens
            model = genai.GenerativeModel("gemini-1.5-flash")
            response = model.generate_content(
                "Hi", generation_config=genai.GenerationConfig(max_output_tokens=1)
            )

            logger.info("Google API key validated successfully")
        except Exception as e:
            logger.warning(f"Google validation exception: {type(e).__name__}: {e}")
            error_msg = str(e).lower()
            error_type = type(e).__name__.lower()

            logger.debug(f"Error message: {error_msg}")
            logger.debug(f"Error type: {error_type}")

            # Check for authentication errors by message content and exception type
            if any(
                keyword in error_msg
                for keyword in [
                    "401",
                    "403",
                    "unauthorized",
                    "unauthenticated",
                    "permission",
                    "invalid",
                    "api_key",
                    "api key",
                ]
            ) or any(
                keyword in error_type
                for keyword in [
                    "authentication",
                    "permission",
                    "unauthorized",
                    "unauthenticated",
                    "invalidargument",
                ]
            ):
                logger.error("Detected authentication error, raising ValueError")
                raise ValueError(
                    "Invalid Google API key. Please check your API key and try again."
                )
            else:
                # For other errors (network, import, etc.), log but don't fail - just return the list
                logger.error(f"Non-authentication error, returning default list: {e}")

    return known_models


async def _get_qwen_models(api_key: Optional[str] = None) -> List[str]:
    """Return list of known Qwen models and validate API key if provided."""

    # List of known Qwen models (as of January 2025)
    known_models = [
        "qwen-plus",
        "qwen-turbo",
        "qwen-max",
        "qwq-32b-preview",
    ]

    # Qwen uses OpenAI-compatible API
    if api_key:
        try:
            from openai import AsyncOpenAI, AuthenticationError

            client = AsyncOpenAI(
                api_key=api_key,
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            )

            # Try to list models to validate the key
            await client.models.list()

            logger.info("Qwen API key validated successfully")
        except AuthenticationError as e:
            logger.warning(f"Qwen authentication failed: {e}")
            raise ValueError(
                "Invalid Qwen API key. Please check your API key and try again."
            )
        except Exception as e:
            logger.error(f"Unexpected error validating Qwen key: {e}")

    return known_models


async def _get_deepseek_models(api_key: Optional[str] = None) -> List[str]:
    """Return list of known DeepSeek models and validate API key if provided."""

    # List of known DeepSeek models (as of January 2025)
    known_models = [
        "deepseek-chat",
        "deepseek-reasoner",
    ]

    # DeepSeek uses OpenAI-compatible API
    if api_key:
        try:
            from openai import AsyncOpenAI, AuthenticationError

            client = AsyncOpenAI(
                api_key=api_key, base_url="https://api.deepseek.com/v1"
            )

            # Try to list models to validate the key
            await client.models.list()

            logger.info("DeepSeek API key validated successfully")
        except AuthenticationError as e:
            logger.warning(f"DeepSeek authentication failed: {e}")
            raise ValueError(
                "Invalid DeepSeek API key. Please check your API key and try again."
            )
        except Exception as e:
            logger.error(f"Unexpected error validating DeepSeek key: {e}")

    return known_models
