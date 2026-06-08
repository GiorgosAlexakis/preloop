"""Standalone Hermes plugin entrypoint for Preloop."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any
from urllib import parse, request
from uuid import uuid4

import yaml

from preloop.integrations.agent_control import (
    AgentControlCapabilities,
    AgentControlClient,
    AgentControlConfig,
    AgentControlRuntimeHooks,
    create_hermes_agent_control_client,
    load_hermes_control_config,
)


class HermesPreloopPlugin:
    """Hermes plugin wrapper around Preloop's Agent Control client."""

    runtime_name = "hermes"

    def __init__(self, config_path: Path | None = None) -> None:
        self.config_path = config_path
        self.client: AgentControlClient | None = None

    def load_config(self) -> AgentControlConfig:
        """Load the `preloop.control` block from Hermes configuration."""
        return load_hermes_control_config(self.config_path)

    def capabilities(self) -> AgentControlCapabilities:
        """Advertise the Hermes control surface exposed by this plugin."""
        return AgentControlCapabilities(
            send_text_prompt=True,
            send_voice_transcript=True,
            supports_new_session=True,
            supports_existing_session=True,
            supports_interrupt=True,
        )

    async def start(self, hermes_runtime: Any | None = None) -> AgentControlClient:
        """Create and connect the Preloop WebSocket client."""
        hooks = AgentControlRuntimeHooks(
            send_text_prompt=self._build_text_handler(hermes_runtime),
            send_voice_transcript=self._build_voice_handler(hermes_runtime),
            interrupt=self._build_interrupt_handler(hermes_runtime),
        )
        self.client = create_hermes_agent_control_client(
            self.config_path,
            runtime_hooks=hooks,
            capabilities=self.capabilities(),
        )
        await self.client.connect_forever()
        return self.client

    def verify(self) -> None:
        """Validate local plugin load and config shape."""
        config = self.load_config()
        if config.runtime != self.runtime_name:
            raise ValueError(f"Expected Hermes runtime config, got {config.runtime!r}")
        if not config.control_ws_url:
            raise ValueError("preloop.control.control_ws_url is required")
        if not config.bearer_token:
            raise ValueError("preloop.control.bearer_token is required")

    def login(self, base_url: str) -> None:
        """Bootstrap Preloop auth and write Hermes Agent Control config."""
        config_path = self.config_path or Path.home() / ".hermes" / "config.yaml"
        runtime_principal_id = f"hermes-{uuid4()}"
        authorize_url = _build_url(
            base_url,
            "/oauth/authorize",
            {
                "response_type": "code",
                "client_id": "cli",
                "redirect_uri": "urn:ietf:wg:oauth:2.0:oob",
                "scope": "offline_access",
            },
        )
        print("Open this Preloop login/signup URL:")
        print(authorize_url)
        code = input("Paste the authorization code: ").strip()
        if not code:
            raise ValueError("Authorization code is required")

        token_response = _post_form(
            _build_url(base_url, "/oauth/token"),
            {
                "grant_type": "authorization_code",
                "code": code,
                "client_id": "cli",
                "redirect_uri": "urn:ietf:wg:oauth:2.0:oob",
            },
        )
        access_token = str(token_response.get("access_token") or "")
        if not access_token:
            raise ValueError("Preloop did not return an access token")

        runtime_session = _post_json(
            _build_url(base_url, "/api/v1/auth/runtime-sessions/token"),
            {
                "session_source_type": "hermes",
                "session_source_id": runtime_principal_id,
                "session_reference": str(config_path),
                "runtime_principal_name": "Hermes",
            },
            access_token,
        )
        runtime_token = str(runtime_session.get("token") or "")
        if not runtime_token:
            raise ValueError("Preloop did not return a runtime token")

        document: dict[str, Any] = {}
        if config_path.exists():
            loaded = yaml.safe_load(config_path.read_text())
            if isinstance(loaded, dict):
                document = loaded
        preloop = document.setdefault("preloop", {})
        preloop["control"] = {
            "enabled": True,
            "protocol": "preloop.agent_control.v1",
            "runtime": "hermes",
            "control_ws_url": _websocket_url(base_url),
            "bearer_token": runtime_token,
            "managed_agent_id": runtime_session.get("managed_agent_id"),
            "runtime_session_id": runtime_session.get("runtime_session_id"),
            "runtime_principal_id": runtime_principal_id,
            "runtime_principal_name": "Hermes",
            "session_reference": str(config_path),
        }
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(yaml.safe_dump(document, sort_keys=False))
        print(f"Wrote Preloop Agent Control config to {config_path}")

    def _build_text_handler(self, hermes_runtime: Any | None) -> Any:
        async def send_text_prompt(command: Any) -> Any:
            if hermes_runtime and hasattr(hermes_runtime, "send_prompt"):
                return await hermes_runtime.send_prompt(
                    command.message, command.metadata
                )
            raise RuntimeError("Hermes runtime hook send_prompt is not available")

        return send_text_prompt

    def _build_voice_handler(self, hermes_runtime: Any | None) -> Any:
        async def send_voice_transcript(command: Any) -> Any:
            if hermes_runtime and hasattr(hermes_runtime, "send_voice_transcript"):
                return await hermes_runtime.send_voice_transcript(
                    command.message,
                    command.metadata,
                )
            if hermes_runtime and hasattr(hermes_runtime, "send_prompt"):
                return await hermes_runtime.send_prompt(
                    command.message, command.metadata
                )
            raise RuntimeError("Hermes runtime voice hook is not available")

        return send_voice_transcript

    def _build_interrupt_handler(self, hermes_runtime: Any | None) -> Any:
        async def interrupt(command: Any) -> Any:
            if hermes_runtime and hasattr(hermes_runtime, "interrupt"):
                return await hermes_runtime.interrupt(command.metadata)
            raise RuntimeError("Hermes runtime interrupt hook is not available")

        return interrupt


plugin = HermesPreloopPlugin()


def main() -> None:
    """CLI helper used by marketplace verification commands."""
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["login", "run", "verify"])
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--base-url", default="https://app.preloop.ai")
    args = parser.parse_args()

    instance = HermesPreloopPlugin(args.config)
    if args.command == "login":
        instance.login(args.base_url)
        return
    if args.command == "verify":
        instance.verify()
        print("preloop-hermes-plugin verified")
        return

    asyncio.run(instance.start())


def _build_url(
    base_url: str,
    path: str,
    query: dict[str, str] | None = None,
) -> str:
    url = base_url.rstrip("/") + path
    if query:
        url += "?" + parse.urlencode(query)
    return url


def _websocket_url(base_url: str) -> str:
    parsed = parse.urlparse(base_url.rstrip() + "/api/v1/agents/control/ws")
    scheme = "ws" if parsed.scheme == "http" else "wss"
    return parse.urlunparse(parsed._replace(scheme=scheme))


def _post_form(url: str, fields: dict[str, str]) -> dict[str, Any]:
    data = parse.urlencode(fields).encode()
    req = request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with request.urlopen(req, timeout=30) as response:
        return json.loads(response.read())


def _post_json(url: str, body: dict[str, Any], access_token: str) -> dict[str, Any]:
    req = request.Request(
        url,
        data=json.dumps(body).encode(),
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
    )
    with request.urlopen(req, timeout=30) as response:
        return json.loads(response.read())


if __name__ == "__main__":
    main()
