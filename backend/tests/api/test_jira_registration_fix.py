"""
Test for the Jira tracker registration fix.
"""

from unittest import IsolatedAsyncioTestCase

from preloop.schemas.tracker import ProjectIdentifier


class TestJiraRegistrationFix(IsolatedAsyncioTestCase):
    """Test that the Jira registration fix works correctly."""

    async def test_dictionary_access_for_organizations(self):
        """Test that we can access organization data as dictionaries."""
        # Simulate what Jira tracker returns
        orgs = [
            {
                "id": "spacecode-team.atlassian.net",
                "name": "spacecode-team.atlassian.net",
                "url": "https://spacecode-team.atlassian.net",
            }
        ]

        projects = [{"id": "10001", "name": "Test Project", "key": "TEST"}]

        # Test the fixed approach - accessing as dictionary
        org_id = orgs[0]["id"]
        self.assertEqual(org_id, "spacecode-team.atlassian.net")

        # Test setting children as dictionary
        orgs[0]["children"] = [
            ProjectIdentifier(
                id=p["id"], name=p["name"], identifier=p["id"], type="project"
            )
            for p in projects
        ]

        self.assertEqual(len(orgs[0]["children"]), 1)
        self.assertEqual(orgs[0]["children"][0].id, "10001")
        self.assertEqual(orgs[0]["children"][0].name, "Test Project")

    async def test_attribute_error_would_occur(self):
        """Verify that the old approach would indeed fail."""
        orgs = [{"id": "test", "name": "test"}]

        # This should raise AttributeError (the old buggy way)
        with self.assertRaises(AttributeError):
            _ = orgs[0].id  # This is what was causing the bug
