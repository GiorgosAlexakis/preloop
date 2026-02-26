"""Check if approval is configured for a tool."""

import asyncio
import os

from sqlalchemy import select
from preloop.models.db.session import get_async_db_session
from preloop.models.models import ApprovalWorkflow, ToolConfiguration


async def check_approval_config(tool_name: str = "estimate_compliance"):
    """Check approval configuration for a tool."""
    print(f"\n{'=' * 80}")
    print(f"Checking approval configuration for: {tool_name}")
    print(f"{'=' * 80}\n")

    async with get_async_db_session() as db:
        # Get all tool configurations
        result = await db.execute(
            select(ToolConfiguration).where(
                ToolConfiguration.tool_name == tool_name,
            )
        )
        configs = result.scalars().all()

        if not configs:
            print(f"❌ No ToolConfiguration found for '{tool_name}'")
            print("\nTo configure approval:")
            print("  1. Go to Preloop UI: /console/tools")
            print(f"  2. Find '{tool_name}' tool")
            print("  3. Enable 'Requires Approval'")
            print("  4. Select or create an approval workflow")
            return

        for config in configs:
            print(f"Account ID: {config.account_id}")
            print(f"Tool Name: {config.tool_name}")
            print(f"Tool Source: {config.tool_source}")
            print(f"Requires Approval: {bool(config.approval_workflow_id)}")
            print(f"Approval Workflow ID: {config.approval_workflow_id}")

            if config.approval_workflow_id:
                # Get the approval workflow
                policy_result = await db.execute(
                    select(ApprovalWorkflow).where(
                        ApprovalWorkflow.id == config.approval_workflow_id
                    )
                )
                policy = policy_result.scalar_one_or_none()

                if policy:
                    print("\n✅ Approval Workflow Configuration:")
                    print(f"   - Type: {policy.approval_type}")
                    print(f"   - User: {policy.user or 'N/A'}")
                    print(f"   - Channel: {policy.channel or 'N/A'}")
                    print(f"   - Webhook URL: {policy.webhook_url or 'N/A'}")
                    print(f"   - Timeout: {policy.timeout_seconds or 300}s")
                else:
                    print(
                        f"\n❌ Approval workflow {config.approval_workflow_id} not found!"
                    )
            else:
                print(
                    "\n❌ Approval not required for this tool (no approval_workflow_id)"
                )

            print(f"\n{'-' * 80}\n")


if __name__ == "__main__":
    # Set database URL if needed
    if not os.getenv("DATABASE_URL"):
        print("⚠️  DATABASE_URL not set, using default")
        os.environ["DATABASE_URL"] = (
            "postgresql+psycopg://postgres:postgres@localhost/preloop"
        )

    asyncio.run(check_approval_config())
