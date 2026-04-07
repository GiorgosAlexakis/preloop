from preloop.models.db.session import get_db_session
from preloop.models.models.account import Account
from preloop.services.subject_governance import is_tool_enabled_for_subject


def main():
    db = next(get_db_session())
    # Find the account that owns this agent
    from preloop.models.models.managed_agent import ManagedAgent

    agent = (
        db.query(ManagedAgent)
        .filter(ManagedAgent.id == "d9f20a6d-241e-41d3-a226-5593ff82e9f2")
        .first()
    )
    if not agent:
        print("Agent not found!")
        return

    print(f"Agent account_id: {agent.account_id}")
    account = db.query(Account).filter(Account.id == agent.account_id).first()

    meta_data = account.meta_data if account else {}
    print(f"Meta data: {meta_data.get('subject_governance', {})}")

    subject_context = {"managed_agent_id": str(agent.id)}

    # Check for a tool we expect to be disabled
    enabled = is_tool_enabled_for_subject(
        meta_data, tool_name="rollback_deployment", subject_context=subject_context
    )
    print(f"rollback_deployment enabled: {enabled}")


main()
