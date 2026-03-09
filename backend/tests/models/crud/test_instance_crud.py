"""Tests for Instance CRUD operations."""

from uuid import uuid4

from sqlalchemy.orm import Session

from preloop.models.crud import crud_instance
from preloop.models.models.instance import Instance


def _create_instance(
    db_session: Session,
    *,
    instance_uuid=None,
    version="1.0.0",
    edition="oss",
    is_active=True,
    **kwargs,
) -> Instance:
    """Helper to create an Instance for testing."""
    instance_uuid = instance_uuid or uuid4()
    obj_in = {
        "instance_uuid": instance_uuid,
        "version": version,
        "edition": edition,
        "is_active": is_active,
        **kwargs,
    }
    return crud_instance.create(db_session, obj_in=obj_in)


class TestInstanceCRUD:
    """Test CRUD operations for Instance."""

    def test_create_and_get_by_uuid(self, db_session: Session):
        """Test creating an instance and retrieving by UUID."""
        inst_uuid = uuid4()
        instance = _create_instance(
            db_session, instance_uuid=inst_uuid, version="2.0.0"
        )
        db_session.flush()

        assert instance.id is not None
        assert instance.instance_uuid == inst_uuid
        assert instance.version == "2.0.0"
        assert instance.edition == "oss"
        assert instance.is_active is True

        found = crud_instance.get_by_uuid(db_session, instance_uuid=inst_uuid)
        assert found is not None
        assert found.id == instance.id

    def test_get_by_uuid_not_found(self, db_session: Session):
        """Test get_by_uuid returns None for non-existent instance."""
        result = crud_instance.get_by_uuid(db_session, instance_uuid=uuid4())
        assert result is None

    def test_get_active(self, db_session: Session):
        """Test retrieving active instances."""
        uuid1, uuid2, uuid3 = uuid4(), uuid4(), uuid4()
        _create_instance(db_session, instance_uuid=uuid1, is_active=True)
        _create_instance(db_session, instance_uuid=uuid2, is_active=True)
        _create_instance(db_session, instance_uuid=uuid3, is_active=False)
        db_session.flush()

        active = crud_instance.get_active(db_session)
        active_uuids = {i.instance_uuid for i in active}
        assert uuid1 in active_uuids
        assert uuid2 in active_uuids
        assert uuid3 not in active_uuids
        assert all(i.is_active for i in active)

    def test_get_active_with_pagination(self, db_session: Session):
        """Test get_active with skip and limit."""
        for _ in range(5):
            _create_instance(db_session, instance_uuid=uuid4(), is_active=True)
        db_session.flush()

        page = crud_instance.get_active(db_session, skip=1, limit=2)
        assert len(page) == 2

    def test_get_by_edition(self, db_session: Session):
        """Test retrieving instances by edition."""
        uuid_oss1, uuid_oss2, uuid_ent = uuid4(), uuid4(), uuid4()
        _create_instance(db_session, instance_uuid=uuid_oss1, edition="oss")
        _create_instance(db_session, instance_uuid=uuid_ent, edition="enterprise")
        _create_instance(db_session, instance_uuid=uuid_oss2, edition="oss")
        db_session.flush()

        oss_instances = crud_instance.get_by_edition(db_session, edition="oss")
        oss_uuids = {i.instance_uuid for i in oss_instances}
        assert uuid_oss1 in oss_uuids
        assert uuid_oss2 in oss_uuids
        assert all(i.edition == "oss" for i in oss_instances)

        ent_instances = crud_instance.get_by_edition(db_session, edition="enterprise")
        assert any(i.instance_uuid == uuid_ent for i in ent_instances)
        assert ent_instances[0].edition == "enterprise"

    def test_get_by_edition_active_only(self, db_session: Session):
        """Test get_by_edition with active_only filter."""
        uuid_active, uuid_inactive = uuid4(), uuid4()
        _create_instance(
            db_session,
            instance_uuid=uuid_active,
            edition="oss",
            is_active=True,
        )
        _create_instance(
            db_session,
            instance_uuid=uuid_inactive,
            edition="oss",
            is_active=False,
        )
        db_session.flush()

        active = crud_instance.get_by_edition(
            db_session, edition="oss", active_only=True
        )
        active_uuids = {i.instance_uuid for i in active}
        assert uuid_active in active_uuids
        assert uuid_inactive not in active_uuids
        assert all(i.is_active for i in active)

    def test_get_with_coordinates(self, db_session: Session):
        """Test retrieving instances with lat/lon coordinates."""
        _create_instance(
            db_session,
            instance_uuid=uuid4(),
            lat=40.7128,
            lon=-74.0060,
        )
        _create_instance(db_session, instance_uuid=uuid4())
        db_session.flush()

        with_coords = crud_instance.get_with_coordinates(db_session)
        assert len(with_coords) == 1
        assert with_coords[0].lat == 40.7128
        assert with_coords[0].lon == -74.0060

    def test_get_all_paginated(self, db_session: Session):
        """Test get_all_paginated with filters."""
        uuids = [uuid4() for _ in range(4)]
        for i in range(4):
            _create_instance(
                db_session,
                instance_uuid=uuids[i],
                edition="oss" if i % 2 == 0 else "enterprise",
                is_active=i < 3,
            )
        db_session.flush()

        all_instances = crud_instance.get_all_paginated(db_session)
        created_uuids = {i.instance_uuid for i in all_instances}
        assert all(u in created_uuids for u in uuids)

        active_only = crud_instance.get_all_paginated(db_session, active_only=True)
        assert all(i.is_active for i in active_only)
        assert uuids[3] not in {i.instance_uuid for i in active_only}

        oss_only = crud_instance.get_all_paginated(db_session, edition="oss")
        assert all(i.edition == "oss" for i in oss_only)
        assert uuids[0] in {i.instance_uuid for i in oss_only}
        assert uuids[2] in {i.instance_uuid for i in oss_only}

    def test_count_total(self, db_session: Session):
        """Test counting total instances."""
        initial = crud_instance.count_total(db_session)
        _create_instance(db_session, instance_uuid=uuid4())
        _create_instance(db_session, instance_uuid=uuid4())
        db_session.flush()

        count = crud_instance.count_total(db_session)
        assert count == initial + 2

    def test_count_active(self, db_session: Session):
        """Test counting active instances."""
        initial = crud_instance.count_active(db_session)
        _create_instance(db_session, instance_uuid=uuid4(), is_active=True)
        _create_instance(db_session, instance_uuid=uuid4(), is_active=False)
        _create_instance(db_session, instance_uuid=uuid4(), is_active=True)
        db_session.flush()

        count = crud_instance.count_active(db_session)
        assert count == initial + 2

    def test_count_by_edition(self, db_session: Session):
        """Test counting instances by edition."""
        initial_oss = crud_instance.count_by_edition(db_session, edition="oss")
        initial_ent = crud_instance.count_by_edition(db_session, edition="enterprise")
        _create_instance(db_session, instance_uuid=uuid4(), edition="oss")
        _create_instance(db_session, instance_uuid=uuid4(), edition="oss")
        _create_instance(db_session, instance_uuid=uuid4(), edition="enterprise")
        db_session.flush()

        oss_count = crud_instance.count_by_edition(db_session, edition="oss")
        assert oss_count == initial_oss + 2

        ent_count = crud_instance.count_by_edition(db_session, edition="enterprise")
        assert ent_count == initial_ent + 1

    def test_get_version_counts(self, db_session: Session):
        """Test getting instance counts by version."""
        _create_instance(db_session, instance_uuid=uuid4(), version="1.0.0")
        _create_instance(db_session, instance_uuid=uuid4(), version="1.0.0")
        _create_instance(db_session, instance_uuid=uuid4(), version="2.0.0")
        db_session.flush()

        counts = crud_instance.get_version_counts(db_session)
        assert counts.get("1.0.0") == 2
        assert counts.get("2.0.0") == 1

    def test_get_country_counts(self, db_session: Session):
        """Test getting instance counts by country code."""
        _create_instance(
            db_session,
            instance_uuid=uuid4(),
            country_code="US",
        )
        _create_instance(
            db_session,
            instance_uuid=uuid4(),
            country_code="US",
        )
        _create_instance(
            db_session,
            instance_uuid=uuid4(),
            country_code="DE",
        )
        db_session.flush()

        counts = crud_instance.get_country_counts(db_session)
        assert counts.get("US") == 2
        assert counts.get("DE") == 1
