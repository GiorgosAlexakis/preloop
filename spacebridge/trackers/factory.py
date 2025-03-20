"""Factory for creating tracker clients."""

import logging
from typing import Any, Dict, Optional

from spacebridge.trackers.base import TrackerInterface
from spacebridge.trackers.github import GitHubClient
from spacebridge.trackers.github.client import GitHubCredentials
from spacebridge.trackers.gitlab import GitLabClient
from spacebridge.trackers.gitlab.client import GitLabCredentials
from spacebridge.trackers.jira.client import JiraClient, JiraCredentials

logger = logging.getLogger(__name__)


async def create_tracker_client(
    tracker_type: str,
    base_url: str,
    token: str,
    config: Dict[str, Any] = None,
) -> TrackerInterface:
    """Create a tracker client with simplified parameters.

    Args:
        tracker_type: Type of tracker ("github", "gitlab", "jira").
        base_url: Base URL for the tracker API.
        token: Authentication token.
        config: Additional configuration options.

    Returns:
        A tracker client interface.

    Raises:
        ValueError: If the tracker type is not supported.
    """
    config = config or {}
    tracker_type = tracker_type.lower()

    if tracker_type == "github":
        credentials = GitHubCredentials(
            token=token,
            username=config.get("username"),
        )

        # Extract owner and repo from base_url if not provided in config
        if "owner" not in config or "repo" not in config:
            # GitHub URL format: https://github.com/owner/repo
            parts = base_url.rstrip("/").split("/")
            if len(parts) >= 5:  # https:, "", github.com, owner, repo
                owner = parts[-2]
                repo = parts[-1]
                config["owner"] = owner
                config["repo"] = repo
            else:
                raise ValueError(
                    "Cannot extract owner/repo from GitHub URL. Please provide them in config."
                )

        return GitHubClient(
            credentials=credentials,
            owner=config["owner"],
            repo=config["repo"],
            timeout=config.get("timeout", 10),
        )

    elif tracker_type == "gitlab":
        credentials = GitLabCredentials(
            token=token,
            username=config.get("username"),
        )

        # Extract project_id from base_url if not provided in config
        if "project_id" not in config:
            # Try to extract project ID from URL or use project path
            # GitLab URL format: https://gitlab.com/namespace/project
            parts = base_url.rstrip("/").split("/")
            if len(parts) >= 5:  # https:, "", gitlab.com, namespace, project
                namespace = parts[-2]
                project_name = parts[-1]
                # Use namespace/project as project_id
                config["project_id"] = f"{namespace}/{project_name}"
                base_url = "/".join(parts[:-2])
            # else:
            #     raise ValueError("Cannot extract project_id from GitLab URL. Please provide it in config.")

        return GitLabClient(
            credentials=credentials,
            project_id=config.get("project_id"),  # Can be None for global access
            timeout=config.get("timeout", 10),
            base_url=base_url,
        )

    elif tracker_type == "jira":
        username = config.get("username", "")
        if not username:
            raise ValueError("Jira configuration must include username (in config)")

        credentials = JiraCredentials(
            token=token,
            username=username,
            url=base_url,
        )

        return JiraClient(
            credentials=credentials,
            timeout=config.get("timeout", 10),
        )

    else:
        raise ValueError(f"Unsupported tracker type: {tracker_type}")


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

                # project_id is optional - if not provided, will work globally at instance level

                credentials = GitLabCredentials(
                    token=config["credentials"]["token"],
                    username=config["credentials"].get("username"),
                )

                # Check if base_url is specified, and if so pass it through
                base_url = config.get("credentials", {}).get("url")
                return GitLabClient(
                    credentials=credentials,
                    project_id=config["project_id"],
                    timeout=config.get("timeout", 10),
                    base_url=base_url,
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
