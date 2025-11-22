"""Tests for IssueSet model and CRUD operations."""

import pytest
from sqlalchemy.orm import Session

from spacemodels.crud import crud_issue_set
from spacemodels.models import AIModel, Account, IssueSet


@pytest.fixture
def create_test_account(db_session: Session, create_account) -> Account:
    """Fixture to create a test account."""
    return create_account()


@pytest.fixture
def create_another_account(db_session: Session, create_account) -> Account:
    """Fixture to create another test account."""
    return create_account()


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


@pytest.fixture
def create_another_ai_model(
    db_session: Session, create_test_account: Account
) -> AIModel:
    """Fixture to create another test AI model for the same account."""
    ai_model = AIModel(
        name="Another AI Model",
        provider_name="test_provider",
        model_identifier="another_model_v1",
        account_id=create_test_account.id,
    )
    db_session.add(ai_model)
    db_session.commit()
    db_session.refresh(ai_model)
    return ai_model


def test_get_supersets_by_issues(
    db_session: Session,
    create_test_ai_model: AIModel,
    create_another_ai_model: AIModel,
    create_test_account: Account,
    create_another_account: Account,
):
    """Test retrieving issue sets that are supersets of a given issue list."""
    # Arrange: Create various issue sets
    superset_issues = ["ID-1", "ID-2", "ID-3"]

    # Set 1: Superset with the first AI model
    superset1 = IssueSet(
        name="Superset 1",
        issue_ids=superset_issues,
        ai_model_id=create_test_ai_model.id,
    )

    # Set 2: Superset with the second AI model
    superset2 = IssueSet(
        name="Superset 2",
        issue_ids=superset_issues,
        ai_model_id=create_another_ai_model.id,
    )

    # Set 3: Superset with no AI model (tracker-based)
    superset_no_model = IssueSet(
        name="Superset No Model", issue_ids=superset_issues, ai_model_id=None
    )

    # Set 4: Unrelated set
    other_set = IssueSet(
        name="Other Set",
        issue_ids=["ID-4", "ID-5"],
        ai_model_id=create_test_ai_model.id,
    )

    # Set 5: Set for another account
    other_account_model = AIModel(
        name="Other Account Model",
        provider_name="p",
        model_identifier="m",
        account_id=create_another_account.id,
    )
    db_session.add(other_account_model)
    db_session.commit()
    superset_other_account = IssueSet(
        name="Superset Other Account",
        issue_ids=superset_issues,
        ai_model_id=other_account_model.id,
    )

    db_session.add_all(
        [superset1, superset2, superset_no_model, other_set, superset_other_account]
    )
    db_session.commit()

    query_issues = ["ID-1", "ID-2"]

    # --- Test Cases ---

    # 1. Query for a single AI model
    retrieved_sets_1 = crud_issue_set.get_supersets_by_issues(
        db_session,
        issue_ids=query_issues,
        ai_model_ids=[create_test_ai_model.id],
        account_id=create_test_account.id,
    )
    assert len(retrieved_sets_1) == 1
    assert retrieved_sets_1[0].id == superset1.id

    # 2. Query for sets with no AI model
    retrieved_sets_none = crud_issue_set.get_supersets_by_issues(
        db_session,
        issue_ids=query_issues,
        ai_model_ids=[None],
        account_id=create_test_account.id,
    )
    assert len(retrieved_sets_none) == 1
    assert retrieved_sets_none[0].id == superset_no_model.id

    # 3. Query for multiple AI models
    retrieved_sets_multi = crud_issue_set.get_supersets_by_issues(
        db_session,
        issue_ids=query_issues,
        ai_model_ids=[create_test_ai_model.id, create_another_ai_model.id],
        account_id=create_test_account.id,
    )
    assert len(retrieved_sets_multi) == 2
    retrieved_ids = {s.id for s in retrieved_sets_multi}
    assert {superset1.id, superset2.id} == retrieved_ids

    # 4. Query for a model and None
    retrieved_sets_with_none = crud_issue_set.get_supersets_by_issues(
        db_session,
        issue_ids=query_issues,
        ai_model_ids=[create_test_ai_model.id, None],
        account_id=create_test_account.id,
    )
    assert len(retrieved_sets_with_none) == 2
    retrieved_ids_with_none = {s.id for s in retrieved_sets_with_none}
    assert {superset1.id, superset_no_model.id} == retrieved_ids_with_none

    # 5. Query for an exact match of all models
    retrieved_exact_match = crud_issue_set.get_supersets_by_issues(
        db_session,
        issue_ids=superset_issues,
        ai_model_ids=[
            create_test_ai_model.id,
            create_another_ai_model.id,
            None,
        ],
        account_id=create_test_account.id,
    )
    assert len(retrieved_exact_match) == 3


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
        ai_model_ids=[create_test_ai_model.id],
        account_id=create_test_account.id,
    )

    # Assert: The exact match should be retrieved
    assert len(retrieved_sets) == 1
    assert retrieved_sets[0].id == initial_set.id
