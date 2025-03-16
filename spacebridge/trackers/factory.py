"""Factory for creating tracker clients."""

import logging
from typing import Any, Dict, Optional

from spacebridge.trackers.base import TrackerInterface
from spacebridge.trackers.github import GitHubClient
from spacebridge.trackers.github.client import GitHubCredentials
from spacebridge.trackers.gitlab import GitLabClient
from spacebridge.trackers.gitlab.client import GitLabCredentials

logger = logging.getLogger(__name__)


class TrackerFactory:
    """Factory for creating tracker clients."""

    @staticmethod
    async def create_client(
        tracker_type: str, config: Dict[str, Any]
    ) -> Optional[TrackerInterface]:
        """Create a tracker client.

        Args:
            tracker_type: Type of tracker ("github", "jira", "gitlab").
            config: Configuration for the tracker.

        Returns:
            A tracker client or None if the tracker type is not supported.
        """
        try:
            if tracker_type == "github":
                if "credentials" not in config or "token" not in config["credentials"]:
                    raise ValueError(
                        "GitHub configuration must include credentials.token"
                    )

                if "owner" not in config or "repo" not in config:
                    raise ValueError("GitHub configuration must include owner and repo")

                credentials = GitHubCredentials(
                    token=config["credentials"]["token"],
                    username=config["credentials"].get("username"),
                )

                return GitHubClient(
                    credentials=credentials,
                    owner=config["owner"],
                    repo=config["repo"],
                    timeout=config.get("timeout", 10),
                )

            elif tracker_type == "gitlab":
                if "credentials" not in config or "token" not in config["credentials"]:
                    raise ValueError(
                        "GitLab configuration must include credentials.token"
                    )

                if "project_id" not in config:
                    raise ValueError("GitLab configuration must include project_id")

                credentials = GitLabCredentials(
                    token=config["credentials"]["token"],
                    username=config["credentials"].get("username"),
                )

                return GitLabClient(
                    credentials=credentials,
                    project_id=config["project_id"],
                    timeout=config.get("timeout", 10),
                )

            elif tracker_type == "jira":
                if "credentials" not in config or "token" not in config["credentials"]:
                    raise ValueError(
                        "Jira configuration must include credentials.token"
                    )

                if (
                    "credentials" not in config
                    or "username" not in config["credentials"]
                ):
                    raise ValueError(
                        "Jira configuration must include credentials.username"
                    )

                if "credentials" not in config or "url" not in config["credentials"]:
                    raise ValueError("Jira configuration must include credentials.url")

                from spacebridge.trackers.jira.client import JiraClient, JiraCredentials

                credentials = JiraCredentials(
                    token=config["credentials"]["token"],
                    username=config["credentials"]["username"],
                    url=config["credentials"]["url"],
                )

                return JiraClient(
                    credentials=credentials,
                    timeout=config.get("timeout", 10),
                )

            else:
                logger.warning(f"Unsupported tracker type: {tracker_type}")
                return None

        except Exception as e:
            logger.exception(f"Failed to create tracker client: {e}")
            return None
