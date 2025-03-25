"""Tests for organization ownership model."""

from sqlalchemy.orm import Session

from spacemodels.models import Account, AccountOrganization, Organization, Tracker


def test_organization_ownership(db_session: Session):
    """Test that an organization is owned by a single account through a tracker."""
    # Create owner account
    owner = Account(
        username="owner_user",
        email="owner@example.com",
        hashed_password="hashed_password",
        is_active=True,
    )
    db_session.add(owner)
    db_session.commit()

    # Create a tracker owned by the owner account
    tracker = Tracker(
        name="GitHub Tracker",
        tracker_type="github",
        api_key="test_api_key",
        account_id=owner.id,
    )
    db_session.add(tracker)
    db_session.commit()

    # Create an organization linked to the tracker
    org = Organization(
        name="Test Organization",
        identifier="test-org",
        tracker_id=tracker.id,
    )
    db_session.add(org)
    db_session.commit()

    # Create member account
    member = Account(
        username="member_user",
        email="member@example.com",
        hashed_password="hashed_password",
        is_active=True,
    )
    db_session.add(member)
    db_session.commit()

    # Add member to organization
    membership = AccountOrganization(
        account_id=member.id,
        organization_id=org.id,
        role="developer",
    )
    db_session.add(membership)
    db_session.commit()

    # Verify ownership
    assert org.owner.id == owner.id
    assert org.owner.username == "owner_user"

    # Verify owner's organizations
    assert len(owner.owned_organizations) == 1
    assert owner.owned_organizations[0].id == org.id
    assert owner.owned_organizations[0].name == "Test Organization"

    # Verify membership
    assert len(org.members) == 1
    assert org.members[0].account_id == member.id
    assert org.members[0].role == "developer"

    # Verify member's organizations
    assert len(member.organization_memberships) == 1
    assert member.organization_memberships[0].organization_id == org.id
    assert member.organization_memberships[0].role == "developer"

    # Owner is not in the members list (only explicit memberships)
    owner_memberships = (
        db_session.query(AccountOrganization).filter_by(account_id=owner.id).all()
    )
    assert len(owner_memberships) == 0


def test_multiple_organizations_same_owner(db_session: Session):
    """Test that multiple organizations can be owned by the same account through a tracker."""
    # Create owner account
    owner = Account(
        username="multi_owner",
        email="multi_owner@example.com",
        hashed_password="hashed_password",
        is_active=True,
    )
    db_session.add(owner)
    db_session.commit()

    # Create a tracker owned by the owner account
    tracker = Tracker(
        name="GitHub Tracker",
        tracker_type="github",
        api_key="test_api_key",
        account_id=owner.id,
    )
    db_session.add(tracker)
    db_session.commit()

    # Create multiple organizations linked to the same tracker
    org1 = Organization(
        name="Organization 1",
        identifier="org-1",
        tracker_id=tracker.id,
    )
    org2 = Organization(
        name="Organization 2",
        identifier="org-2",
        tracker_id=tracker.id,
    )
    db_session.add_all([org1, org2])
    db_session.commit()

    # Verify ownership
    assert org1.owner.id == owner.id
    assert org2.owner.id == owner.id

    # Verify owner's organizations
    owned_orgs = owner.owned_organizations
    assert len(owned_orgs) == 2
    org_names = [org.name for org in owned_orgs]
    assert "Organization 1" in org_names
    assert "Organization 2" in org_names
