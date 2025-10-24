"""Tests for issue compliance Pydantic schemas."""

import json
from datetime import datetime


from spacebridge.schemas.issue_compliance import (
    Annotation,
    CompliancePromptMetadata,
    ComplianceSuggestionResponse,
    ComplianceWorkflow,
    IssueComplianceResultBase,
    IssueComplianceResultCreate,
    IssueComplianceResultResponse,
    Prompt,
)


class TestAnnotation:
    """Test Annotation schema."""

    def test_create_annotation(self):
        """Test creating Annotation with all fields."""
        annotation = Annotation(
            text="Issue description",
            label="acceptance_criteria",
            status="missing",
            comment="Acceptance criteria not provided",
        )

        assert annotation.text == "Issue description"
        assert annotation.label == "acceptance_criteria"
        assert annotation.status == "missing"
        assert annotation.comment == "Acceptance criteria not provided"


class TestIssueComplianceResultBase:
    """Test IssueComplianceResultBase schema."""

    def test_create_with_required_fields(self):
        """Test creating IssueComplianceResultBase with required fields."""
        result = IssueComplianceResultBase(
            prompt_id="prompt-123",
            name="Definition of Ready",
            compliance_factor=0.75,
            reason="Missing acceptance criteria",
            suggestion="Add clear acceptance criteria",
            issue_id="issue-456",
        )

        assert result.prompt_id == "prompt-123"
        assert result.name == "Definition of Ready"
        assert result.compliance_factor == 0.75
        assert result.reason == "Missing acceptance criteria"
        assert result.suggestion == "Add clear acceptance criteria"
        assert result.issue_id == "issue-456"
        assert result.annotated_description is None

    def test_create_with_annotated_description(self):
        """Test creating with annotated description."""
        annotations = [
            Annotation(
                text="User story",
                label="user_story",
                status="present",
                comment="Clear user story",
            ),
            Annotation(
                text="Acceptance criteria",
                label="acceptance_criteria",
                status="missing",
                comment="No acceptance criteria",
            ),
        ]

        result = IssueComplianceResultBase(
            prompt_id="prompt-123",
            name="Definition of Ready",
            compliance_factor=0.5,
            reason="Partial compliance",
            suggestion="Add acceptance criteria",
            issue_id="issue-456",
            annotated_description=annotations,
        )

        assert len(result.annotated_description) == 2
        assert result.annotated_description[0].label == "user_story"
        assert result.annotated_description[1].status == "missing"


class TestIssueComplianceResultCreate:
    """Test IssueComplianceResultCreate schema."""

    def test_inherits_from_base(self):
        """Test that Create inherits from Base."""
        result = IssueComplianceResultCreate(
            prompt_id="prompt-123",
            name="Definition of Ready",
            compliance_factor=0.8,
            reason="Good compliance",
            suggestion="Minor improvements",
            issue_id="issue-456",
        )

        assert isinstance(result, IssueComplianceResultBase)
        assert result.prompt_id == "prompt-123"


class TestIssueComplianceResultResponse:
    """Test IssueComplianceResultResponse schema."""

    def test_create_response(self):
        """Test creating IssueComplianceResultResponse."""
        created_at = datetime.now()
        updated_at = datetime.now()

        response = IssueComplianceResultResponse(
            id="result-789",
            prompt_id="prompt-123",
            name="Definition of Ready",
            short_name="dor",
            compliance_factor=0.9,
            reason="Excellent compliance",
            suggestion="No changes needed",
            issue_id="issue-456",
            created_at=created_at,
            updated_at=updated_at,
        )

        assert response.id == "result-789"
        assert response.short_name == "dor"
        assert response.created_at == created_at
        assert response.updated_at == updated_at

    def test_parse_annotated_description_from_json_string(self):
        """Test that JSON string annotated_description is parsed."""
        annotations_json = json.dumps(
            [
                {
                    "text": "Story text",
                    "label": "user_story",
                    "status": "present",
                    "comment": "Good",
                },
                {
                    "text": "Criteria text",
                    "label": "acceptance_criteria",
                    "status": "missing",
                    "comment": "Add criteria",
                },
            ]
        )

        response = IssueComplianceResultResponse(
            id="result-789",
            prompt_id="prompt-123",
            name="Definition of Ready",
            short_name="dor",
            compliance_factor=0.7,
            reason="Needs improvement",
            suggestion="Add acceptance criteria",
            issue_id="issue-456",
            annotated_description=annotations_json,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        assert response.annotated_description is not None
        assert isinstance(response.annotated_description, list)
        assert len(response.annotated_description) == 2
        # Pydantic converts dicts to Annotation objects
        assert isinstance(response.annotated_description[0], (dict, Annotation))
        if isinstance(response.annotated_description[0], Annotation):
            assert response.annotated_description[0].label == "user_story"
            assert response.annotated_description[1].status == "missing"
        else:
            assert response.annotated_description[0]["label"] == "user_story"
            assert response.annotated_description[1]["status"] == "missing"

    def test_parse_annotated_description_from_list(self):
        """Test that list annotated_description is parsed."""
        annotations = [
            {
                "text": "Story",
                "label": "user_story",
                "status": "present",
                "comment": "Good",
            }
        ]

        response = IssueComplianceResultResponse(
            id="result-789",
            prompt_id="prompt-123",
            name="Definition of Ready",
            short_name="dor",
            compliance_factor=0.8,
            reason="Good",
            suggestion="None",
            issue_id="issue-456",
            annotated_description=annotations,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        # Pydantic converts dicts to Annotation objects
        assert len(response.annotated_description) == 1
        assert isinstance(response.annotated_description[0], (dict, Annotation))
        if isinstance(response.annotated_description[0], Annotation):
            assert response.annotated_description[0].label == "user_story"
            assert response.annotated_description[0].text == "Story"
        else:
            assert response.annotated_description[0]["label"] == "user_story"
            assert response.annotated_description[0]["text"] == "Story"

    def test_parse_annotated_description_invalid_json(self):
        """Test that invalid JSON returns None."""
        invalid_json = "this is not valid json {"

        response = IssueComplianceResultResponse(
            id="result-789",
            prompt_id="prompt-123",
            name="Definition of Ready",
            short_name="dor",
            compliance_factor=0.8,
            reason="Good",
            suggestion="None",
            issue_id="issue-456",
            annotated_description=invalid_json,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        # Invalid JSON should return None per the validator logic
        assert response.annotated_description is None

    def test_from_attributes_config(self):
        """Test that from_attributes is enabled."""
        assert IssueComplianceResultResponse.Config.from_attributes is True


class TestComplianceSuggestionResponse:
    """Test ComplianceSuggestionResponse schema."""

    def test_create_suggestion_response(self):
        """Test creating ComplianceSuggestionResponse."""
        response = ComplianceSuggestionResponse(
            title="Improved Title: Add User Authentication",
            description="As a user, I want to log in with email and password...",
            changes="Added user story format and acceptance criteria",
        )

        assert response.title == "Improved Title: Add User Authentication"
        assert "As a user" in response.description
        assert response.changes == "Added user story format and acceptance criteria"


class TestCompliancePromptMetadata:
    """Test CompliancePromptMetadata schema."""

    def test_create_prompt_metadata(self):
        """Test creating CompliancePromptMetadata."""
        metadata = CompliancePromptMetadata(
            id="prompt-abc",
            name="Definition of Ready",
            short_name="dor",
        )

        assert metadata.id == "prompt-abc"
        assert metadata.name == "Definition of Ready"
        assert metadata.short_name == "dor"


class TestPrompt:
    """Test Prompt schema."""

    def test_create_prompt(self):
        """Test creating Prompt."""
        prompt = Prompt(
            name="evaluate_dor",
            system="You are a compliance evaluator...",
            user="Evaluate this issue: {issue_description}",
        )

        assert prompt.name == "evaluate_dor"
        assert prompt.system == "You are a compliance evaluator..."
        assert prompt.user == "Evaluate this issue: {issue_description}"


class TestComplianceWorkflow:
    """Test ComplianceWorkflow schema."""

    def test_create_compliance_workflow(self):
        """Test creating ComplianceWorkflow."""
        evaluate_prompt = Prompt(
            name="evaluate",
            system="System prompt for evaluation",
            user="User prompt for evaluation",
        )

        improvement_prompt = Prompt(
            name="improve",
            system="System prompt for improvement",
            user="User prompt for improvement",
        )

        workflow = ComplianceWorkflow(
            name="Definition of Ready",
            short_name="dor",
            evaluate=evaluate_prompt,
            propose_improvement=improvement_prompt,
        )

        assert workflow.name == "Definition of Ready"
        assert workflow.short_name == "dor"
        assert workflow.evaluate.name == "evaluate"
        assert workflow.propose_improvement.name == "improve"
