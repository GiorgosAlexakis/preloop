import asyncio
from dotenv import load_dotenv
from preloop_models.db.session import get_db_session
from preloop_models.crud.flow import CRUDFlow
from preloop_models.schemas.flow import FlowCreate


async def seed_presets():
    """
    Seeds the database with a few example flow presets.
    """
    session_generator = get_db_session()
    session = next(session_generator)
    try:
        crud_flow = CRUDFlow()
        presets = [
            {
                "name": "Auto-Update Docs/Tests",
                "description": "Evaluates pull requests to see if they properly update docs/tests, and if not, opens a new pull request with suggested doc/test updates.",
                "icon": "file-earmark-text",
                "is_preset": True,
                "trigger_event_source": "github",
                "trigger_event_type": "pull_request_opened",
                "prompt_template": "The following pull request was opened: {{pr_title}}. Please review the changes and determine if the documentation and tests have been updated appropriately. If not, please create a new pull request with the necessary updates.",
                "openhands_agent_config": {
                    "agent_type": "CodeActAgent",
                    "max_iterations": 10,
                },
            },
            {
                "name": "Triage New Issues",
                "description": "Automatically labels and assigns new issues based on their content.",
                "icon": "tag",
                "is_preset": True,
                "trigger_event_source": "github",
                "trigger_event_type": "issue_opened",
                "prompt_template": "A new issue has been opened: {{issue_title}}. Please analyze the issue and add the appropriate labels and assign it to the correct team member.",
                "openhands_agent_config": {
                    "agent_type": "CodeActAgent",
                    "max_iterations": 5,
                },
            },
        ]

        for preset_data in presets:
            flow_in = FlowCreate(**preset_data)
            crud_flow.create(session, flow_in=flow_in)
            print(f"Created preset: {preset_data['name']}")
    finally:
        session.close()


if __name__ == "__main__":
    load_dotenv()
    asyncio.run(seed_presets())
