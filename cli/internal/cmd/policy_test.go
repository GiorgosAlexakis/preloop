package cmd

import (
	"bytes"
	"strings"
	"testing"
)

func TestSplitPolicyDiffChanges(t *testing.T) {
	diff := &PolicyDiff{
		HasChanges: true,
		Changes: []DiffChange{
			{Path: "$.tools.read_repo", Operation: "add"},
			{Path: "$.tools.write_repo", Operation: "modify"},
			{Path: "$.approval_workflows.legacy", Operation: "remove"},
		},
	}

	added, modified, removed := splitPolicyDiffChanges(diff)

	if len(added) != 1 || added[0].Path != "$.tools.read_repo" {
		t.Fatalf("unexpected added changes: %+v", added)
	}
	if len(modified) != 1 || modified[0].Path != "$.tools.write_repo" {
		t.Fatalf("unexpected modified changes: %+v", modified)
	}
	if len(removed) != 1 || removed[0].Path != "$.approval_workflows.legacy" {
		t.Fatalf("unexpected removed changes: %+v", removed)
	}
}

func TestBuildPolicyApplyConfirmationPrompt_IncludesRemovals(t *testing.T) {
	diff := &PolicyDiff{
		HasChanges: true,
		Changes: []DiffChange{
			{Operation: "add"},
			{Operation: "modify"},
			{Operation: "remove"},
		},
	}

	prompt := buildPolicyApplyConfirmationPrompt(diff)

	for _, expected := range []string{"1 addition", "1 modification", "1 removal"} {
		if !strings.Contains(prompt, expected) {
			t.Fatalf("expected prompt to contain %q, got %q", expected, prompt)
		}
	}
}

func TestConfirmAction(t *testing.T) {
	testCases := []struct {
		name     string
		input    string
		expected bool
	}{
		{name: "yes", input: "y\n", expected: true},
		{name: "full yes", input: "yes\n", expected: true},
		{name: "default no", input: "\n", expected: false},
	}

	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {
			var output bytes.Buffer
			confirmed, err := confirmAction(
				strings.NewReader(tc.input),
				&output,
				"Proceed? (y/N): ",
			)
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if confirmed != tc.expected {
				t.Fatalf("expected %t, got %t", tc.expected, confirmed)
			}
			if !strings.Contains(output.String(), "Proceed?") {
				t.Fatalf("expected prompt to be written, got %q", output.String())
			}
		})
	}
}
