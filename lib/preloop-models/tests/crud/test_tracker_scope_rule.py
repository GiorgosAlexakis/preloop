"""Tests for TrackerScopeRule CRUD operations and validation."""

from uuid import uuid4

from sqlalchemy.orm import Session

from spacemodels.crud.tracker_scope_rule import crud_tracker_scope_rule
from spacemodels.models.tracker_scope_rule import (
    TrackerScopeRule,
    ScopeType,
    RuleType,
)


class TestTrackerScopeRuleValidation:
    """Test scope rule validation logic."""

    def test_validate_empty_rules(self):
        """Empty rules list should be valid."""
        is_valid, error = crud_tracker_scope_rule.validate_scope_rules([])
        assert is_valid is True
        assert error is None

    def test_validate_org_include_only(self):
        """Organization include rules only should be valid."""
        rules = [
            {
                "scope_type": ScopeType.ORGANIZATION.value,
                "rule_type": RuleType.INCLUDE.value,
                "identifier": "my-org",
            }
        ]
        is_valid, error = crud_tracker_scope_rule.validate_scope_rules(rules)
        assert is_valid is True
        assert error is None

    def test_validate_org_include_with_project_includes(self):
        """Organization with project includes (whitelist mode) should be valid."""
        rules = [
            {
                "scope_type": ScopeType.ORGANIZATION.value,
                "rule_type": RuleType.INCLUDE.value,
                "identifier": "my-org",
            },
            {
                "scope_type": ScopeType.PROJECT.value,
                "rule_type": RuleType.INCLUDE.value,
                "identifier": "my-org/project-a",
            },
            {
                "scope_type": ScopeType.PROJECT.value,
                "rule_type": RuleType.INCLUDE.value,
                "identifier": "my-org/project-b",
            },
        ]
        is_valid, error = crud_tracker_scope_rule.validate_scope_rules(rules)
        assert is_valid is True
        assert error is None

    def test_validate_org_include_with_project_excludes(self):
        """Organization with project excludes (blacklist mode) should be valid."""
        rules = [
            {
                "scope_type": ScopeType.ORGANIZATION.value,
                "rule_type": RuleType.INCLUDE.value,
                "identifier": "my-org",
            },
            {
                "scope_type": ScopeType.PROJECT.value,
                "rule_type": RuleType.EXCLUDE.value,
                "identifier": "my-org/archived-project",
            },
            {
                "scope_type": ScopeType.PROJECT.value,
                "rule_type": RuleType.EXCLUDE.value,
                "identifier": "my-org/deprecated-project",
            },
        ]
        is_valid, error = crud_tracker_scope_rule.validate_scope_rules(rules)
        assert is_valid is True
        assert error is None

    def test_validate_mixed_include_exclude_same_org_invalid(self):
        """Organization with both project includes and excludes should be invalid."""
        rules = [
            {
                "scope_type": ScopeType.ORGANIZATION.value,
                "rule_type": RuleType.INCLUDE.value,
                "identifier": "my-org",
            },
            {
                "scope_type": ScopeType.PROJECT.value,
                "rule_type": RuleType.INCLUDE.value,
                "identifier": "my-org/project-a",
            },
            {
                "scope_type": ScopeType.PROJECT.value,
                "rule_type": RuleType.EXCLUDE.value,
                "identifier": "my-org/project-b",
            },
        ]
        is_valid, error = crud_tracker_scope_rule.validate_scope_rules(rules)
        assert is_valid is False
        assert error is not None
        assert "my-org" in error
        assert "PROJECT INCLUDE" in error
        assert "PROJECT EXCLUDE" in error

    def test_validate_multiple_orgs_separate_rules_valid(self):
        """Multiple organizations with different rule types should be valid."""
        rules = [
            {
                "scope_type": ScopeType.ORGANIZATION.value,
                "rule_type": RuleType.INCLUDE.value,
                "identifier": "org-a",
            },
            {
                "scope_type": ScopeType.PROJECT.value,
                "rule_type": RuleType.INCLUDE.value,
                "identifier": "org-a/project-1",
            },
            {
                "scope_type": ScopeType.ORGANIZATION.value,
                "rule_type": RuleType.INCLUDE.value,
                "identifier": "org-b",
            },
            {
                "scope_type": ScopeType.PROJECT.value,
                "rule_type": RuleType.EXCLUDE.value,
                "identifier": "org-b/project-old",
            },
        ]
        is_valid, error = crud_tracker_scope_rule.validate_scope_rules(rules)
        assert is_valid is True
        assert error is None

    def test_validate_with_enum_objects(self):
        """Validation should work with enum objects (not just string values)."""
        rules = [
            {
                "scope_type": ScopeType.ORGANIZATION,
                "rule_type": RuleType.INCLUDE,
                "identifier": "my-org",
            },
            {
                "scope_type": ScopeType.PROJECT,
                "rule_type": RuleType.INCLUDE,
                "identifier": "my-org/project-a",
            },
        ]
        is_valid, error = crud_tracker_scope_rule.validate_scope_rules(rules)
        assert is_valid is True
        assert error is None

    def test_validate_project_without_slash(self):
        """Project identifiers without org prefix should group by project name."""
        rules = [
            {
                "scope_type": ScopeType.ORGANIZATION.value,
                "rule_type": RuleType.INCLUDE.value,
                "identifier": "my-org",
            },
            {
                "scope_type": ScopeType.PROJECT.value,
                "rule_type": RuleType.INCLUDE.value,
                "identifier": "project-a",
            },
            {
                "scope_type": ScopeType.PROJECT.value,
                "rule_type": RuleType.EXCLUDE.value,
                "identifier": "project-a",  # Same project, different rule type
            },
        ]
        is_valid, error = crud_tracker_scope_rule.validate_scope_rules(rules)
        assert is_valid is False
        assert error is not None
        assert "project-a" in error


class TestTrackerScopeRuleCRUD:
    """Test CRUD operations for TrackerScopeRule."""

    def test_get_by_tracker(self, db_session: Session, create_tracker):
        """Test retrieving scope rules by tracker ID."""
        test_tracker = create_tracker()

        # Create some scope rules
        rule1 = TrackerScopeRule(
            tracker_id=test_tracker.id,
            scope_type=ScopeType.ORGANIZATION.value,
            rule_type=RuleType.INCLUDE.value,
            identifier="org-1",
        )
        rule2 = TrackerScopeRule(
            tracker_id=test_tracker.id,
            scope_type=ScopeType.PROJECT.value,
            rule_type=RuleType.INCLUDE.value,
            identifier="org-1/project-a",
        )
        db_session.add_all([rule1, rule2])
        db_session.commit()

        # Retrieve rules
        rules = crud_tracker_scope_rule.get_by_tracker(
            db_session, tracker_id=test_tracker.id
        )

        assert len(rules) == 2
        assert any(r.identifier == "org-1" for r in rules)
        assert any(r.identifier == "org-1/project-a" for r in rules)

    def test_get_by_tracker_with_account_filter(
        self, db_session: Session, create_tracker
    ):
        """Test retrieving scope rules filtered by account ID."""
        test_tracker = create_tracker()

        # Create scope rules
        rule = TrackerScopeRule(
            tracker_id=test_tracker.id,
            scope_type=ScopeType.ORGANIZATION.value,
            rule_type=RuleType.INCLUDE.value,
            identifier="org-1",
        )
        db_session.add(rule)
        db_session.commit()

        # Retrieve with correct account ID
        rules = crud_tracker_scope_rule.get_by_tracker(
            db_session, tracker_id=test_tracker.id, account_id=test_tracker.account_id
        )
        assert len(rules) == 1

        # Retrieve with wrong account ID (use a valid UUID that doesn't exist)
        wrong_account_uuid = uuid4()
        rules = crud_tracker_scope_rule.get_by_tracker(
            db_session, tracker_id=test_tracker.id, account_id=wrong_account_uuid
        )
        assert len(rules) == 0

    def test_create_scope_rule(self, db_session: Session, create_tracker):
        """Test creating a scope rule."""
        test_tracker = create_tracker()

        rule_data = {
            "tracker_id": test_tracker.id,
            "scope_type": ScopeType.ORGANIZATION.value,
            "rule_type": RuleType.INCLUDE.value,
            "identifier": "test-org",
        }

        rule = crud_tracker_scope_rule.create(db_session, obj_in=rule_data)

        assert rule.id is not None
        assert rule.tracker_id == test_tracker.id
        assert rule.scope_type == ScopeType.ORGANIZATION.value
        assert rule.rule_type == RuleType.INCLUDE.value
        assert rule.identifier == "test-org"

    def test_delete_scope_rule(self, db_session: Session, create_tracker):
        """Test deleting a scope rule."""
        test_tracker = create_tracker()

        rule = TrackerScopeRule(
            tracker_id=test_tracker.id,
            scope_type=ScopeType.ORGANIZATION.value,
            rule_type=RuleType.INCLUDE.value,
            identifier="org-to-delete",
        )
        db_session.add(rule)
        db_session.commit()
        rule_id = rule.id

        # Delete the rule
        crud_tracker_scope_rule.delete(db_session, id=rule_id)

        # Verify deletion
        deleted_rule = crud_tracker_scope_rule.get(db_session, id=rule_id)
        assert deleted_rule is None

    def test_update_scope_rule(self, db_session: Session, create_tracker):
        """Test updating a scope rule."""
        test_tracker = create_tracker()

        rule = TrackerScopeRule(
            tracker_id=test_tracker.id,
            scope_type=ScopeType.ORGANIZATION.value,
            rule_type=RuleType.INCLUDE.value,
            identifier="old-identifier",
        )
        db_session.add(rule)
        db_session.commit()

        # Update the rule
        updated_rule = crud_tracker_scope_rule.update(
            db_session, db_obj=rule, obj_in={"identifier": "new-identifier"}
        )

        assert updated_rule.identifier == "new-identifier"
        assert updated_rule.id == rule.id
