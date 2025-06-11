import pytest
from sqlalchemy.orm import Session
from uuid import uuid4

from spacemodels.models import Organization, Tracker
from spacemodels.schemas.flow import FlowCreate, FlowUpdate
from spacemodels.crud import crud_organization, crud_flow  # Import the CRUD instances
from spacemodels.schemas.organization import OrganizationCreate


# Removed local db_session override, will use global one from conftest.py


@pytest.fixture(scope="function")
def test_tracker(db_session: Session, create_account) -> Tracker:
    """Creates a tracker for use in tests, ensuring an account exists."""
    from spacemodels.crud import crud_tracker
    from spacemodels.schemas.tracker import TrackerCreate  # Local import

    account = create_account()  # Use the fixture from conftest
    tracker_create = TrackerCreate(
        name=f"Test Tracker {uuid4()}",
        tracker_type="github",  # or any valid TrackerType
        account_id=account.id,
        api_key="testkey",
        url="https://example.com/tracker",  # Ensure URL is provided if needed by model validation
    )
    return crud_tracker.create(db=db_session, obj_in=tracker_create)


@pytest.fixture(scope="function")
def test_organization(
    db_session: Session, test_tracker: Tracker
) -> Organization:  # Forward ref for Tracker
    """Creates an organization for use in tests, ensuring a tracker exists."""
    org_name = f"Test Org {uuid4()}"
    org_identifier = f"test-org-{uuid4().hex[:8]}"
    org_create = OrganizationCreate(
        name=org_name,
        identifier=org_identifier,  # Provide identifier
        tracker_id=test_tracker.id,  # Provide tracker_id
    )
    return crud_organization.create(db=db_session, obj_in=org_create)


def test_create_flow(db_session: Session, test_organization: Organization) -> None:
    """Test creating a new flow."""
    flow_name = f"Test Flow {uuid4()}"
    flow_in_corrected = FlowCreate(
        name=flow_name,
        description="A test flow description",
        organization_id=test_organization.id,
        trigger_event_source="test_source",
        trigger_event_type="test_event",
        prompt_template="Test prompt {{data}}",
        openhands_agent_config={"agent": "TestAgent"},
    )
    flow = crud_flow.create(db=db_session, flow_in=flow_in_corrected)
    assert flow is not None
    assert flow.name == flow_name
    assert flow.organization_id == test_organization.id
    assert flow.description == "A test flow description"
    # Removed: assert flow.definition == {"nodes": [], "edges": []}


def test_get_flow(db_session: Session, test_organization: Organization) -> None:
    """Test retrieving a flow by ID."""
    flow_name = f"Test Flow for Get {uuid4()}"
    flow_in = FlowCreate(
        name=flow_name,
        organization_id=test_organization.id,
        trigger_event_source="test_get_source",
        trigger_event_type="test_get_event",
        prompt_template="Test get prompt",
        openhands_agent_config={"agent": "GetAgent"},
        # definition={"key": "value"}, # Not in FlowCreate
    )
    created_flow = crud_flow.create(db=db_session, flow_in=flow_in)
    retrieved_flow = crud_flow.get(db=db_session, id=created_flow.id)
    assert retrieved_flow is not None
    assert retrieved_flow.id == created_flow.id
    assert retrieved_flow.name == flow_name


def test_get_flows_by_organization(
    db_session: Session,
    test_organization: Organization,
    create_account,  # Added create_account fixture
) -> None:
    """Test retrieving flows by organization ID."""
    flow_name1 = f"Org Flow 1 {uuid4()}"
    flow_in1 = FlowCreate(
        name=flow_name1,
        organization_id=test_organization.id,
        trigger_event_source="org_source1",
        trigger_event_type="org_event1",
        prompt_template="Org prompt1",
        openhands_agent_config={"agent": "OrgAgent1"},
        # definition={} # Not in FlowCreate
    )
    crud_flow.create(db=db_session, flow_in=flow_in1)

    flow_name2 = f"Org Flow 2 {uuid4()}"
    flow_in2 = FlowCreate(
        name=flow_name2,
        organization_id=test_organization.id,
        trigger_event_source="org_source2",
        trigger_event_type="org_event2",
        prompt_template="Org prompt2",
        openhands_agent_config={"agent": "OrgAgent2"},
        # definition={} # Not in FlowCreate
    )
    crud_flow.create(db=db_session, flow_in=flow_in2)

    # Create another org and flow to ensure we only get flows for the target org
    # Need another tracker for another organization.
    # We will use the `create_tracker` and `create_account` fixtures from conftest.py
    # to create a new, independent tracker and account for the other organization.
    from spacemodels.crud import (
        crud_tracker as other_crud_tracker,
    )  # Alias to avoid confusion
    from spacemodels.schemas.tracker import TrackerCreate as OtherTrackerCreate  # Alias
    from spacemodels.models import Account as OtherAccount

    # Create a new account for the new tracker
    new_account_for_other_org: OtherAccount = create_account(
        username=f"other_org_user_{uuid4().hex[:4]}",
        email=f"other_org_{uuid4().hex[:4]}@example.com",
    )

    other_tracker_create = OtherTrackerCreate(
        name=f"Other Test Tracker {uuid4()}",
        tracker_type="github",
        account_id=new_account_for_other_org.id,
        api_key="other_test_key",
        url="https://example.com/other_tracker",
    )
    other_tracker = other_crud_tracker.create(
        db=db_session, obj_in=other_tracker_create
    )

    other_org_name = f"Other Test Org {uuid4()}"
    other_org_identifier = f"other-org-{uuid4().hex[:8]}"
    other_org_create = OrganizationCreate(
        name=other_org_name,
        identifier=other_org_identifier,
        tracker_id=other_tracker.id,  # Use the newly created other_tracker's id
    )
    other_organization = crud_organization.create(
        db=db_session, obj_in=other_org_create
    )
    other_flow_in = FlowCreate(
        name="Other Org Flow",
        organization_id=other_organization.id,
        trigger_event_source="other_org_source",
        trigger_event_type="other_org_event",
        prompt_template="Other org prompt",
        openhands_agent_config={"agent": "OtherOrgAgent"},
        # definition={} # Not in FlowCreate
    )
    crud_flow.create(db=db_session, flow_in=other_flow_in)

    flows = crud_flow.get_by_organization(
        db=db_session,
        organization_id=test_organization.id,
    )
    assert flows is not None
    assert len(flows) == 2
    flow_names = {flow.name for flow in flows}
    assert flow_name1 in flow_names
    assert flow_name2 in flow_names


def test_update_flow(db_session: Session, test_organization: Organization) -> None:
    """Test updating an existing flow."""
    flow_name = f"Initial Flow Name {uuid4()}"
    flow_in = FlowCreate(
        name=flow_name,
        organization_id=test_organization.id,
        trigger_event_source="update_source_initial",
        trigger_event_type="update_event_initial",
        prompt_template="Update prompt initial",
        openhands_agent_config={"agent": "UpdateAgentInitial"},
        # definition={"v": 1} # Not in FlowCreate
    )
    created_flow = crud_flow.create(db=db_session, flow_in=flow_in)

    updated_flow_name = f"Updated Flow Name {uuid4()}"
    updated_description = "This is an updated description."
    # updated_definition = {"v": 2, "new_key": "new_value"} # 'definition' is not part of FlowUpdate
    flow_update_data = FlowUpdate(
        name=updated_flow_name,
        description=updated_description,
        # definition=updated_definition, # Removed
    )

    # Fetch the object first, as update_flow expects db_obj
    flow_to_update = crud_flow.get(db=db_session, id=created_flow.id)
    assert flow_to_update is not None  # Ensure it exists before update

    updated_flow = crud_flow.update(
        db=db_session, db_obj=flow_to_update, flow_in=flow_update_data
    )
    assert updated_flow is not None
    assert updated_flow.id == created_flow.id
    assert updated_flow.name == updated_flow_name
    assert updated_flow.description == updated_description
    # assert updated_flow.definition == updated_definition # Removed
    assert (
        updated_flow.organization_id == test_organization.id
    )  # Ensure org_id is not changed


def test_remove_flow(db_session: Session, test_organization: Organization) -> None:
    """Test removing a flow."""
    flow_name = f"Flow to Remove {uuid4()}"
    flow_in = FlowCreate(
        name=flow_name,
        organization_id=test_organization.id,
        trigger_event_source="remove_source",
        trigger_event_type="remove_event",
        prompt_template="Remove prompt",
        openhands_agent_config={"agent": "RemoveAgent"},
        # definition={} # Not in FlowCreate
    )
    created_flow = crud_flow.create(db=db_session, flow_in=flow_in)
    flow_id_to_remove = created_flow.id

    removed_flow = crud_flow.remove(db=db_session, id=flow_id_to_remove)
    assert removed_flow is not None
    assert removed_flow.id == flow_id_to_remove

    retrieved_after_remove = crud_flow.get(
        db=db_session,
        id=flow_id_to_remove,
    )
    assert retrieved_after_remove is None


def test_get_flow_not_found(db_session: Session) -> None:
    """Test retrieving a non-existent flow."""
    non_existent_flow_id = uuid4()
    retrieved_flow = crud_flow.get(
        db=db_session, id=str(non_existent_flow_id)
    )  # Changed to str
    assert retrieved_flow is None


# def test_update_flow_not_found(db_session: Session) -> None:
#     """Test updating a non-existent flow."""
#     # This test is removed because update_flow now expects a db_obj.
#     # The "not found" case for get is covered by test_get_flow_not_found.
#     # If update_flow were to take an ID, this test would be relevant.
#     # For now, ensuring an object exists before updating is the responsibility
#     # of the calling code, typically by fetching it first.
#     pass


def test_remove_flow_not_found(db_session: Session) -> None:
    """Test removing a non-existent flow."""
    non_existent_flow_id = uuid4()
    removed_flow = crud_flow.remove(
        db=db_session, id=str(non_existent_flow_id)
    )  # Changed to str
    assert removed_flow is None
