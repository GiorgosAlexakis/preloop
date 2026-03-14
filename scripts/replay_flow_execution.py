#!/usr/bin/env python
"""Replay a stored flow execution locally using its captured trigger payload."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import click
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from preloop.config import settings
from preloop.models.crud import crud_flow, crud_flow_execution
from preloop.models.db.session import get_db_session, get_session_factory
from preloop.models.models.flow_execution import FlowExecution
from preloop.models.models.flow_execution_log import FlowExecutionLog
from preloop.models.models.runtime_session_activity import RuntimeSessionActivity
from preloop.services.flow_trigger_service import FlowTriggerService

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


@dataclass
class SourceExecution:
    execution_id: str
    flow_id: str
    flow_name: Optional[str]
    trigger_event_data: dict[str, Any]


def _dump_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _query_execution_from_database(
    database_url: str, execution_id: str
) -> SourceExecution:
    engine = create_engine(database_url)
    session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = session_factory()
    try:
        row = (
            session.execute(
                text(
                    """
                select
                    e.id::text as execution_id,
                    e.flow_id::text as flow_id,
                    f.name as flow_name,
                    e.trigger_event_details::text as trigger_event_details
                from flow_execution e
                join flow f on f.id = e.flow_id
                where e.id = :execution_id
                """
                ),
                {"execution_id": execution_id},
            )
            .mappings()
            .first()
        )
        if not row:
            raise click.ClickException(
                f"Execution {execution_id} was not found in the source database."
            )
        trigger_event_details = row["trigger_event_details"]
        return SourceExecution(
            execution_id=row["execution_id"],
            flow_id=row["flow_id"],
            flow_name=row["flow_name"],
            trigger_event_data=json.loads(trigger_event_details)
            if trigger_event_details
            else {},
        )
    finally:
        session.close()
        engine.dispose()


def _query_execution_from_kubectl_psql(
    *,
    namespace: str,
    pod: str,
    execution_id: str,
    db_name: str,
    db_user: str,
    container: Optional[str],
) -> SourceExecution:
    sql = (
        "select "
        "e.id::text, "
        "e.flow_id::text, "
        "coalesce(f.name, ''), "
        "coalesce(e.trigger_event_details::text, '{}') "
        "from flow_execution e "
        "join flow f on f.id = e.flow_id "
        f"where e.id = '{execution_id}';"
    )
    command = ["kubectl", "exec", "-n", namespace, pod]
    if container:
        command.extend(["-c", container])
    command.extend(
        [
            "--",
            "psql",
            "-U",
            db_user,
            "-d",
            db_name,
            "-t",
            "-A",
            "-F",
            "\t",
            "-c",
            sql,
        ]
    )
    completed = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
    )
    line = next(
        (
            candidate.strip()
            for candidate in completed.stdout.splitlines()
            if candidate.strip()
        ),
        None,
    )
    if not line:
        raise click.ClickException(
            f"Execution {execution_id} was not found in {namespace}/{pod}."
        )
    execution_id_text, flow_id, flow_name, trigger_event_details = line.split("\t", 3)
    return SourceExecution(
        execution_id=execution_id_text,
        flow_id=flow_id,
        flow_name=flow_name or None,
        trigger_event_data=json.loads(trigger_event_details or "{}"),
    )


def _load_source_execution(
    *,
    execution_id: str,
    source_database_url: Optional[str],
    source_trigger_json: Optional[Path],
    source_k8s_namespace: Optional[str],
    source_k8s_pod: Optional[str],
    source_k8s_container: Optional[str],
    source_db_name: str,
    source_db_user: str,
) -> SourceExecution:
    if source_trigger_json:
        payload = json.loads(source_trigger_json.read_text(encoding="utf-8"))
        return SourceExecution(
            execution_id=execution_id,
            flow_id=str(payload.get("flow_id", "")),
            flow_name=payload.get("flow_name"),
            trigger_event_data=payload.get("trigger_event_data") or payload,
        )
    if source_database_url:
        return _query_execution_from_database(source_database_url, execution_id)
    if source_k8s_namespace and source_k8s_pod:
        return _query_execution_from_kubectl_psql(
            namespace=source_k8s_namespace,
            pod=source_k8s_pod,
            execution_id=execution_id,
            db_name=source_db_name,
            db_user=source_db_user,
            container=source_k8s_container,
        )

    local_db_url = os.getenv("DATABASE_URL")
    if not local_db_url:
        raise click.ClickException(
            "DATABASE_URL is not set and no source execution input was provided."
        )
    return _query_execution_from_database(local_db_url, execution_id)


def _prepare_replay_trigger_data(
    source_execution: SourceExecution,
    *,
    target_flow_account_id: Any,
    preserve_source_account_id: bool,
    test_mode: bool,
) -> dict[str, Any]:
    trigger_event_data = json.loads(
        json.dumps(source_execution.trigger_event_data or {})
    )
    trigger_event_data.pop("test_mode", None)
    trigger_event_data["replay_source_execution_id"] = source_execution.execution_id
    trigger_event_data["replay_source_flow_id"] = source_execution.flow_id
    if not preserve_source_account_id:
        trigger_event_data["account_id"] = str(target_flow_account_id)
    trigger_event_data["test_mode"] = test_mode
    return trigger_event_data


def _print_recent_diagnostics(session_factory, execution_id: str, tail: int) -> None:
    session = session_factory()
    try:
        execution = crud_flow_execution.get(session, id=execution_id)
        if not execution:
            click.echo("No execution row found for diagnostics.")
            return

        click.echo("\nExecution summary")
        click.echo(f"  status: {execution.status}")
        click.echo(f"  error_message: {execution.error_message or '-'}")
        click.echo(f"  tool_calls_count: {execution.tool_calls_count or 0}")
        click.echo(f"  total_tokens: {execution.total_tokens or 0}")
        click.echo(f"  estimated_cost: {execution.estimated_cost or 0}")

        activities = (
            session.query(RuntimeSessionActivity)
            .filter(RuntimeSessionActivity.flow_execution_id == execution.id)
            .order_by(RuntimeSessionActivity.timestamp.desc())
            .limit(tail)
            .all()
        )
        if activities:
            click.echo("\nRecent runtime activity")
            for activity in reversed(activities):
                metadata = activity.metadata_ or {}
                arguments = metadata.get("arguments")
                click.echo(
                    f"  - {activity.timestamp.isoformat()} {activity.server_name}/{activity.tool_name} "
                    f"[{activity.status}] args={json.dumps(arguments, sort_keys=True, default=str) if arguments else '-'}"
                )

        gateway_events = (
            session.query(FlowExecutionLog)
            .filter(
                FlowExecutionLog.execution_id == execution.id,
                FlowExecutionLog.log_type == "model_gateway_call",
            )
            .order_by(FlowExecutionLog.timestamp.desc())
            .limit(tail)
            .all()
        )
        if gateway_events:
            click.echo("\nRecent gateway events")
            for row in reversed(gateway_events):
                payload = row.metadata_ or {}
                click.echo(
                    f"  - {row.timestamp.isoformat()} status={payload.get('status_code')} "
                    f"tokens={payload.get('total_tokens')} model={payload.get('requested_model')} "
                    f"finish_reason={payload.get('finish_reason')} error={payload.get('error_detail') or '-'}"
                )
    finally:
        session.close()


async def _wait_for_terminal_execution(
    session_factory,
    execution_id: str,
    *,
    timeout_seconds: int,
    poll_interval_seconds: float,
    diagnostics_tail: int,
) -> int:
    terminal_statuses = {"SUCCEEDED", "FAILED", "STOPPED", "CANCELLED", "TIMEOUT"}
    waited = 0.0
    last_status: Optional[str] = None
    while waited <= timeout_seconds:
        session = session_factory()
        try:
            execution: FlowExecution | None = crud_flow_execution.get(
                session, id=execution_id
            )
            if execution is None:
                raise click.ClickException(
                    f"Execution {execution_id} disappeared from the local database."
                )
            if execution.status != last_status:
                click.echo(
                    f"[{int(waited):>4}s] status={execution.status} "
                    f"tool_calls={execution.tool_calls_count or 0} "
                    f"tokens={execution.total_tokens or 0}"
                )
                last_status = execution.status
            if execution.status in terminal_statuses:
                _print_recent_diagnostics(
                    session_factory, execution_id, diagnostics_tail
                )
                return 0 if execution.status == "SUCCEEDED" else 1
        finally:
            session.close()

        await asyncio.sleep(poll_interval_seconds)
        waited += poll_interval_seconds

    click.echo(
        f"Timed out waiting for execution {execution_id} after {timeout_seconds} seconds."
    )
    _print_recent_diagnostics(session_factory, execution_id, diagnostics_tail)
    return 1


@click.command()
@click.option("--execution-id", required=True, help="Execution ID to replay.")
@click.option(
    "--target-flow-id",
    help="Local flow ID to run. Defaults to the source execution's flow ID.",
)
@click.option(
    "--source-database-url",
    help="Optional source database URL for fetching the original execution.",
)
@click.option(
    "--source-trigger-json",
    type=click.Path(exists=True, path_type=Path),
    help="Replay directly from a previously exported trigger JSON file.",
)
@click.option(
    "--source-k8s-namespace",
    help="Kubernetes namespace containing the source Postgres pod.",
)
@click.option(
    "--source-k8s-pod",
    help="Kubernetes Postgres pod name used to fetch the original execution.",
)
@click.option(
    "--source-k8s-container",
    help="Optional container name for kubectl exec when the pod has multiple containers.",
)
@click.option("--source-db-name", default="preloop", show_default=True)
@click.option("--source-db-user", default="postgres", show_default=True)
@click.option(
    "--dump-trigger-json",
    type=click.Path(path_type=Path),
    help="Optional path to write the normalized replay trigger JSON.",
)
@click.option(
    "--execution-timeout-seconds",
    default=600,
    show_default=True,
    help="Local execution timeout ceiling for the orchestrator.",
)
@click.option(
    "--wait-timeout-seconds",
    default=720,
    show_default=True,
    help="How long this script waits for the replayed execution to finish.",
)
@click.option(
    "--poll-interval-seconds",
    default=2.0,
    show_default=True,
    help="Polling interval while waiting for the replayed execution.",
)
@click.option(
    "--diagnostics-tail",
    default=8,
    show_default=True,
    help="How many recent runtime activities and gateway events to print at the end.",
)
@click.option(
    "--test-mode/--no-test-mode",
    default=False,
    show_default=True,
    help="Whether to replay as a test execution.",
)
@click.option(
    "--preserve-source-account-id/--rewrite-account-id",
    default=False,
    show_default=True,
    help="Keep the source account_id instead of rewriting it to the local target flow account.",
)
def main(
    execution_id: str,
    target_flow_id: Optional[str],
    source_database_url: Optional[str],
    source_trigger_json: Optional[Path],
    source_k8s_namespace: Optional[str],
    source_k8s_pod: Optional[str],
    source_k8s_container: Optional[str],
    source_db_name: str,
    source_db_user: str,
    dump_trigger_json: Optional[Path],
    execution_timeout_seconds: int,
    wait_timeout_seconds: int,
    poll_interval_seconds: float,
    diagnostics_tail: int,
    test_mode: bool,
    preserve_source_account_id: bool,
) -> None:
    """Replay one stored flow execution locally."""

    load_dotenv()
    source_execution = _load_source_execution(
        execution_id=execution_id,
        source_database_url=source_database_url,
        source_trigger_json=source_trigger_json,
        source_k8s_namespace=source_k8s_namespace,
        source_k8s_pod=source_k8s_pod,
        source_k8s_container=source_k8s_container,
        source_db_name=source_db_name,
        source_db_user=source_db_user,
    )

    db_gen = get_db_session()
    db = next(db_gen)
    session_factory = get_session_factory()
    try:
        resolved_target_flow_id = target_flow_id or source_execution.flow_id
        if not resolved_target_flow_id:
            raise click.ClickException(
                "Could not infer a target flow ID. Pass --target-flow-id explicitly."
            )
        target_flow = crud_flow.get(db, id=resolved_target_flow_id)
        if not target_flow:
            raise click.ClickException(
                f"Target flow {resolved_target_flow_id} was not found in the local database."
            )

        settings.flow_execution_max_wait_seconds = max(30, execution_timeout_seconds)
        replay_trigger_data = _prepare_replay_trigger_data(
            source_execution,
            target_flow_account_id=target_flow.account_id,
            preserve_source_account_id=preserve_source_account_id,
            test_mode=test_mode,
        )
        if dump_trigger_json:
            _dump_json(dump_trigger_json, replay_trigger_data)
            click.echo(f"Wrote replay trigger payload to {dump_trigger_json}")

        click.echo(
            f"Replaying source execution {source_execution.execution_id} "
            f"({source_execution.flow_name or source_execution.flow_id}) "
            f"into local flow {target_flow.name} ({target_flow.id})"
        )

        async def _run() -> int:
            trigger_service = FlowTriggerService(db)
            result = await trigger_service.trigger_flow(
                flow_id=uuid.UUID(str(target_flow.id)),
                test_mode=test_mode,
                trigger_event_data=replay_trigger_data,
            )
            replay_execution_id = result["id"]
            click.echo(f"Started local replay execution {replay_execution_id}")
            return await _wait_for_terminal_execution(
                session_factory,
                replay_execution_id,
                timeout_seconds=wait_timeout_seconds,
                poll_interval_seconds=poll_interval_seconds,
                diagnostics_tail=diagnostics_tail,
            )

        raise SystemExit(asyncio.run(_run()))
    finally:
        try:
            next(db_gen)
        except StopIteration:
            pass


if __name__ == "__main__":
    main()
