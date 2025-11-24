#!/usr/bin/env python3
"""Script to inspect running flow execution containers."""

import argparse
import asyncio
import json
import logging
import sys
from typing import List, Dict, Any

import aiodocker

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def list_flow_containers() -> List[Dict[str, Any]]:
    """
    List all Preloop AI flow execution containers.

    Returns:
        List of container information dicts
    """
    docker = aiodocker.Docker()

    try:
        # Get containers with preloop_ai labels
        # Docker API expects label filters as a list
        containers = await docker.containers.list(
            all=True, filters={"label": ["preloop_ai.agent_type"]}
        )

        container_info = []

        for container in containers:
            info = await container.show()
            labels = info["Config"]["Labels"]
            state = info["State"]

            container_data = {
                "id": container.id,
                "short_id": container.id[:12],
                "flow_id": labels.get("preloop_ai.flow_id"),
                "execution_id": labels.get("preloop_ai.execution_id"),
                "agent_type": labels.get("preloop_ai.agent_type"),
                "status": state["Status"],
                "running": state["Running"],
                "exit_code": state.get("ExitCode"),
                "started_at": state.get("StartedAt"),
                "finished_at": state.get("FinishedAt"),
            }

            container_info.append(container_data)

        return container_info

    finally:
        await docker.close()


async def get_container_logs(container_id: str, tail: int = 100) -> List[str]:
    """
    Get logs from a container.

    Args:
        container_id: Container ID
        tail: Number of recent lines to retrieve

    Returns:
        List of log lines
    """
    docker = aiodocker.Docker()

    try:
        container = await docker.containers.get(container_id)
        logs = await container.log(stdout=True, stderr=True, tail=tail)
        return [line.decode("utf-8", errors="replace") for line in logs]
    finally:
        await docker.close()


async def inspect_container(container_id: str) -> Dict[str, Any]:
    """
    Get detailed information about a container.

    Args:
        container_id: Container ID

    Returns:
        Container inspection data
    """
    docker = aiodocker.Docker()

    try:
        container = await docker.containers.get(container_id)
        return await container.show()
    finally:
        await docker.close()


def format_container_info(container: Dict[str, Any]) -> str:
    """Format container information for display."""
    lines = [
        f"Container ID: {container['short_id']}",
        f"Flow ID: {container['flow_id']}",
        f"Execution ID: {container['execution_id']}",
        f"Agent Type: {container['agent_type']}",
        f"Status: {container['status']}",
        f"Running: {container['running']}",
        f"Exit Code: {container['exit_code']}",
        f"Started At: {container['started_at']}",
        f"Finished At: {container['finished_at']}",
    ]
    return "\n".join(lines)


async def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Inspect Preloop AI flow execution containers"
    )
    parser.add_argument("--list", action="store_true", help="List all flow containers")
    parser.add_argument(
        "--logs", metavar="CONTAINER_ID", help="Get logs from a specific container"
    )
    parser.add_argument(
        "--tail", type=int, default=100, help="Number of log lines to retrieve"
    )
    parser.add_argument(
        "--inspect",
        metavar="CONTAINER_ID",
        help="Get detailed inspection of a container",
    )
    parser.add_argument("--json", action="store_true", help="Output in JSON format")

    args = parser.parse_args()

    if args.list:
        containers = await list_flow_containers()

        if args.json:
            print(json.dumps(containers, indent=2))
        else:
            if not containers:
                print("No Preloop AI flow containers found.")
            else:
                print(f"Found {len(containers)} flow containers:\n")
                for container in containers:
                    print(format_container_info(container))
                    print("-" * 80)

    elif args.logs:
        logs = await get_container_logs(args.logs, tail=args.tail)

        if args.json:
            print(json.dumps({"logs": logs}, indent=2))
        else:
            print(f"Logs from container {args.logs[:12]} (last {args.tail} lines):\n")
            for line in logs:
                print(line.rstrip())

    elif args.inspect:
        inspection = await inspect_container(args.inspect)

        if args.json:
            print(json.dumps(inspection, indent=2, default=str))
        else:
            print(f"Inspection of container {args.inspect[:12]}:\n")
            print(json.dumps(inspection, indent=2, default=str))

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
