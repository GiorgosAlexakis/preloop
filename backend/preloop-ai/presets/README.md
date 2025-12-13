# Flow Presets

This directory contains YAML files defining flow presets that are created for new accounts.

## File Naming Convention

Preset files should be named with a numeric prefix to control the order they appear:

```
01-issue-triage.yml
02-pr-reviewer.yml
03-implementation.yml
```

## File Format

Each YAML file should define a single flow preset:

```yaml
name: "Issue Triage Assistant"
description: "Automatically analyze new issues..."
icon: "funnel"
trigger_event_source: null  # Set to tracker_id when instantiated
trigger_event_type: "issue.opened"
prompt_template: |
  You are an intelligent issue triage assistant.
  ...
agent_type: "codex"
agent_config:
  sandbox_type: "exec"
  enable_auto_lint: false
allowed_mcp_servers: []
allowed_mcp_tools:
  - name: "search_issues"
  - name: "get_issue"
git_clone_config: null
is_preset: true
```

## Notes

- The `is_preset` field defaults to `true` if not specified
- Presets are loaded at application startup and cached
- Invalid YAML files will cause a startup error
