"""Resolver for account-related placeholders."""

import logging
from typing import Optional

from spacemodels.crud import crud_account

from .base import PromptResolver, ResolverContext

logger = logging.getLogger(__name__)


class AccountResolver(PromptResolver):
    """
    Resolver for account data from the database.

    Handles placeholders like:
    - {{account.email}}
    - {{account.name}}
    - {{account.id}}
    """

    @property
    def prefix(self) -> str:
        """Return the prefix this resolver handles."""
        return "account"

    async def resolve(self, path: str, context: ResolverContext) -> Optional[str]:
        """
        Resolve account placeholders.

        Args:
            path: Path after the prefix (e.g., "email", "name")
            context: Resolver context

        Returns:
            Resolved value or None
        """
        # Try to get account ID from trigger event
        account_id = context.trigger_event_data.get("account_id")

        if not account_id:
            self.logger.warning("No account_id in trigger event data")
            return None

        # Query account from database using CRUD layer
        account = crud_account.get(context.db, id=account_id)

        if not account:
            self.logger.warning(f"Could not find account with id={account_id}")
            return None

        # Resolve the requested field
        if path == "email":
            return account.email
        elif path == "name":
            return account.name or ""
        elif path == "id":
            return str(account.id)
        else:
            self.logger.warning(f"Unknown account field: {path}")
            return None
