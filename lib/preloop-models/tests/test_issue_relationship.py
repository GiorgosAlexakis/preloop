"""Tests for issue relationship functionality."""

import pytest
from sqlalchemy.exc import IntegrityError

from spacemodels.crud import crud_issue, crud_issue_relationship


def test_create_relationship_blocks(db_session, create_issue):
    """Test creating a 'blocks' relationship between two issues."""
    issue1 = create_issue(title="Blocker Issue")
    issue2 = create_issue(title="Blocked Issue")

    relationship = crud_issue_relationship.create(
        db_session,
        source_issue_id=issue1.id,
        target_issue_id=issue2.id,
        type="blocks",
    )

    assert relationship.source_issue_id == issue1.id
    assert relationship.target_issue_id == issue2.id
    assert relationship.type == "blocks"


def test_create_relationship_related(db_session, create_issue):
    """Test creating a 'related' relationship, ensuring ID order is handled."""
    issue1 = create_issue(title="First Issue")
    issue2 = create_issue(title="Second Issue")

    # Ensure the smaller ID is always the source for 'related' type
    id1, id2 = sorted([issue1.id, issue2.id])

    relationship = crud_issue_relationship.create(
        db_session,
        source_issue_id=issue2.id,  # Use larger ID as source
        target_issue_id=issue1.id,  # Use smaller ID as target
        type="related",
    )

    assert relationship.source_issue_id == id1
    assert relationship.target_issue_id == id2
    assert relationship.type == "related"


def test_get_for_issue(db_session, create_issue):
    """Test retrieving all relationships for a specific issue."""
    issue1 = create_issue(title="Central Issue")
    issue2 = create_issue(title="Blocked by Central")
    issue3 = create_issue(title="Related to Central")

    # Create relationships
    crud_issue_relationship.create(
        db_session, source_issue_id=issue1.id, target_issue_id=issue2.id, type="blocks"
    )
    crud_issue_relationship.create(
        db_session, source_issue_id=issue1.id, target_issue_id=issue3.id, type="related"
    )

    relationships = crud_issue_relationship.get_for_issue(
        db_session, issue_id=issue1.id
    )
    assert len(relationships) == 2


def test_remove_relationship(db_session, create_issue):
    """Test removing an issue relationship."""
    issue1 = create_issue()
    issue2 = create_issue()

    crud_issue_relationship.create(
        db_session, source_issue_id=issue1.id, target_issue_id=issue2.id, type="blocks"
    )

    # Verify it exists
    assert (
        len(crud_issue_relationship.get_for_issue(db_session, issue_id=issue1.id)) == 1
    )

    # Remove it
    crud_issue_relationship.remove(
        db_session, source_issue_id=issue1.id, target_issue_id=issue2.id, type="blocks"
    )

    # Verify it's gone
    assert (
        len(crud_issue_relationship.get_for_issue(db_session, issue_id=issue1.id)) == 0
    )


def test_prevent_duplicate_related_relationship(db_session, create_issue):
    """Test that creating a duplicate 'related' relationship raises an error."""
    issue1 = create_issue()
    issue2 = create_issue()

    # Create the first relationship
    crud_issue_relationship.create(
        db_session, source_issue_id=issue1.id, target_issue_id=issue2.id, type="related"
    )

    # Attempting to create the reverse should fail due to primary key constraint
    with pytest.raises(IntegrityError):
        crud_issue_relationship.create(
            db_session,
            source_issue_id=issue2.id,
            target_issue_id=issue1.id,
            type="related",
        )


def test_delete_issue_cascades_relationships(db_session, create_issue):
    """Test that deleting an issue cascades to its relationships."""
    issue1 = create_issue()
    issue2 = create_issue()

    crud_issue_relationship.create(
        db_session, source_issue_id=issue1.id, target_issue_id=issue2.id, type="blocks"
    )

    # Verify relationship exists
    assert (
        len(crud_issue_relationship.get_for_issue(db_session, issue_id=issue2.id)) == 1
    )

    # Delete the source issue
    crud_issue.delete(db_session, id=issue1.id)

    # Verify the relationship is also deleted
    assert (
        len(crud_issue_relationship.get_for_issue(db_session, issue_id=issue2.id)) == 0
    )
