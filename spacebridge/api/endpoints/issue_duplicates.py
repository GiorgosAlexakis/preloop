from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Any, List, Dict
import logging
import openai
import os

from spacebridge.schemas.issue_duplicate import (
    IssueDuplicate as IssueDuplicateSchema,
    IssueDuplicateCreate,
)
from SpaceModels.spacemodels.crud.issue_duplicate import crud_issue_duplicate
from spacemodels.crud import crud_issue, crud_llm_provider
from spacemodels.db.session import get_db_session as get_db

logger = logging.getLogger(__name__)

router = APIRouter()

DEFAULT_DUPLICATE_ANALYSIS_LLM_NAME = "gpt-4o"
LLM_DUPLICATE_SYSTEM_PROMPT = "You are an expert issue tracker assistant. Your task is to determine if two issues are duplicates of each other."
LLM_DUPLICATE_USER_PROMPT_TEMPLATE = """
Use your expert judgement to determine if the following two issues are duplicates.

- Two issues are considered duplicates if they describe the same core problem, request, or task, even if the wording differs slightly or one contains minor additional details.
- Two issues are not considered duplicates even if they look almost identical, if they refer to different components.

Issue 1:
Title: {issue1_title}
Description:
---
{issue1_description}
---

Issue 2:
Title: {issue2_title}
Description:
---
{issue2_description}
---

Based on the information above, is Issue 2 a duplicate of Issue 1?

Respond with ONLY one of the following words:
DUPLICATE
NOT_DUPLICATE
"""


@router.get(
    "/issue-duplicates/check",
    response_model=IssueDuplicateSchema,
    tags=["Issue Duplicates"],
)
def check_or_create_issue_duplicate(
    *,
    db: Session = Depends(get_db),
    issue1_id: str,
    issue2_id: str,
) -> Any:
    if issue1_id == issue2_id:
        raise HTTPException(status_code=400, detail="Issue IDs cannot be the same.")

    existing_duplicate = crud_issue_duplicate.get_by_issue_ids(
        db, issue1_id=issue1_id, issue2_id=issue2_id
    )
    if existing_duplicate:
        logger.info(
            f"Found existing duplicate entry for issues {issue1_id} and {issue2_id}."
        )
        return existing_duplicate

    logger.info(
        f"No existing duplicate entry for issues {issue1_id} and {issue2_id}. Proceeding with LLM analysis."
    )

    issue1 = crud_issue.get(db, id=issue1_id)
    issue2 = crud_issue.get(db, id=issue2_id)

    if not issue1 or not issue2:
        missing_ids_str = []
        if not issue1:
            missing_ids_str.append(str(issue1_id))
        if not issue2:
            missing_ids_str.append(str(issue2_id))
        detail = f"Issue(s) not found: {', '.join(missing_ids_str)}."
        logger.warning(detail)
        raise HTTPException(status_code=404, detail=detail)

    default_provider = crud_llm_provider.get_default_active_provider(db)
    if not default_provider:
        logger.error("No default active LLM provider configured.")
        raise HTTPException(
            status_code=500, detail="No default active LLM provider configured."
        )

    logger.info(
        f"Using LLM model '{DEFAULT_DUPLICATE_ANALYSIS_LLM_NAME}' from provider '{default_provider.provider_name}'."
    )

    prompt_text = LLM_DUPLICATE_USER_PROMPT_TEMPLATE.format(
        issue1_id=issue1.id,
        issue1_title=issue1.title or "N/A",
        issue1_description=issue1.description or "No description provided.",
        issue2_id=issue2.id,
        issue2_title=issue2.title or "N/A",
        issue2_description=issue2.description or "No description provided.",
    )

    messages: List[Dict[str, str]] = [
        {"role": "system", "content": LLM_DUPLICATE_SYSTEM_PROMPT},
        {"role": "user", "content": prompt_text},
    ]

    llm_response_text = ""
    try:
        api_key = (
            default_provider.credentials.get("api_key")
            if default_provider.credentials
            else None
        )
        if not api_key:
            logger.warning(
                f"API key not found in credentials for provider {default_provider.name}. Trying OPENAI_API_KEY env var."
            )
            api_key = os.getenv("OPENAI_API_KEY")

        if not api_key:
            logger.error(
                f"OpenAI API key not found for provider {default_provider.name} or environment variable."
            )
            raise HTTPException(
                status_code=500, detail="OpenAI API key not configured."
            )

        client = openai.OpenAI(api_key=api_key)

        response = client.chat.completions.create(
            model=DEFAULT_DUPLICATE_ANALYSIS_LLM_NAME,
            messages=messages,
            temperature=0.2,
            max_tokens=50,
        )
        llm_response_text = response.choices[0].message.content.strip()
        logger.info(
            f"LLM response for issues {issue1_id}, {issue2_id}: '{llm_response_text}'"
        )

    except openai.APIError as e:
        logger.exception(
            f"OpenAI API call for model '{DEFAULT_DUPLICATE_ANALYSIS_LLM_NAME}' failed: {e}"
        )
        raise HTTPException(status_code=503, detail=f"LLM invocation failed: {str(e)}")
    except Exception as e:
        logger.exception(
            f"An unexpected error occurred during LLM invocation for model '{DEFAULT_DUPLICATE_ANALYSIS_LLM_NAME}': {e}"
        )
        raise HTTPException(status_code=500, detail=f"LLM processing error: {str(e)}")

    llm_decision = llm_response_text.upper()
    if llm_decision == "DUPLICATE":
        parsed_status = "confirmed"
    elif llm_decision == "NOT_DUPLICATE":
        parsed_status = "rejected"
    else:
        logger.warning(
            f"LLM returned unexpected status: '{llm_response_text}'. Defaulting to 'undecided'."
        )
        parsed_status = "undecided"

    duplicate_create_data = IssueDuplicateCreate(
        issue1_id=issue1.id,
        issue2_id=issue2.id,
        decision=parsed_status,
        llm_provider_id=default_provider.id,
        llm_model_name=DEFAULT_DUPLICATE_ANALYSIS_LLM_NAME,
    )

    new_duplicate_entry = crud_issue_duplicate.create(
        db, obj_in=duplicate_create_data.model_dump()
    )
    logger.info(
        f"Created new IssueDuplicate entry ID {new_duplicate_entry.id} for issues {issue1_id}, {issue2_id} with status '{parsed_status}'."
    )
    return new_duplicate_entry
