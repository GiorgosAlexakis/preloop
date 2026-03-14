"""OpenAI-compatible model gateway service."""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, Iterator, List, Optional

import litellm
from sqlalchemy import or_
from sqlalchemy.orm import Session

from preloop.models.crud import crud_api_usage, crud_managed_agent, crud_runtime_session
from preloop.models.models.ai_model import AIModel
from preloop.services.account_realtime import (
    ACCOUNT_TOPIC_MANAGED_AGENTS,
    ACCOUNT_TOPIC_RUNTIME_SESSIONS,
    build_account_event,
    emit_account_event,
)
from preloop.services.model_gateway_auth import ModelGatewayAuthContext
from preloop.services.model_gateway_budget import (
    BudgetCheckResult,
    ModelGatewayBudgetService,
)
from preloop.services.model_gateway_events import ModelGatewayEventEmitter
from preloop.services.model_gateway_errors import (
    GatewayProvider,
    ModelGatewayAPIError,
)
from preloop.services.model_runtime_resolver import resolve_ai_model_runtime
from preloop.services.gateway_usage_search import GatewayUsageSearchService
from preloop.services.secret_service import get_secret_service
from preloop.utils.audit import log_model_gateway_request

_PROVIDER_PREFIX: Dict[str, str] = {
    "openai": "openai",
    "anthropic": "anthropic",
    "google": "gemini",
    "gemini": "gemini",
    "qwen": "openai",
    "deepseek": "deepseek",
}

logger = logging.getLogger(__name__)


class OpenAIGatewayService:
    """Service for Preloop's OpenAI-compatible gateway."""

    def __init__(self, db: Session, auth_context: ModelGatewayAuthContext) -> None:
        self.db = db
        self.auth_context = auth_context

    def list_models(self) -> Dict[str, Any]:
        """List gateway-enabled models available to the authenticated account."""
        data = []
        for ai_model in self._get_account_models():
            runtime = resolve_ai_model_runtime(ai_model)
            if not runtime.model_gateway_enabled:
                continue
            data.append(
                {
                    "id": runtime.model_gateway_model_alias,
                    "object": "model",
                    "created": int(ai_model.created_at.timestamp())
                    if ai_model.created_at
                    else 0,
                    "owned_by": "preloop",
                }
            )

        return {"object": "list", "data": data}

    def create_chat_completion(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle OpenAI-compatible chat completions."""
        if payload.get("stream"):
            raise ModelGatewayAPIError(
                provider="openai",
                status_code=400,
                message="Use stream_chat_completion for stream=true",
            )

        model = self._resolve_requested_model(payload.get("model"), provider="openai")
        messages = payload.get("messages")
        if not isinstance(messages, list) or not messages:
            raise ModelGatewayAPIError(
                provider="openai",
                status_code=400,
                message="messages must be a non-empty list",
            )
        started_at = time.perf_counter()
        budget_result = self._check_budget(model, payload)
        if budget_result and budget_result.hard_limit_exceeded:
            detail = self._budget_denial_detail(budget_result)
            self._record_gateway_request(
                endpoint="/openai/v1/chat/completions",
                method="POST",
                status_code=403,
                duration=time.perf_counter() - started_at,
                ai_model=model,
                requested_model=payload.get("model"),
                response_payload=None,
                upstream_response=None,
                endpoint_kind="chat_completions",
                budget_result=budget_result,
                error_detail=detail,
                request_payload=payload,
            )
            raise ModelGatewayAPIError(
                provider="openai",
                status_code=403,
                message=detail,
            )

        try:
            response = self._call_litellm(
                model,
                messages=messages,
                payload=payload,
                provider="openai",
            )
            response_dict = self._response_to_dict(response)
            assistant_content = self._extract_assistant_text(response_dict)
            usage = self._normalize_usage(
                response_dict.get("usage"),
                prompt_key="prompt_tokens",
                completion_key="completion_tokens",
            )
            response_payload = {
                "id": response_dict.get("id", f"chatcmpl_{int(time.time())}"),
                "object": "chat.completion",
                "created": response_dict.get("created", int(time.time())),
                "model": payload.get("model")
                or resolve_ai_model_runtime(model).model_gateway_model_alias,
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": assistant_content},
                        "finish_reason": self._extract_finish_reason(response_dict),
                    }
                ],
                "usage": usage,
            }
            self._record_gateway_request(
                endpoint="/openai/v1/chat/completions",
                method="POST",
                status_code=200,
                duration=time.perf_counter() - started_at,
                ai_model=model,
                requested_model=payload.get("model"),
                response_payload=response_payload,
                upstream_response=response_dict,
                endpoint_kind="chat_completions",
                budget_result=budget_result,
                request_payload=payload,
            )
            return response_payload
        except ModelGatewayAPIError as exc:
            self._record_gateway_request(
                endpoint="/openai/v1/chat/completions",
                method="POST",
                status_code=exc.status_code,
                duration=time.perf_counter() - started_at,
                ai_model=model,
                requested_model=payload.get("model"),
                response_payload=None,
                upstream_response=None,
                endpoint_kind="chat_completions",
                error_detail=exc.message,
                budget_result=budget_result,
                request_payload=payload,
            )
            raise

    def create_response(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle OpenAI Responses API-compatible requests."""
        if payload.get("stream"):
            raise ModelGatewayAPIError(
                provider="openai",
                status_code=400,
                message="Use stream_response for stream=true",
            )

        model = self._resolve_requested_model(payload.get("model"), provider="openai")
        messages = self._normalize_responses_input(payload)
        started_at = time.perf_counter()
        budget_result = self._check_budget(model, payload)
        if budget_result and budget_result.hard_limit_exceeded:
            detail = self._budget_denial_detail(budget_result)
            self._record_gateway_request(
                endpoint="/openai/v1/responses",
                method="POST",
                status_code=403,
                duration=time.perf_counter() - started_at,
                ai_model=model,
                requested_model=payload.get("model"),
                response_payload=None,
                upstream_response=None,
                endpoint_kind="responses",
                budget_result=budget_result,
                error_detail=detail,
                request_payload=payload,
            )
            raise ModelGatewayAPIError(
                provider="openai",
                status_code=403,
                message=detail,
            )
        try:
            response = self._call_litellm(
                model,
                messages=messages,
                payload=payload,
                provider="openai",
            )
            response_dict = self._response_to_dict(response)
            output_items = self._build_response_output_items(response_dict)
            assistant_text = self._response_output_text(output_items)
            usage = self._normalize_usage(
                response_dict.get("usage"),
                prompt_key="prompt_tokens",
                completion_key="completion_tokens",
                output_names=("completion_tokens", "output_tokens"),
            )

            response_payload = {
                "id": response_dict.get("id", f"resp_{int(time.time())}"),
                "object": "response",
                "created_at": response_dict.get("created", int(time.time())),
                "model": payload.get("model")
                or resolve_ai_model_runtime(model).model_gateway_model_alias,
                "status": "completed",
                "output": output_items,
                "output_text": assistant_text,
                "usage": {
                    "input_tokens": usage["prompt_tokens"],
                    "output_tokens": usage["completion_tokens"],
                    "total_tokens": usage["total_tokens"],
                },
            }
            self._record_gateway_request(
                endpoint="/openai/v1/responses",
                method="POST",
                status_code=200,
                duration=time.perf_counter() - started_at,
                ai_model=model,
                requested_model=payload.get("model"),
                response_payload=response_payload,
                upstream_response=response_dict,
                endpoint_kind="responses",
                budget_result=budget_result,
                request_payload=payload,
            )
            return response_payload
        except ModelGatewayAPIError as exc:
            self._record_gateway_request(
                endpoint="/openai/v1/responses",
                method="POST",
                status_code=exc.status_code,
                duration=time.perf_counter() - started_at,
                ai_model=model,
                requested_model=payload.get("model"),
                response_payload=None,
                upstream_response=None,
                endpoint_kind="responses",
                error_detail=exc.message,
                budget_result=budget_result,
                request_payload=payload,
            )
            raise

    def create_message(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle Anthropic Messages API-compatible requests."""
        if payload.get("stream"):
            raise ModelGatewayAPIError(
                provider="anthropic",
                status_code=400,
                message="Use stream_message for stream=true",
            )

        model = self._resolve_requested_model(
            payload.get("model"), provider="anthropic"
        )
        messages = self._normalize_anthropic_messages_input(payload)
        started_at = time.perf_counter()
        budget_result = self._check_budget(model, {**payload, "messages": messages})
        if budget_result and budget_result.hard_limit_exceeded:
            detail = self._budget_denial_detail(budget_result)
            self._record_gateway_request(
                endpoint="/anthropic/v1/messages",
                method="POST",
                status_code=403,
                duration=time.perf_counter() - started_at,
                ai_model=model,
                requested_model=payload.get("model"),
                response_payload=None,
                upstream_response=None,
                endpoint_kind="anthropic_messages",
                budget_result=budget_result,
                error_detail=detail,
                request_payload=payload,
            )
            raise ModelGatewayAPIError(
                provider="anthropic",
                status_code=403,
                message=detail,
            )

        try:
            response = self._call_litellm(
                model,
                messages=messages,
                payload=payload,
                provider="anthropic",
            )
            response_dict = self._response_to_dict(response)
            assistant_text = self._extract_assistant_text(response_dict)
            usage = self._normalize_usage(
                response_dict.get("usage"),
                prompt_key="prompt_tokens",
                completion_key="completion_tokens",
                output_names=("completion_tokens", "output_tokens"),
            )
            response_payload = self._build_anthropic_message_payload(
                response_id=response_dict.get("id", f"msg_{int(time.time())}"),
                model_name=payload.get("model")
                or resolve_ai_model_runtime(model).model_gateway_model_alias,
                assistant_text=assistant_text,
                stop_reason=self._to_anthropic_stop_reason(
                    self._extract_finish_reason(response_dict)
                ),
                usage=usage,
            )
            self._record_gateway_request(
                endpoint="/anthropic/v1/messages",
                method="POST",
                status_code=200,
                duration=time.perf_counter() - started_at,
                ai_model=model,
                requested_model=payload.get("model"),
                response_payload=response_payload,
                upstream_response=response_dict,
                endpoint_kind="anthropic_messages",
                budget_result=budget_result,
                request_payload=payload,
            )
            return response_payload
        except ModelGatewayAPIError as exc:
            self._record_gateway_request(
                endpoint="/anthropic/v1/messages",
                method="POST",
                status_code=exc.status_code,
                duration=time.perf_counter() - started_at,
                ai_model=model,
                requested_model=payload.get("model"),
                response_payload=None,
                upstream_response=None,
                endpoint_kind="anthropic_messages",
                error_detail=exc.message,
                budget_result=budget_result,
                request_payload=payload,
            )
            raise

    def stream_message(self, payload: Dict[str, Any]) -> Iterator[str]:
        """Handle streaming Anthropic Messages API-compatible requests."""
        model = self._resolve_requested_model(
            payload.get("model"), provider="anthropic"
        )
        messages = self._normalize_anthropic_messages_input(payload)
        budget_payload = {**payload, "messages": messages}
        started_at = time.perf_counter()
        budget_result = self._check_budget(model, budget_payload)
        if budget_result and budget_result.hard_limit_exceeded:
            detail = self._budget_denial_detail(budget_result)
            self._record_gateway_request(
                endpoint="/anthropic/v1/messages",
                method="POST",
                status_code=403,
                duration=time.perf_counter() - started_at,
                ai_model=model,
                requested_model=payload.get("model"),
                response_payload=None,
                upstream_response=None,
                endpoint_kind="anthropic_messages_stream",
                budget_result=budget_result,
                error_detail=detail,
                request_payload=payload,
            )
            raise ModelGatewayAPIError(
                provider="anthropic",
                status_code=403,
                message=detail,
            )

        try:
            upstream_stream = self._call_litellm(
                model,
                messages=messages,
                payload=payload,
                stream=True,
                provider="anthropic",
            )
        except ModelGatewayAPIError as exc:
            self._record_gateway_request(
                endpoint="/anthropic/v1/messages",
                method="POST",
                status_code=exc.status_code,
                duration=time.perf_counter() - started_at,
                ai_model=model,
                requested_model=payload.get("model"),
                response_payload=None,
                upstream_response=None,
                endpoint_kind="anthropic_messages_stream",
                error_detail=exc.message,
                budget_result=budget_result,
                request_payload=payload,
            )
            raise

        requested_model = (
            payload.get("model")
            or resolve_ai_model_runtime(model).model_gateway_model_alias
        )

        def event_stream() -> Iterator[str]:
            assistant_parts: List[str] = []
            final_usage = {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
            }
            last_finish_reason: Optional[str] = None
            response_id: Optional[str] = None
            emitted_start = False
            recorded = False

            try:
                for chunk in upstream_stream:
                    chunk_dict = self._response_to_dict(chunk)
                    response_id = response_id or chunk_dict.get(
                        "id", f"msg_{int(time.time())}"
                    )
                    if chunk_dict.get("usage") is not None:
                        final_usage = self._normalize_usage(
                            chunk_dict.get("usage"),
                            prompt_key="prompt_tokens",
                            completion_key="completion_tokens",
                            output_names=("completion_tokens", "output_tokens"),
                        )
                    if not emitted_start:
                        yield self._anthropic_sse_event(
                            "message_start",
                            {
                                "type": "message_start",
                                "message": self._build_anthropic_message_payload(
                                    response_id=response_id,
                                    model_name=requested_model,
                                    assistant_text="",
                                    stop_reason=None,
                                    usage=final_usage,
                                ),
                            },
                        )
                        yield self._anthropic_sse_event(
                            "content_block_start",
                            {
                                "type": "content_block_start",
                                "index": 0,
                                "content_block": {"type": "text", "text": ""},
                            },
                        )
                        emitted_start = True

                    delta_text = self._extract_stream_delta_text(chunk_dict)
                    if delta_text:
                        assistant_parts.append(delta_text)
                        yield self._anthropic_sse_event(
                            "content_block_delta",
                            {
                                "type": "content_block_delta",
                                "index": 0,
                                "delta": {"type": "text_delta", "text": delta_text},
                            },
                        )

                    last_finish_reason = (
                        self._extract_finish_reason(chunk_dict) or last_finish_reason
                    )

                response_id = response_id or f"msg_{int(time.time())}"
                if not emitted_start:
                    yield self._anthropic_sse_event(
                        "message_start",
                        {
                            "type": "message_start",
                            "message": self._build_anthropic_message_payload(
                                response_id=response_id,
                                model_name=requested_model,
                                assistant_text="",
                                stop_reason=None,
                                usage=final_usage,
                            ),
                        },
                    )
                    yield self._anthropic_sse_event(
                        "content_block_start",
                        {
                            "type": "content_block_start",
                            "index": 0,
                            "content_block": {"type": "text", "text": ""},
                        },
                    )

                yield self._anthropic_sse_event(
                    "content_block_stop",
                    {"type": "content_block_stop", "index": 0},
                )
                stop_reason = self._to_anthropic_stop_reason(last_finish_reason)
                response_payload = self._build_anthropic_message_payload(
                    response_id=response_id,
                    model_name=requested_model,
                    assistant_text="".join(assistant_parts),
                    stop_reason=stop_reason,
                    usage=final_usage,
                )
                yield self._anthropic_sse_event(
                    "message_delta",
                    {
                        "type": "message_delta",
                        "delta": {
                            "stop_reason": stop_reason,
                            "stop_sequence": None,
                        },
                        "usage": {
                            "output_tokens": final_usage["completion_tokens"],
                        },
                    },
                )
                self._record_gateway_request(
                    endpoint="/anthropic/v1/messages",
                    method="POST",
                    status_code=200,
                    duration=time.perf_counter() - started_at,
                    ai_model=model,
                    requested_model=payload.get("model"),
                    response_payload=response_payload,
                    upstream_response={
                        "id": response_id,
                        "choices": [{"finish_reason": last_finish_reason}],
                    },
                    endpoint_kind="anthropic_messages_stream",
                    budget_result=budget_result,
                    request_payload=payload,
                )
                recorded = True
                yield self._anthropic_sse_event(
                    "message_stop",
                    {"type": "message_stop"},
                )
            except Exception as exc:
                if not recorded:
                    self._record_gateway_request(
                        endpoint="/anthropic/v1/messages",
                        method="POST",
                        status_code=502,
                        duration=time.perf_counter() - started_at,
                        ai_model=model,
                        requested_model=payload.get("model"),
                        response_payload=None,
                        upstream_response=None,
                        endpoint_kind="anthropic_messages_stream",
                        budget_result=budget_result,
                        error_detail=str(exc),
                        request_payload=payload,
                    )
                raise

        return event_stream()

    def stream_chat_completion(self, payload: Dict[str, Any]) -> Iterator[str]:
        """Handle streaming OpenAI-compatible chat completions."""
        model = self._resolve_requested_model(payload.get("model"), provider="openai")
        messages = payload.get("messages")
        if not isinstance(messages, list) or not messages:
            raise ModelGatewayAPIError(
                provider="openai",
                status_code=400,
                message="messages must be a non-empty list",
            )

        started_at = time.perf_counter()
        budget_result = self._check_budget(model, payload)
        if budget_result and budget_result.hard_limit_exceeded:
            detail = self._budget_denial_detail(budget_result)
            self._record_gateway_request(
                endpoint="/openai/v1/chat/completions",
                method="POST",
                status_code=403,
                duration=time.perf_counter() - started_at,
                ai_model=model,
                requested_model=payload.get("model"),
                response_payload=None,
                upstream_response=None,
                endpoint_kind="chat_completions_stream",
                budget_result=budget_result,
                error_detail=detail,
                request_payload=payload,
            )
            raise ModelGatewayAPIError(
                provider="openai",
                status_code=403,
                message=detail,
            )

        try:
            upstream_stream = self._call_litellm(
                model,
                messages=messages,
                payload=payload,
                stream=True,
                provider="openai",
            )
        except ModelGatewayAPIError as exc:
            self._record_gateway_request(
                endpoint="/openai/v1/chat/completions",
                method="POST",
                status_code=exc.status_code,
                duration=time.perf_counter() - started_at,
                ai_model=model,
                requested_model=payload.get("model"),
                response_payload=None,
                upstream_response=None,
                endpoint_kind="chat_completions_stream",
                error_detail=exc.message,
                budget_result=budget_result,
                request_payload=payload,
            )
            raise

        requested_model = (
            payload.get("model")
            or resolve_ai_model_runtime(model).model_gateway_model_alias
        )

        def event_stream() -> Iterator[str]:
            assistant_parts: List[str] = []
            final_usage = {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
            }
            last_finish_reason: Optional[str] = None
            response_id: Optional[str] = None
            created_at: Optional[int] = None
            recorded = False
            try:
                for chunk in upstream_stream:
                    chunk_dict = self._response_to_dict(chunk)
                    response_id = response_id or chunk_dict.get(
                        "id", f"chatcmpl_{int(time.time())}"
                    )
                    created_at = created_at or chunk_dict.get(
                        "created", int(time.time())
                    )
                    event_payload = self._normalize_chat_stream_chunk(
                        chunk_dict,
                        model_name=requested_model,
                        response_id=response_id,
                        created_at=created_at,
                    )
                    delta_text = self._extract_stream_delta_text(event_payload)
                    if delta_text:
                        assistant_parts.append(delta_text)
                    last_finish_reason = (
                        self._extract_finish_reason(event_payload) or last_finish_reason
                    )
                    if chunk_dict.get("usage") is not None:
                        final_usage = self._normalize_usage(
                            chunk_dict.get("usage"),
                            prompt_key="prompt_tokens",
                            completion_key="completion_tokens",
                        )
                    yield self._sse_event(event_payload)

                response_payload = {
                    "id": response_id or f"chatcmpl_{int(time.time())}",
                    "object": "chat.completion",
                    "created": created_at or int(time.time()),
                    "model": requested_model,
                    "choices": [
                        {
                            "index": 0,
                            "message": {
                                "role": "assistant",
                                "content": "".join(assistant_parts),
                            },
                            "finish_reason": last_finish_reason,
                        }
                    ],
                    "usage": final_usage,
                }
                self._record_gateway_request(
                    endpoint="/openai/v1/chat/completions",
                    method="POST",
                    status_code=200,
                    duration=time.perf_counter() - started_at,
                    ai_model=model,
                    requested_model=payload.get("model"),
                    response_payload=response_payload,
                    upstream_response=response_payload,
                    endpoint_kind="chat_completions_stream",
                    budget_result=budget_result,
                    request_payload=payload,
                )
                recorded = True
                yield self._sse_done()
            except Exception as exc:
                if not recorded:
                    self._record_gateway_request(
                        endpoint="/openai/v1/chat/completions",
                        method="POST",
                        status_code=502,
                        duration=time.perf_counter() - started_at,
                        ai_model=model,
                        requested_model=payload.get("model"),
                        response_payload=None,
                        upstream_response=None,
                        endpoint_kind="chat_completions_stream",
                        budget_result=budget_result,
                        error_detail=str(exc),
                        request_payload=payload,
                    )
                raise

        return event_stream()

    def stream_response(self, payload: Dict[str, Any]) -> Iterator[str]:
        """Handle streaming OpenAI Responses API-compatible requests."""
        model = self._resolve_requested_model(payload.get("model"), provider="openai")
        messages = self._normalize_responses_input(payload)
        started_at = time.perf_counter()
        budget_result = self._check_budget(model, payload)
        if budget_result and budget_result.hard_limit_exceeded:
            detail = self._budget_denial_detail(budget_result)
            self._record_gateway_request(
                endpoint="/openai/v1/responses",
                method="POST",
                status_code=403,
                duration=time.perf_counter() - started_at,
                ai_model=model,
                requested_model=payload.get("model"),
                response_payload=None,
                upstream_response=None,
                endpoint_kind="responses_stream",
                budget_result=budget_result,
                error_detail=detail,
                request_payload=payload,
            )
            raise ModelGatewayAPIError(
                provider="openai",
                status_code=403,
                message=detail,
            )

        try:
            upstream_stream = self._call_litellm(
                model,
                messages=messages,
                payload=payload,
                stream=True,
                provider="openai",
            )
        except ModelGatewayAPIError as exc:
            self._record_gateway_request(
                endpoint="/openai/v1/responses",
                method="POST",
                status_code=exc.status_code,
                duration=time.perf_counter() - started_at,
                ai_model=model,
                requested_model=payload.get("model"),
                response_payload=None,
                upstream_response=None,
                endpoint_kind="responses_stream",
                error_detail=exc.message,
                budget_result=budget_result,
                request_payload=payload,
            )
            raise

        requested_model = (
            payload.get("model")
            or resolve_ai_model_runtime(model).model_gateway_model_alias
        )

        def event_stream() -> Iterator[str]:
            response_id = f"resp_{int(time.time())}"
            created_at = int(time.time())
            text_item_id = f"msg_{response_id}"
            assistant_parts: List[str] = []
            final_usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
            recorded = False
            text_output_index: Optional[int] = None
            output_items: List[Dict[str, Any]] = []
            tool_call_states: Dict[int, Dict[str, Any]] = {}
            try:
                yield self._sse_event(
                    {
                        "type": "response.created",
                        "response": {
                            "id": response_id,
                            "object": "response",
                            "created_at": created_at,
                            "model": requested_model,
                            "status": "in_progress",
                        },
                    }
                )

                for chunk in upstream_stream:
                    chunk_dict = self._response_to_dict(chunk)
                    delta_text = self._extract_stream_delta_text(chunk_dict)
                    if delta_text:
                        if text_output_index is None:
                            text_output_index = len(output_items)
                            output_items.append(
                                {
                                    "id": text_item_id,
                                    "type": "message",
                                    "status": "in_progress",
                                    "role": "assistant",
                                    "content": [],
                                }
                            )
                            yield self._sse_event(
                                {
                                    "type": "response.output_item.added",
                                    "response_id": response_id,
                                    "output_index": text_output_index,
                                    "item": output_items[text_output_index],
                                }
                            )
                            yield self._sse_event(
                                {
                                    "type": "response.content_part.added",
                                    "item_id": text_item_id,
                                    "output_index": text_output_index,
                                    "content_index": 0,
                                    "part": {"type": "output_text", "text": ""},
                                }
                            )
                        assistant_parts.append(delta_text)
                        yield self._sse_event(
                            {
                                "type": "response.output_text.delta",
                                "item_id": text_item_id,
                                "output_index": text_output_index,
                                "content_index": 0,
                                "delta": delta_text,
                            }
                        )
                    for tool_delta in self._extract_stream_tool_call_deltas(chunk_dict):
                        index = int(tool_delta.get("index", 0) or 0)
                        state = tool_call_states.get(index)
                        if state is None:
                            call_id = (
                                tool_delta.get("id") or f"call_{response_id}_{index}"
                            )
                            item_id = f"fc_{response_id}_{index}"
                            state = {
                                "item": {
                                    "id": item_id,
                                    "type": "function_call",
                                    "status": "in_progress",
                                    "call_id": call_id,
                                    "name": "",
                                    "arguments": "",
                                },
                                "output_index": len(output_items),
                            }
                            tool_call_states[index] = state
                            output_items.append(state["item"])
                            yield self._sse_event(
                                {
                                    "type": "response.output_item.added",
                                    "response_id": response_id,
                                    "output_index": state["output_index"],
                                    "item": state["item"],
                                }
                            )
                        function_payload = tool_delta.get("function") or {}
                        if function_payload.get("name"):
                            state["item"]["name"] = function_payload["name"]
                        arguments_delta = function_payload.get("arguments")
                        if arguments_delta:
                            state["item"]["arguments"] += arguments_delta
                            yield self._sse_event(
                                {
                                    "type": "response.function_call_arguments.delta",
                                    "item_id": state["item"]["id"],
                                    "output_index": state["output_index"],
                                    "delta": arguments_delta,
                                }
                            )
                    if chunk_dict.get("usage") is not None:
                        usage = self._normalize_usage(
                            chunk_dict.get("usage"),
                            prompt_key="prompt_tokens",
                            completion_key="completion_tokens",
                            output_names=("completion_tokens", "output_tokens"),
                        )
                        final_usage = {
                            "input_tokens": usage["prompt_tokens"],
                            "output_tokens": usage["completion_tokens"],
                            "total_tokens": usage["total_tokens"],
                        }

                full_text = "".join(assistant_parts)
                if text_output_index is not None:
                    output_items[text_output_index] = {
                        "id": text_item_id,
                        "type": "message",
                        "status": "completed",
                        "role": "assistant",
                        "content": [{"type": "output_text", "text": full_text}],
                    }
                    yield self._sse_event(
                        {
                            "type": "response.output_text.done",
                            "item_id": text_item_id,
                            "output_index": text_output_index,
                            "content_index": 0,
                            "text": full_text,
                        }
                    )
                    yield self._sse_event(
                        {
                            "type": "response.content_part.done",
                            "item_id": text_item_id,
                            "output_index": text_output_index,
                            "content_index": 0,
                            "part": {"type": "output_text", "text": full_text},
                        }
                    )
                    yield self._sse_event(
                        {
                            "type": "response.output_item.done",
                            "output_index": text_output_index,
                            "item": output_items[text_output_index],
                        }
                    )
                for state in sorted(
                    tool_call_states.values(), key=lambda item: item["output_index"]
                ):
                    state["item"]["status"] = "completed"
                    yield self._sse_event(
                        {
                            "type": "response.function_call_arguments.done",
                            "item_id": state["item"]["id"],
                            "output_index": state["output_index"],
                            "arguments": state["item"]["arguments"],
                        }
                    )
                    yield self._sse_event(
                        {
                            "type": "response.output_item.done",
                            "output_index": state["output_index"],
                            "item": state["item"],
                        }
                    )
                response_payload = {
                    "id": response_id,
                    "object": "response",
                    "created_at": created_at,
                    "model": requested_model,
                    "status": "completed",
                    "output": output_items,
                    "output_text": full_text,
                    "usage": final_usage,
                }
                yield self._sse_event(
                    {
                        "type": "response.completed",
                        "response": response_payload,
                    }
                )
                self._record_gateway_request(
                    endpoint="/openai/v1/responses",
                    method="POST",
                    status_code=200,
                    duration=time.perf_counter() - started_at,
                    ai_model=model,
                    requested_model=payload.get("model"),
                    response_payload=response_payload,
                    upstream_response=response_payload,
                    endpoint_kind="responses_stream",
                    budget_result=budget_result,
                    request_payload=payload,
                )
                recorded = True
                yield self._sse_done()
            except Exception as exc:
                if not recorded:
                    self._record_gateway_request(
                        endpoint="/openai/v1/responses",
                        method="POST",
                        status_code=502,
                        duration=time.perf_counter() - started_at,
                        ai_model=model,
                        requested_model=payload.get("model"),
                        response_payload=None,
                        upstream_response=None,
                        endpoint_kind="responses_stream",
                        budget_result=budget_result,
                        error_detail=str(exc),
                        request_payload=payload,
                    )
                raise

        return event_stream()

    def _get_account_models(self) -> List[AIModel]:
        account_id = self.auth_context.user.account_id
        return (
            self.db.query(AIModel)
            .filter(or_(AIModel.account_id == account_id, AIModel.account_id.is_(None)))
            .all()
        )

    def _resolve_requested_model(
        self, requested_model: Optional[str], *, provider: GatewayProvider
    ) -> AIModel:
        models = self._get_account_models()
        gateway_enabled_models: List[tuple[AIModel, str]] = []
        default_gateway_model: Optional[AIModel] = None
        for ai_model in models:
            runtime = resolve_ai_model_runtime(ai_model)
            if runtime.model_gateway_enabled and runtime.model_gateway_model_alias:
                gateway_enabled_models.append(
                    (ai_model, runtime.model_gateway_model_alias)
                )
                if ai_model.is_default:
                    default_gateway_model = ai_model

        if requested_model:
            for ai_model, alias in gateway_enabled_models:
                if alias == requested_model:
                    return ai_model
            raise ModelGatewayAPIError(
                provider=provider,
                status_code=404,
                message="Requested model not found",
            )

        if default_gateway_model:
            return default_gateway_model

        raise ModelGatewayAPIError(
            provider=provider,
            status_code=404,
            message="No gateway-enabled default model configured",
        )

    def _call_litellm(
        self,
        ai_model: AIModel,
        *,
        messages: List[Dict[str, Any]],
        payload: Dict[str, Any],
        stream: bool = False,
        provider: GatewayProvider,
    ):
        resolved_secret = get_secret_service().resolve_ai_model_api_key(ai_model)
        if not resolved_secret:
            raise ModelGatewayAPIError(
                provider=provider,
                status_code=400,
                message="Model credentials are not configured",
            )

        kwargs: Dict[str, Any] = {
            "model": self._to_litellm_model(ai_model),
            "messages": messages,
            "api_key": resolved_secret.value,
        }
        if stream:
            kwargs["stream"] = True
            if payload.get("stream_options") is not None:
                kwargs["stream_options"] = payload["stream_options"]
        if ai_model.api_endpoint:
            kwargs["api_base"] = ai_model.api_endpoint
        if payload.get("tools") is not None:
            kwargs["tools"] = self._normalize_openai_tools(payload["tools"])
        if payload.get("tool_choice") is not None:
            kwargs["tool_choice"] = self._normalize_openai_tool_choice(
                payload["tool_choice"]
            )
        if payload.get("parallel_tool_calls") is not None:
            kwargs["parallel_tool_calls"] = payload["parallel_tool_calls"]

        for source_key, target_key in (
            ("temperature", "temperature"),
            ("max_tokens", "max_tokens"),
            ("max_completion_tokens", "max_tokens"),
        ):
            if payload.get(source_key) is not None and target_key not in kwargs:
                kwargs[target_key] = payload[source_key]

        try:
            return litellm.completion(**kwargs)
        except Exception as exc:
            raise self._normalize_upstream_error(provider, exc) from exc

    def _normalize_responses_input(
        self, payload: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        messages: List[Dict[str, Any]] = []
        instructions = payload.get("instructions")
        if instructions:
            messages.append({"role": "system", "content": instructions})

        raw_input = payload.get("input")
        if isinstance(raw_input, str):
            messages.append({"role": "user", "content": raw_input})
        elif isinstance(raw_input, list):
            for item in raw_input:
                if not isinstance(item, dict):
                    continue
                normalized = self._normalize_responses_input_item(item)
                if normalized:
                    messages.extend(normalized)

        if not messages:
            raise ModelGatewayAPIError(
                provider="openai",
                status_code=400,
                message="input must be provided",
            )
        return messages

    def _normalize_responses_input_item(
        self, item: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Convert one Responses API input item into chat-completions messages."""
        item_type = item.get("type")

        if item_type == "function_call":
            function_name = item.get("name")
            call_id = item.get("call_id")
            if not function_name or not call_id:
                return []
            return [
                {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "id": call_id,
                            "type": "function",
                            "function": {
                                "name": function_name,
                                "arguments": item.get("arguments") or "",
                            },
                        }
                    ],
                }
            ]

        if item_type == "function_call_output":
            call_id = item.get("call_id")
            if not call_id:
                return []
            return [
                {
                    "role": "tool",
                    "tool_call_id": call_id,
                    "content": self._content_to_text(item.get("output", "")),
                }
            ]

        role = item.get("role", "user")
        content = item.get("content", "")
        return [{"role": role, "content": self._content_to_text(content)}]

    def _normalize_anthropic_messages_input(
        self, payload: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Normalize Anthropic messages input to the internal chat format."""
        raw_messages = payload.get("messages")
        if not isinstance(raw_messages, list) or not raw_messages:
            raise ModelGatewayAPIError(
                provider="anthropic",
                status_code=400,
                message="messages must be a non-empty list",
            )

        messages: List[Dict[str, Any]] = []
        system_prompt = payload.get("system")
        if system_prompt:
            messages.append(
                {"role": "system", "content": self._content_to_text(system_prompt)}
            )

        for item in raw_messages:
            if not isinstance(item, dict):
                continue
            role = item.get("role", "user")
            content = item.get("content", "")
            messages.append({"role": role, "content": self._content_to_text(content)})

        if len(messages) == 0:
            raise ModelGatewayAPIError(
                provider="anthropic",
                status_code=400,
                message="messages must be a non-empty list",
            )
        return messages

    @staticmethod
    def _normalize_upstream_error(
        provider: GatewayProvider, exc: Exception
    ) -> ModelGatewayAPIError:
        status_code = (
            getattr(exc, "status_code", None) or getattr(exc, "status", None) or 502
        )
        try:
            status_code = int(status_code)
        except (TypeError, ValueError):
            status_code = 502

        if status_code < 400 or status_code > 599:
            status_code = 502

        message = (
            getattr(exc, "message", None)
            or getattr(exc, "detail", None)
            or str(exc)
            or "Gateway upstream error"
        )
        if status_code >= 500 and not getattr(exc, "status_code", None):
            message = f"Gateway upstream error: {message}"

        error_type = getattr(exc, "type", None) or getattr(exc, "error_type", None)
        code = getattr(exc, "code", None)
        return ModelGatewayAPIError(
            provider=provider,
            status_code=status_code,
            message=message,
            error_type=str(error_type) if error_type is not None else None,
            code=str(code) if code is not None else None,
        )

    @staticmethod
    def _to_litellm_model(ai_model: AIModel) -> str:
        provider = (ai_model.provider_name or "openai").strip().lower()
        prefix = _PROVIDER_PREFIX.get(provider, provider)
        return f"{prefix}/{ai_model.model_identifier}"

    @staticmethod
    def _response_to_dict(response: Any) -> Dict[str, Any]:
        if hasattr(response, "model_dump"):
            return response.model_dump()
        if isinstance(response, dict):
            return response
        return dict(response)

    @staticmethod
    def _content_to_text(content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            texts = []
            for item in content:
                if isinstance(item, dict) and item.get("type") in {
                    "input_text",
                    "text",
                    "output_text",
                }:
                    texts.append(item.get("text", ""))
            return "\n".join(filter(None, texts))
        return str(content)

    def _extract_assistant_text(self, response_dict: Dict[str, Any]) -> str:
        choices = response_dict.get("choices") or []
        if choices:
            message = choices[0].get("message") or {}
            content = message.get("content", "")
            return self._content_to_text(content)
        return ""

    def _extract_tool_calls(
        self, response_dict: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        choices = response_dict.get("choices") or []
        if not choices:
            return []
        message = choices[0].get("message") or {}
        tool_calls = message.get("tool_calls") or []
        return [tool_call for tool_call in tool_calls if isinstance(tool_call, dict)]

    def _extract_stream_delta_text(self, response_dict: Dict[str, Any]) -> str:
        """Extract text delta from a streamed chunk."""
        choices = response_dict.get("choices") or []
        if not choices:
            return ""
        delta = choices[0].get("delta") or {}
        content = delta.get("content", "")
        return self._content_to_text(content)

    def _extract_stream_tool_call_deltas(
        self, response_dict: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Extract streamed tool call deltas from one chunk."""
        choices = response_dict.get("choices") or []
        if not choices:
            return []
        delta = choices[0].get("delta") or {}
        tool_calls = delta.get("tool_calls") or []
        return [tool_call for tool_call in tool_calls if isinstance(tool_call, dict)]

    def _build_response_output_items(
        self, response_dict: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Build Responses API output items from one chat-completions payload."""
        output_items: List[Dict[str, Any]] = []
        assistant_text = self._extract_assistant_text(response_dict)
        if assistant_text:
            output_items.append(
                {
                    "id": response_dict.get("id", f"msg_{int(time.time())}"),
                    "type": "message",
                    "status": "completed",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": assistant_text}],
                }
            )
        for index, tool_call in enumerate(self._extract_tool_calls(response_dict)):
            function_payload = tool_call.get("function") or {}
            call_id = tool_call.get("id") or f"call_{index}"
            output_items.append(
                {
                    "id": f"fc_{call_id}",
                    "type": "function_call",
                    "status": "completed",
                    "call_id": call_id,
                    "name": function_payload.get("name", ""),
                    "arguments": function_payload.get("arguments", ""),
                }
            )
        return output_items

    @staticmethod
    def _response_output_text(output_items: List[Dict[str, Any]]) -> str:
        """Return the concatenated assistant text from response output items."""
        text_parts: List[str] = []
        for item in output_items:
            if item.get("type") != "message":
                continue
            for content in item.get("content") or []:
                if isinstance(content, dict) and content.get("type") == "output_text":
                    text_parts.append(content.get("text", ""))
        return "".join(text_parts)

    @staticmethod
    def _normalize_openai_tools(tools: Any) -> Any:
        """Normalize Responses API tools to chat-completions tool format."""
        if not isinstance(tools, list):
            return tools
        normalized_tools = []
        for tool in tools:
            if not isinstance(tool, dict):
                normalized_tools.append(tool)
                continue
            tool_type = tool.get("type")
            if tool_type in {
                "web_search",
                "web_search_preview",
                "file_search",
                "code_interpreter",
                "computer_use_preview",
            }:
                # Hosted Responses tools are not supported by the LiteLLM
                # compatibility path used by the gateway today.
                continue
            if tool_type == "custom" and not isinstance(tool.get("custom"), dict):
                custom_payload = {
                    key: value for key, value in tool.items() if key not in {"type"}
                }
                normalized_tools.append(
                    {
                        "type": "custom",
                        "custom": OpenAIGatewayService._normalize_custom_tool_payload(
                            custom_payload
                        ),
                    }
                )
                continue
            if tool_type != "function":
                normalized_tools.append(tool)
                continue
            function_name = tool.get("name")
            if not function_name:
                normalized_tools.append(tool)
                continue
            normalized_tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": function_name,
                        "description": tool.get("description"),
                        "parameters": tool.get("parameters") or {"type": "object"},
                    },
                }
            )
        return normalized_tools

    @staticmethod
    def _normalize_custom_tool_payload(
        custom_payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Normalize flat custom tool payloads for LiteLLM/OpenAI compatibility."""
        normalized_payload = dict(custom_payload)
        custom_format = normalized_payload.get("format")
        if isinstance(custom_format, dict) and custom_format.get("type") == "grammar":
            grammar_payload = custom_format.get("grammar")
            if isinstance(grammar_payload, dict):
                normalized_grammar = dict(grammar_payload)
            else:
                normalized_grammar = {}

            if normalized_grammar.get("syntax") is None and custom_format.get("syntax"):
                normalized_grammar["syntax"] = custom_format["syntax"]
            if (
                normalized_grammar.get("definition") is None
                and custom_format.get("definition") is not None
            ):
                normalized_grammar["definition"] = custom_format["definition"]
            if normalized_grammar.get("definition") is None and isinstance(
                grammar_payload, str
            ):
                normalized_grammar["definition"] = grammar_payload

            normalized_payload["format"] = {
                "type": "grammar",
                "grammar": normalized_grammar,
            }
        return normalized_payload

    @staticmethod
    def _normalize_openai_tool_choice(tool_choice: Any) -> Any:
        """Normalize Responses API tool_choice to chat-completions format."""
        if not isinstance(tool_choice, dict) or tool_choice.get("type") != "function":
            return tool_choice
        function_name = tool_choice.get("name")
        if not function_name:
            return tool_choice
        return {
            "type": "function",
            "function": {"name": function_name},
        }

    @staticmethod
    def _extract_finish_reason(response_dict: Dict[str, Any]) -> Optional[str]:
        choices = response_dict.get("choices") or []
        if not choices:
            return None
        return choices[0].get("finish_reason")

    @staticmethod
    def _normalize_usage(
        usage: Optional[Dict[str, Any]],
        *,
        prompt_key: str,
        completion_key: str,
        output_names: tuple[str, ...] = ("completion_tokens",),
    ) -> Dict[str, int]:
        usage = usage or {}
        prompt_tokens = int(usage.get(prompt_key, usage.get("input_tokens", 0)) or 0)
        completion_tokens = 0
        for key in output_names:
            if usage.get(key) is not None:
                completion_tokens = int(usage.get(key) or 0)
                break
        total_tokens = int(
            usage.get("total_tokens", prompt_tokens + completion_tokens) or 0
        )
        return {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
        }

    def _record_gateway_request(
        self,
        *,
        endpoint: str,
        method: str,
        status_code: int,
        duration: float,
        ai_model: AIModel,
        requested_model: Optional[str],
        response_payload: Optional[Dict[str, Any]],
        upstream_response: Optional[Dict[str, Any]],
        endpoint_kind: str,
        budget_result: Optional[BudgetCheckResult] = None,
        error_detail: Optional[str] = None,
        request_payload: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Persist one usage fact for a gateway request."""
        runtime = resolve_ai_model_runtime(ai_model)
        usage = response_payload.get("usage") if response_payload else {}
        prompt_tokens = usage.get("prompt_tokens") or usage.get("input_tokens") or 0
        completion_tokens = (
            usage.get("completion_tokens") or usage.get("output_tokens") or 0
        )
        total_tokens = usage.get("total_tokens")
        if total_tokens is None and (prompt_tokens or completion_tokens):
            total_tokens = prompt_tokens + completion_tokens
        runtime_context = (
            (self.auth_context.api_key.context_data or {})
            if self.auth_context.api_key
            else {}
        )
        runtime_principal = runtime_context.get("runtime_principal") or {}

        usage_row = crud_api_usage.log_gateway_request(
            self.db,
            endpoint=endpoint,
            method=method,
            status_code=status_code,
            duration=duration,
            user_id=str(self.auth_context.user.id),
            account_id=str(self.auth_context.user.account_id),
            api_key_id=(
                str(self.auth_context.api_key.id) if self.auth_context.api_key else None
            ),
            auth_subject_type=(
                "api_key"
                if self.auth_context.api_key
                else "oauth_mcp_token"
                if self.auth_context.oauth_access_token
                else "user_token"
            ),
            ai_model_id=str(ai_model.id),
            flow_id=runtime_context.get("flow_id"),
            flow_execution_id=runtime_context.get("flow_execution_id"),
            runtime_session_id=runtime_context.get("runtime_session_id"),
            model_alias=runtime.model_gateway_model_alias or requested_model,
            provider_name=ai_model.provider_name,
            upstream_request_id=(
                upstream_response.get("id") if upstream_response else None
            ),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            estimated_cost=self._estimate_cost(
                ai_model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens or 0,
            ),
            runtime_principal_type=runtime_principal.get("type"),
            runtime_principal_id=runtime_principal.get("id"),
            runtime_principal_name=runtime_principal.get("name"),
            meta_data={
                "endpoint_kind": endpoint_kind,
                "requested_model": requested_model,
                "gateway_provider": runtime.model_gateway_provider,
                "error_detail": error_detail,
                "budget": self._budget_meta_data(budget_result),
                "finish_reason": self._extract_finish_reason(upstream_response or {})
                if upstream_response
                else None,
            },
        )
        observed_at = usage_row.timestamp
        runtime_session = None
        if usage_row.runtime_session_id:
            runtime_session = crud_runtime_session.touch_activity(
                self.db,
                account_id=self.auth_context.user.account_id,
                runtime_session_id=usage_row.runtime_session_id,
                observed_at=observed_at,
            )
            if runtime_session is not None:
                emit_account_event(
                    build_account_event(
                        account_id=str(self.auth_context.user.account_id),
                        topic=ACCOUNT_TOPIC_RUNTIME_SESSIONS,
                        event_type="runtime_session_updated",
                        payload={
                            "runtime_session_id": str(runtime_session.id),
                            "session_source_type": runtime_session.session_source_type,
                            "session_source_id": runtime_session.session_source_id,
                            "session_reference": runtime_session.session_reference,
                            "runtime_principal_type": runtime_session.runtime_principal_type,
                            "runtime_principal_id": runtime_session.runtime_principal_id,
                            "runtime_principal_name": runtime_session.runtime_principal_name,
                            "last_activity_at": runtime_session.last_activity_at.isoformat()
                            if runtime_session.last_activity_at
                            else None,
                            "last_request_at": observed_at.isoformat(),
                            "ended_at": runtime_session.ended_at.isoformat()
                            if runtime_session.ended_at
                            else None,
                        },
                        runtime_session_id=str(runtime_session.id),
                        execution_id=str(usage_row.flow_execution_id)
                        if usage_row.flow_execution_id
                        else None,
                        flow_id=str(usage_row.flow_id) if usage_row.flow_id else None,
                    )
                )

        managed_agent = None
        if usage_row.runtime_principal_type and usage_row.runtime_principal_id:
            managed_agent = crud_managed_agent.touch_last_seen_for_principal(
                self.db,
                account_id=self.auth_context.user.account_id,
                session_source_type=usage_row.runtime_principal_type,
                session_source_id=usage_row.runtime_principal_id,
                runtime_session_id=usage_row.runtime_session_id,
                observed_at=observed_at,
            )
            if managed_agent is not None:
                emit_account_event(
                    build_account_event(
                        account_id=str(self.auth_context.user.account_id),
                        topic=ACCOUNT_TOPIC_MANAGED_AGENTS,
                        event_type="managed_agent_updated",
                        payload={
                            "agent_id": str(managed_agent.id),
                            "runtime_session_id": str(managed_agent.runtime_session_id)
                            if managed_agent.runtime_session_id
                            else None,
                            "display_name": managed_agent.display_name,
                            "session_source_type": managed_agent.session_source_type,
                            "session_source_id": managed_agent.session_source_id,
                            "session_reference": managed_agent.session_reference,
                            "last_seen_at": managed_agent.last_seen_at.isoformat(),
                        },
                        runtime_session_id=str(usage_row.runtime_session_id)
                        if usage_row.runtime_session_id
                        else None,
                        execution_id=str(usage_row.flow_execution_id)
                        if usage_row.flow_execution_id
                        else None,
                        flow_id=str(usage_row.flow_id) if usage_row.flow_id else None,
                    )
                )

        log_model_gateway_request(
            self.db,
            account_id=self.auth_context.user.account_id,
            user_id=self.auth_context.user.id,
            api_usage_id=str(usage_row.id),
            endpoint=endpoint,
            endpoint_kind=endpoint_kind,
            status_code=status_code,
            outcome=(
                "success"
                if status_code < 400
                else self._audit_outcome(status_code, error_detail)
            ),
            requested_model=requested_model,
            model_alias=runtime.model_gateway_model_alias or requested_model,
            provider_name=ai_model.provider_name,
            gateway_provider=runtime.model_gateway_provider,
            auth_subject_type=usage_row.auth_subject_type,
            runtime_session_id=(
                str(usage_row.runtime_session_id)
                if usage_row.runtime_session_id
                else None
            ),
            runtime_principal_type=usage_row.runtime_principal_type,
            runtime_principal_id=usage_row.runtime_principal_id,
            runtime_principal_name=usage_row.runtime_principal_name,
            api_key_id=(
                str(self.auth_context.api_key.id) if self.auth_context.api_key else None
            ),
            api_key_name=self.auth_context.api_key.name
            if self.auth_context.api_key
            else None,
            flow_id=str(usage_row.flow_id) if usage_row.flow_id else None,
            flow_execution_id=(
                str(usage_row.flow_execution_id)
                if usage_row.flow_execution_id
                else None
            ),
            upstream_request_id=usage_row.upstream_request_id,
            error_detail=error_detail,
            error_type=(
                self._audit_error_type(status_code, error_detail)
                if status_code >= 400
                else None
            ),
            budget=self._budget_meta_data(budget_result),
        )
        ModelGatewayEventEmitter(self.db).emit_for_usage(
            usage=usage_row,
            request_payload=request_payload,
            response_payload=response_payload,
        )
        try:
            GatewayUsageSearchService(self.db).auto_index_interaction(
                usage=usage_row,
                request_payload=request_payload,
                response_payload=response_payload,
            )
        except Exception:
            logger.exception(
                "Automatic gateway interaction indexing failed for usage %s",
                usage_row.id,
            )

    @staticmethod
    def _estimate_cost(
        ai_model: AIModel,
        *,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int,
    ) -> Optional[float]:
        """Estimate request cost from model pricing metadata."""
        pricing = None
        if ai_model.meta_data and isinstance(ai_model.meta_data, dict):
            pricing = ai_model.meta_data.get("pricing")
        if (
            not pricing
            and ai_model.model_parameters
            and isinstance(ai_model.model_parameters, dict)
        ):
            pricing = ai_model.model_parameters.get("pricing")
        if not pricing or not isinstance(pricing, dict):
            return None

        input_price_per_1k = pricing.get("input_price_per_1k")
        output_price_per_1k = pricing.get("output_price_per_1k")
        if input_price_per_1k is not None or output_price_per_1k is not None:
            input_cost = (prompt_tokens / 1000.0) * float(input_price_per_1k or 0)
            output_cost = (completion_tokens / 1000.0) * float(output_price_per_1k or 0)
            return round(input_cost + output_cost, 6)

        price_per_1k = pricing.get("price_per_1k")
        if price_per_1k is not None:
            return round((total_tokens / 1000.0) * float(price_per_1k), 6)

        return None

    def _check_budget(
        self, ai_model: AIModel, payload: Dict[str, Any]
    ) -> Optional[BudgetCheckResult]:
        """Check configured gateway budgets before the upstream call."""
        return ModelGatewayBudgetService(self.db, self.auth_context).preflight_check(
            ai_model, payload
        )

    @staticmethod
    def _budget_meta_data(
        budget_result: Optional[BudgetCheckResult],
    ) -> Optional[Dict[str, Any]]:
        if not budget_result:
            return None
        return {
            "pricing_available": budget_result.pricing_available,
            "estimated_request_cost_usd": budget_result.estimated_request_cost_usd,
            "account_current_spend_usd": budget_result.account_current_spend_usd,
            "account_estimated_total_usd": budget_result.account_estimated_total_usd,
            "account_limit_usd": budget_result.account_limit_usd,
            "account_soft_limit_usd": budget_result.account_soft_limit_usd,
            "flow_current_spend_usd": budget_result.flow_current_spend_usd,
            "flow_estimated_total_usd": budget_result.flow_estimated_total_usd,
            "flow_limit_usd": budget_result.flow_limit_usd,
            "flow_soft_limit_usd": budget_result.flow_soft_limit_usd,
            "soft_limit_exceeded": budget_result.soft_limit_exceeded,
            "hard_limit_exceeded": budget_result.hard_limit_exceeded,
            "enforcement_reason": budget_result.enforcement_reason,
        }

    @staticmethod
    def _budget_denial_detail(budget_result: BudgetCheckResult) -> str:
        if budget_result.enforcement_reason == "account_budget_exceeded":
            return "Model gateway budget exceeded: account monthly limit reached"
        if budget_result.enforcement_reason == "flow_budget_exceeded":
            return "Model gateway budget exceeded: flow monthly limit reached"
        if (
            budget_result.enforcement_reason
            == "pricing_required_for_budget_enforcement"
        ):
            return (
                "Model gateway budget enforcement requires pricing metadata for "
                "the selected gateway model"
            )
        return "Model gateway budget exceeded"

    @staticmethod
    def _audit_outcome(status_code: int, error_detail: Optional[str]) -> str:
        if (
            status_code == 403
            and error_detail
            and (
                "budget exceeded" in error_detail.lower()
                or "budget enforcement requires pricing metadata"
                in error_detail.lower()
            )
        ):
            return "budget_denied"
        return "failed"

    @staticmethod
    def _audit_error_type(status_code: int, error_detail: Optional[str]) -> str:
        if (
            status_code == 403
            and error_detail
            and (
                "budget exceeded" in error_detail.lower()
                or "budget enforcement requires pricing metadata"
                in error_detail.lower()
            )
        ):
            return "budget_limit_exceeded"
        if status_code == 400:
            return "validation_error"
        if status_code == 401:
            return "authentication_error"
        if status_code == 403:
            return "permission_error"
        if status_code == 404:
            return "not_found_error"
        if status_code == 429:
            return "rate_limit_error"
        if status_code >= 500:
            return "upstream_error"
        return "gateway_error"

    @staticmethod
    def _to_anthropic_stop_reason(finish_reason: Optional[str]) -> Optional[str]:
        mapping = {
            "stop": "end_turn",
            "length": "max_tokens",
            "content_filter": "stop_sequence",
            "tool_calls": "tool_use",
        }
        return mapping.get(finish_reason or "", "end_turn" if finish_reason else None)

    @staticmethod
    def _build_anthropic_message_payload(
        *,
        response_id: str,
        model_name: Optional[str],
        assistant_text: str,
        stop_reason: Optional[str],
        usage: Dict[str, int],
    ) -> Dict[str, Any]:
        return {
            "id": response_id,
            "type": "message",
            "role": "assistant",
            "content": [{"type": "text", "text": assistant_text}],
            "model": model_name,
            "stop_reason": stop_reason,
            "stop_sequence": None,
            "usage": {
                "input_tokens": usage["prompt_tokens"],
                "output_tokens": usage["completion_tokens"],
            },
        }

    def _normalize_chat_stream_chunk(
        self,
        chunk_dict: Dict[str, Any],
        *,
        model_name: Optional[str],
        response_id: str,
        created_at: int,
    ) -> Dict[str, Any]:
        """Normalize one streamed chat chunk to OpenAI-compatible shape."""
        payload = {
            "id": chunk_dict.get("id", response_id),
            "object": chunk_dict.get("object", "chat.completion.chunk"),
            "created": chunk_dict.get("created", created_at),
            "model": model_name,
            "choices": [],
        }
        for choice in chunk_dict.get("choices") or []:
            delta = choice.get("delta") or {}
            if not delta and choice.get("message"):
                delta = {
                    "content": self._content_to_text(
                        choice["message"].get("content", "")
                    )
                }
            payload["choices"].append(
                {
                    "index": choice.get("index", 0),
                    "delta": delta,
                    "finish_reason": choice.get("finish_reason"),
                }
            )
        if chunk_dict.get("usage") is not None:
            payload["usage"] = self._normalize_usage(
                chunk_dict.get("usage"),
                prompt_key="prompt_tokens",
                completion_key="completion_tokens",
            )
        return payload

    @staticmethod
    def _sse_event(payload: Any) -> str:
        return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

    @staticmethod
    def _sse_done() -> str:
        return "data: [DONE]\n\n"

    @staticmethod
    def _anthropic_sse_event(event_name: str, payload: Any) -> str:
        return (
            f"event: {event_name}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
        )
