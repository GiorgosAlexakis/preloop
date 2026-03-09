"""Provider-agnostic secret resolution service."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import logging
from typing import Optional, Protocol
from urllib import error as urllib_error
from urllib import parse as urllib_parse
from urllib import request as urllib_request
from uuid import UUID

from sqlalchemy.orm import Session

from preloop.config import settings
from preloop.models.crud.secret_reference import crud_secret_reference
from preloop.models.models.ai_model import AIModel
from preloop.models.models.secret_reference import SecretReference
from preloop.utils.encryption import decrypt_value, encrypt_value

logger = logging.getLogger(__name__)


LOCAL_ENCRYPTED_BACKEND = "local_encrypted"
VAULT_KV_V2_BACKEND = "vault_kv_v2"
OPENBAO_KV_V2_BACKEND = "openbao_kv_v2"


@dataclass
class ResolvedSecret:
    """Resolved secret value plus non-sensitive metadata."""

    value: str
    backend_type: str
    secret_reference_id: Optional[UUID] = None


class SecretBackend(Protocol):
    """Interface for secret backend adapters."""

    backend_type: str

    def validate_reference(
        self,
        *,
        external_ref: Optional[str],
        meta_data: Optional[dict],
    ) -> None:
        """Validate a backend-specific reference before storing it."""

    def resolve(self, secret_ref: SecretReference) -> str:
        """Resolve the secret value from the backend."""


class LocalEncryptedSecretBackend:
    """Local encrypted secret backend stored in the database."""

    backend_type = LOCAL_ENCRYPTED_BACKEND

    def validate_reference(
        self,
        *,
        external_ref: Optional[str],
        meta_data: Optional[dict],
    ) -> None:
        if external_ref:
            raise ValueError("local_encrypted backend does not accept external_ref")

    def resolve(self, secret_ref: SecretReference) -> str:
        if not secret_ref.encrypted_value:
            return ""
        return decrypt_value(secret_ref.encrypted_value)


class VaultKVV2SecretBackend:
    """Vault/OpenBao-compatible KV v2 secret backend."""

    def __init__(self, backend_type: str = VAULT_KV_V2_BACKEND) -> None:
        self.backend_type = backend_type

    def validate_reference(
        self,
        *,
        external_ref: Optional[str],
        meta_data: Optional[dict],
    ) -> None:
        if not settings.vault_kv_v2.is_configured:
            raise ValueError(
                f"{self.backend_type} backend is not configured on this Preloop instance"
            )
        if not external_ref:
            raise ValueError(f"{self.backend_type} requires credentials_external_ref")
        field = (meta_data or {}).get("field")
        if field is not None and not isinstance(field, str):
            raise ValueError("credentials_meta_data.field must be a string")
        self._normalize_external_ref(external_ref)

    def resolve(self, secret_ref: SecretReference) -> str:
        self.validate_reference(
            external_ref=secret_ref.external_ref,
            meta_data=secret_ref.meta_data,
        )
        path = self._build_secret_path(secret_ref.external_ref or "")
        payload = self._read_secret(path, secret_ref.meta_data or {})
        data = payload.get("data", {}).get("data", {})
        field = (secret_ref.meta_data or {}).get("field", "value")
        value = data.get(field)
        if value is None:
            raise ValueError(
                f"Secret field '{field}' not found for backend {self.backend_type}"
            )
        return str(value)

    def _build_secret_path(self, external_ref: str) -> str:
        raw_ref = self._normalize_external_ref(external_ref)
        prefix = settings.vault_kv_v2.path_prefix.strip().strip("/")
        path = f"{prefix}/{raw_ref}" if prefix else raw_ref
        return f"{settings.vault_kv_v2.mount.strip('/')}/data/{path}"

    @staticmethod
    def _normalize_external_ref(external_ref: str) -> str:
        raw_ref = external_ref.strip()
        if not raw_ref:
            raise ValueError("credentials_external_ref must not be empty")
        if raw_ref != urllib_parse.unquote(raw_ref):
            raise ValueError(
                "credentials_external_ref must not contain percent-encoded characters"
            )

        normalized_parts: list[str] = []
        for part in raw_ref.split("/"):
            normalized_part = part.strip()
            if normalized_part in {"", ".", ".."}:
                raise ValueError(
                    "credentials_external_ref must be a relative secret path "
                    "without empty or traversal segments"
                )
            if "\\" in normalized_part:
                raise ValueError(
                    "credentials_external_ref must use forward slashes only"
                )
            if any(ord(char) < 32 for char in normalized_part):
                raise ValueError(
                    "credentials_external_ref must not contain control characters"
                )
            normalized_parts.append(normalized_part)

        return "/".join(normalized_parts)

    def _read_secret(self, path: str, meta_data: dict) -> dict:
        base_url = settings.vault_kv_v2.url.rstrip("/")
        params = {}
        if meta_data.get("version") is not None:
            params["version"] = str(meta_data["version"])
        query = f"?{urllib_parse.urlencode(params)}" if params else ""
        url = f"{base_url}/v1/{path}{query}"
        req = urllib_request.Request(
            url,
            headers=self._build_headers(),
            method="GET",
        )
        ssl_context = None
        if not settings.vault_kv_v2.verify_tls:
            import ssl

            ssl_context = ssl._create_unverified_context()
        elif settings.vault_kv_v2.ca_cert_path:
            import ssl

            ssl_context = ssl.create_default_context(
                cafile=settings.vault_kv_v2.ca_cert_path
            )

        try:
            with urllib_request.urlopen(
                req,
                timeout=settings.vault_kv_v2.timeout_seconds,
                context=ssl_context,
            ) as response:
                import json

                return json.loads(response.read().decode("utf-8"))
        except urllib_error.HTTPError as exc:
            raise ValueError(
                f"{self.backend_type} secret lookup failed with status {exc.code}"
            ) from exc
        except urllib_error.URLError as exc:
            raise ValueError(
                f"{self.backend_type} secret lookup failed: {exc.reason}"
            ) from exc

    def _build_headers(self) -> dict[str, str]:
        headers = {"X-Vault-Token": settings.vault_kv_v2.token}
        if settings.vault_kv_v2.namespace:
            headers["X-Vault-Namespace"] = settings.vault_kv_v2.namespace
        return headers


class SecretService:
    """Secret storage and resolution service."""

    def __init__(self) -> None:
        self._backends: dict[str, SecretBackend] = {
            LOCAL_ENCRYPTED_BACKEND: LocalEncryptedSecretBackend(),
        }
        if settings.vault_kv_v2.is_configured:
            self._backends[VAULT_KV_V2_BACKEND] = VaultKVV2SecretBackend(
                VAULT_KV_V2_BACKEND
            )
            self._backends[OPENBAO_KV_V2_BACKEND] = VaultKVV2SecretBackend(
                OPENBAO_KV_V2_BACKEND
            )

    def create_local_secret_reference(
        self,
        db: Session,
        *,
        account_id: Optional[UUID],
        name: str,
        secret_kind: str,
        secret_value: str,
        existing_secret_id: Optional[UUID] = None,
    ) -> SecretReference:
        """Create or update a locally encrypted secret reference."""
        encrypted_value = encrypt_value(secret_value)
        now = datetime.now(timezone.utc)

        if existing_secret_id:
            secret_ref = crud_secret_reference.get(db, id=existing_secret_id)
            if secret_ref:
                secret_ref.name = name
                secret_ref.backend_type = LOCAL_ENCRYPTED_BACKEND
                secret_ref.secret_kind = secret_kind
                secret_ref.encrypted_value = encrypted_value
                secret_ref.status = "active"
                secret_ref.last_verified_at = now
                db.add(secret_ref)
                db.commit()
                db.refresh(secret_ref)
                return secret_ref

        secret_ref = crud_secret_reference.create(
            db,
            obj_in={
                "account_id": account_id,
                "name": name,
                "backend_type": LOCAL_ENCRYPTED_BACKEND,
                "secret_kind": secret_kind,
                "encrypted_value": encrypted_value,
                "status": "active",
                "last_verified_at": now,
                "meta_data": {},
                "created_at": now,
                "updated_at": now,
            },
        )
        return secret_ref

    def create_external_secret_reference(
        self,
        db: Session,
        *,
        account_id: Optional[UUID],
        name: str,
        secret_kind: str,
        backend_type: str,
        external_ref: str,
        meta_data: Optional[dict] = None,
        existing_secret_id: Optional[UUID] = None,
    ) -> SecretReference:
        """Create or update a secret reference backed by an external secret store."""
        backend = self._backends.get(backend_type)
        if not backend:
            raise ValueError(f"Unsupported secret backend: {backend_type}")
        backend.validate_reference(external_ref=external_ref, meta_data=meta_data)
        now = datetime.now(timezone.utc)

        if existing_secret_id:
            secret_ref = crud_secret_reference.get(db, id=existing_secret_id)
            if secret_ref:
                secret_ref.name = name
                secret_ref.backend_type = backend_type
                secret_ref.secret_kind = secret_kind
                secret_ref.encrypted_value = None
                secret_ref.external_ref = external_ref
                secret_ref.status = "active"
                secret_ref.last_verified_at = now
                secret_ref.meta_data = meta_data or {}
                db.add(secret_ref)
                db.commit()
                db.refresh(secret_ref)
                return secret_ref

        return crud_secret_reference.create(
            db,
            obj_in={
                "account_id": account_id,
                "name": name,
                "backend_type": backend_type,
                "secret_kind": secret_kind,
                "encrypted_value": None,
                "external_ref": external_ref,
                "status": "active",
                "last_verified_at": now,
                "meta_data": meta_data or {},
                "created_at": now,
                "updated_at": now,
            },
        )

    def resolve_secret_reference(self, secret_ref: SecretReference) -> ResolvedSecret:
        """Resolve a secret from its backend."""
        backend = self._backends.get(secret_ref.backend_type)
        if not backend:
            raise ValueError(f"Unsupported secret backend: {secret_ref.backend_type}")

        value = backend.resolve(secret_ref)
        return ResolvedSecret(
            value=value,
            backend_type=secret_ref.backend_type,
            secret_reference_id=secret_ref.id,
        )

    def resolve_ai_model_api_key(self, ai_model: AIModel) -> Optional[ResolvedSecret]:
        """Resolve the API key for an AI model."""
        if ai_model.credentials_secret:
            return self.resolve_secret_reference(ai_model.credentials_secret)

        if ai_model.api_key:
            # Legacy plaintext fallback while existing deployments are migrated.
            return ResolvedSecret(
                value=ai_model.api_key, backend_type="legacy_plaintext"
            )

        return None


_secret_service: Optional[SecretService] = None


def get_secret_service() -> SecretService:
    """Get or create the singleton secret service."""
    global _secret_service
    if _secret_service is None:
        _secret_service = SecretService()
    return _secret_service
