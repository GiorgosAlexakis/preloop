"""Resolver for trigger event placeholders."""

import logging
from typing import Optional

from .base import PromptResolver, ResolverContext

logger = logging.getLogger(__name__)


class TriggerEventResolver(PromptResolver):
    """
    Resolver for trigger event data.

    Handles placeholders like:
    - {{trigger_event.payload.issue.title}}
    - {{trigger_event.payload.commit.sha}}
    - {{trigger_event.source}}
    """

    @property
    def prefix(self) -> str:
        """Return the prefix this resolver handles."""
        return "trigger_event"

    async def resolve(self, path: str, context: ResolverContext) -> Optional[str]:
        """
        Resolve trigger event placeholders.

        Args:
            path: Path after the prefix (e.g., "payload.issue.title")
                  If empty, returns the entire trigger event as JSON
            context: Resolver context

        Returns:
            Resolved value or None
        """
        if not context.trigger_event_data:
            self.logger.warning("No trigger event data available")
            return None

        # If no path specified, return entire event as JSON
        if not path or path.strip() == "":
            import json

            try:
                return json.dumps(context.trigger_event_data, indent=2)
            except Exception as e:
                self.logger.error(f"Failed to serialize trigger event data: {e}")
                return None

        # Handle direct event fields
        value = self._safe_get_nested(context.trigger_event_data, path)

        if value is None:
            self.logger.debug(f"Could not resolve trigger_event.{path} in event data")

        return value
