"""Tests for IssueSet model and CRUD operations."""

import pytest
from sqlalchemy.orm import Session

from spacemodels.crud import crud_issue_set
from spacemodels.models import AIModel, Account, IssueSet


@pytest.fixture
def create_test_account(db_session: Session) -> Account:
    """Fixture to create a test account."""
    account = Account(username="test_user", email="test@example.com")
    db_session.add(account)
    db_session.commit()
    db_session.refresh(account)
    return account


@pytest.fixture
def create_test_ai_model(db_session: Session, create_test_account: Account) -> AIModel:
    """Fixture to create a test AI model."""
    ai_model = AIModel(
        name="Test AI Model",
        provider_name="test_provider",
        model_identifier="test_model_v1",
        account_id=create_test_account.id,
    )
    db_session.add(ai_model)
    db_session.commit()
    db_session.refresh(ai_model)
    return ai_model


def test_get_supersets_by_issues(
    db_session: Session, create_test_ai_model: AIModel, create_test_account: Account
):
    """Test retrieving issue sets that are supersets of a given issue list."""
    # Arrange: Create a superset and another unrelated set
    superset_issues = ["ID-1", "ID-2", "ID-3"]
    superset = IssueSet(
        name="Superset 1",
        issue_ids=superset_issues,
        ai_model_id=create_test_ai_model.id,
    )
    other_set = IssueSet(
        name="Other Set",
        issue_ids=["ID-4", "ID-5"],
        ai_model_id=create_test_ai_model.id,
    )
    db_session.add_all([superset, other_set])
    db_session.commit()

    # Act: Query for supersets of a subset
    query_issues = ["ID-1", "ID-2"]
    retrieved_sets = crud_issue_set.get_supersets_by_issues(
        db_session,
        issue_ids=query_issues,
        ai_model_id=create_test_ai_model.id,
        account_id=create_test_account.id,
    )

    # Assert: Only the superset should be returned
    assert len(retrieved_sets) == 1
    assert retrieved_sets[0].id == superset.id
    assert retrieved_sets[0].name == "Superset 1"

    # Act: Query for an exact match
    retrieved_exact_match = crud_issue_set.get_supersets_by_issues(
        db_session,
        issue_ids=superset_issues,
        ai_model_id=create_test_ai_model.id,
        account_id=create_test_account.id,
    )

    # Assert: The exact match should be returned
    assert len(retrieved_exact_match) == 1
    assert retrieved_exact_match[0].id == superset.id


def test_create_and_remove_subsets(
    db_session: Session, create_test_ai_model: AIModel, create_test_account: Account
):
    """Test creating a superset removes existing subsets."""
    # Arrange: Create an initial subset
    subset_issues = ["ID-10", "ID-11"]
    subset = IssueSet(
        name="Initial Subset",
        issue_ids=subset_issues,
        ai_model_id=create_test_ai_model.id,
    )
    db_session.add(subset)
    db_session.commit()

    # Confirm the subset exists
    assert db_session.query(IssueSet).filter_by(id=subset.id).first() is not None

    # Act: Create a new superset
    superset_issues = ["ID-10", "ID-11", "ID-12"]
    created_set = crud_issue_set.create_and_remove_subsets(
        db=db_session,
        name="New Superset",
        issue_ids=superset_issues,
        ai_model_id=create_test_ai_model.id,
        account_id=create_test_account.id,
    )

    # Assert: The new superset was created
    assert created_set.id is not None
    assert created_set.name == "New Superset"
    assert created_set.issue_ids == superset_issues

    # Assert: The original subset was deleted
    assert db_session.query(IssueSet).filter_by(id=subset.id).first() is None


def test_retrieval_of_exact_set(
    db_session: Session, create_test_ai_model: AIModel, create_test_account: Account
):
    """Test that get_supersets_by_issues retrieves an exact match."""
    # Arrange: Create an initial IssueSet
    issue_ids = ["ID-20", "ID-21"]
    initial_set = crud_issue_set.create_and_remove_subsets(
        db=db_session,
        name="Initial Set",
        issue_ids=issue_ids,
        ai_model_id=create_test_ai_model.id,
        account_id=create_test_account.id,
    )
    db_session.commit()

    # Act: Call get_supersets_by_issues with the exact same parameters
    retrieved_sets = crud_issue_set.get_supersets_by_issues(
        db=db_session,
        issue_ids=issue_ids,
        ai_model_id=create_test_ai_model.id,
        account_id=create_test_account.id,
    )

    # Assert: The existing set is retrieved
    assert len(retrieved_sets) == 1
    assert retrieved_sets[0].id == initial_set.id
