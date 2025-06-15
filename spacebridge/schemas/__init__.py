"""API schemas for request and response validation.

This module contains Pydantic models used for API request/response validation.
These are not database models - all database models are imported from SpaceModels.
"""

from spacebridge.schemas.auth import (
    LoginRequest,
    RefreshRequest,
    Token,
    TokenData,
    User,
    UserInDB,
)
from spacebridge.schemas.comment import (
    CommentBase,
    CommentCreate,
    CommentList,
    CommentResponse,
)
from spacebridge.schemas.issue import (
    IssueBase,
    IssueCreate,
    IssueResponse,
    IssueSearchResults,
    IssueUpdate,
)
from spacebridge.schemas.organization import (
    OrganizationBase,
    OrganizationCreate,
    OrganizationResponse,
    OrganizationUpdate,
)
from spacebridge.schemas.project import (
    ProjectBase,
    ProjectCreate,
    ProjectResponse,
    ProjectUpdate,
    TestConnectionRequest,
    TestConnectionResponse,
)
from spacebridge.schemas.duplicates import (
    DuplicateIssuePair,
    ProjectDuplicatesResponse,
)
from spacebridge.schemas.llm_provider import (
    LLMProviderBase,
    LLMProviderCreate,
    LLMProviderRead,
    LLMProviderUpdate,
)

__all__ = [
    # Auth schemas
    "LoginRequest",
    "RefreshRequest",
    "Token",
    "TokenData",
    "User",
    "UserInDB",
    # Comment schemas
    "CommentBase",
    "CommentCreate",
    "CommentList",
    "CommentResponse",
    # Issue schemas
    "IssueBase",
    "IssueCreate",
    "IssueResponse",
    "IssueSearchResults",
    "IssueUpdate",
    # Organization schemas
    "OrganizationBase",
    "OrganizationCreate",
    "OrganizationResponse",
    "OrganizationUpdate",
    # Project schemas
    "ProjectBase",
    "ProjectCreate",
    "ProjectResponse",
    "ProjectUpdate",
    "TestConnectionRequest",
    "TestConnectionResponse",
    # Duplicates schemas
    "DuplicateIssuePair",
    "ProjectDuplicatesResponse",
    # LLMProvider schemas
    "LLMProviderBase",
    "LLMProviderCreate",
    "LLMProviderRead",
    "LLMProviderUpdate",
]
