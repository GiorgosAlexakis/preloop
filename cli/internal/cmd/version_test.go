package cmd

import (
	"bytes"
	"io"
	"os"
	"strings"
	"testing"

	"github.com/preloop/preloop/cli/internal/version"
)

func TestVersionCommandPrintsReleaseVersion(t *testing.T) {
	oldVersion := version.Version
	oldCommit := version.Commit
	oldBuildDate := version.BuildDate
	version.Version = "0.9.0"
	version.Commit = "test-commit"
	version.BuildDate = "2026-03-12T00:00:00Z"
	defer func() {
		version.Version = oldVersion
		version.Commit = oldCommit
		version.BuildDate = oldBuildDate
	}()

	oldStdout := os.Stdout
	readPipe, writePipe, err := os.Pipe()
	if err != nil {
		t.Fatalf("failed to create stdout pipe: %v", err)
	}
	os.Stdout = writePipe
	defer func() {
		os.Stdout = oldStdout
	}()

	runErr := versionCmd.RunE(versionCmd, nil)
	_ = writePipe.Close()
	if runErr != nil {
		t.Fatalf("unexpected error: %v", runErr)
	}

	var output bytes.Buffer
	if _, err := io.Copy(&output, readPipe); err != nil {
		t.Fatalf("failed to read version output: %v", err)
	}

	text := output.String()
	if !strings.Contains(text, "preloop version 0.9.0") {
		t.Fatalf("expected version output to contain release version, got %q", text)
	}
	if !strings.Contains(text, "commit: test-commit") {
		t.Fatalf("expected version output to include commit, got %q", text)
	}
}
