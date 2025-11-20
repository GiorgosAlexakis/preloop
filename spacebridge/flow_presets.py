"""
Flow preset configurations.

These presets are created for every new account to help users get started quickly.
"""

from typing import Any, Dict, List

FLOW_PRESETS: List[Dict[str, Any]] = [
    {
        "name": "Issue Triage Assistant",
        "description": "Automatically analyze new issues, suggest labels, priority, and potential assignees based on content and context.",
        "icon": "funnel",
        "trigger_event_source": None,  # Will be set to tracker_id when instantiated
        "trigger_event_type": "issue.opened",
        "prompt_template": """You are an intelligent issue triage assistant.

A new issue has been created:
Title: {{trigger_event.payload.issue.title}}
Description: {{trigger_event.payload.issue.description}}
Author: {{trigger_event.payload.issue.author}}
Repository: {{trigger_event.payload.repository.name}}

Your task:
1. Analyze the issue content and determine appropriate labels
2. Suggest a priority level (low, medium, high, critical)
3. Recommend potential assignees based on the issue type
4. Check if this might be a duplicate of existing issues
5. Suggest any relevant documentation or resources

Use the search_issues tool to check for similar issues.
Use the update_issue tool to add your suggested labels and priority.
Provide a clear summary of your analysis in a comment on the issue.""",
        "agent_type": "codex",
        "agent_config": {
            "sandbox_type": "exec",
            "enable_auto_lint": False,
        },
        "allowed_mcp_servers": [],
        "allowed_mcp_tools": [
            {"name": "search_issues"},
            {"name": "get_issue"},
            {"name": "update_issue"},
            {"name": "add_comment"},
        ],
        "git_clone_config": None,
        "is_preset": True,
    },
    {
        "name": "Pull Request Reviewer",
        "description": "Automatically review pull requests for code quality, potential bugs, security issues, and best practices.",
        "icon": "code-square",
        "trigger_event_source": None,  # Will be set to tracker_id when instantiated
        "trigger_event_type": "pull_request.opened",
        "prompt_template": """You are an expert code reviewer.

A new pull request has been created:
Title: {{trigger_event.payload.pull_request.title}}
Description: {{trigger_event.payload.pull_request.description}}
Author: {{trigger_event.payload.pull_request.author}}
Repository: {{trigger_event.payload.repository.name}}
Branch: {{trigger_event.payload.pull_request.source_branch}} → {{trigger_event.payload.pull_request.target_branch}}

Your task:
1. Clone the repository and review the code changes
2. Check for:
   - Code quality issues
   - Potential bugs or edge cases
   - Security vulnerabilities
   - Performance concerns
   - Best practice violations
   - Missing tests or documentation
3. Provide constructive feedback with specific line references
4. Suggest improvements and alternatives
5. Highlight any critical issues that should block the merge

Use the add_comment tool to post your review findings.
Be thorough but constructive in your feedback.""",
        "agent_type": "codex",
        "agent_config": {
            "sandbox_type": "exec",
            "enable_auto_lint": True,
        },
        "allowed_mcp_servers": [],
        "allowed_mcp_tools": [
            {"name": "get_issue"},
            {"name": "add_comment"},
            {"name": "update_issue"},
        ],
        "git_clone_config": {
            "enabled": True,
            "repositories": [],  # Will be configured per instance
            "git_user_name": "Preloop AI",
            "git_user_email": "hello@preloop.ai",
            "source_branch": None,  # Use PR source branch
            "target_branch": None,
            "create_pull_request": False,
        },
        "is_preset": True,
    },
    {
        "name": "Automated Issue Implementation",
        "description": "Convert issue descriptions into working code implementations, create branches, and open pull requests automatically.",
        "icon": "lightning",
        "trigger_event_source": None,  # Will be set to tracker_id when instantiated
        "trigger_event_type": "issue.labeled",
        "trigger_config": {
            "filter_conditions": {"labels": ["auto-implement", "ready-for-automation"]}
        },
        "prompt_template": """You are an expert software engineer.

An issue has been marked for automatic implementation:
Title: {{trigger_event.payload.issue.title}}
Description: {{trigger_event.payload.issue.description}}
Repository: {{trigger_event.payload.repository.name}}
Issue Number: {{trigger_event.payload.issue.number}}

Your task:
1. Clone the repository
2. Create a new branch for this implementation
3. Implement the requested changes based on the issue description
4. Write appropriate tests
5. Ensure code follows project conventions and passes linting
6. Commit your changes with clear, descriptive messages
7. Create a pull request referencing the original issue
8. Comment on the issue with a summary of what was implemented

Use best practices for the project's language and framework.
Make sure to handle edge cases and error conditions.""",
        "agent_type": "codex",
        "agent_config": {
            "sandbox_type": "exec",
            "enable_auto_lint": True,
        },
        "allowed_mcp_servers": [],
        "allowed_mcp_tools": [
            {"name": "get_issue"},
            {"name": "add_comment"},
            {"name": "update_issue"},
            {"name": "create_issue"},
        ],
        "git_clone_config": {
            "enabled": True,
            "repositories": [],  # Will be configured per instance
            "git_user_name": "Preloop AI",
            "git_user_email": "hello@preloop.ai",
            "source_branch": "main",
            "target_branch": None,  # Auto-generated from issue
            "create_pull_request": True,
            "pull_request_title": "Implements: {{trigger_event.payload.issue.title}}",
            "pull_request_description": "Automated implementation for #{{trigger_event.payload.issue.number}}\n\nCloses #{{trigger_event.payload.issue.number}}",
        },
        "is_preset": True,
    },
    {
        "name": "Documentation Generator",
        "description": "Automatically generate or update documentation based on code changes, pull requests, or explicit requests.",
        "icon": "book",
        "trigger_event_source": None,  # Will be set to tracker_id when instantiated
        "trigger_event_type": "issue.labeled",
        "trigger_config": {
            "filter_conditions": {"labels": ["documentation", "docs-needed"]}
        },
        "prompt_template": """You are a technical documentation specialist.

A documentation request has been created:
Title: {{trigger_event.payload.issue.title}}
Description: {{trigger_event.payload.issue.description}}
Repository: {{trigger_event.payload.repository.name}}

Your task:
1. Clone the repository
2. Analyze the codebase to understand the changes/features needing documentation
3. Generate or update relevant documentation:
   - README files
   - API documentation
   - User guides
   - Code comments and docstrings
   - Architecture diagrams (in Markdown format)
4. Ensure documentation is clear, comprehensive, and follows project style
5. Create a pull request with the documentation updates
6. Comment on the issue with a summary of the documentation added

Focus on clarity, completeness, and examples.
Include code snippets and diagrams where appropriate.""",
        "agent_type": "codex",
        "agent_config": {
            "sandbox_type": "exec",
            "enable_auto_lint": False,
        },
        "allowed_mcp_servers": [],
        "allowed_mcp_tools": [
            {"name": "get_issue"},
            {"name": "add_comment"},
            {"name": "update_issue"},
        ],
        "git_clone_config": {
            "enabled": True,
            "repositories": [],  # Will be configured per instance
            "git_user_name": "Preloop AI",
            "git_user_email": "hello@preloop.ai",
            "source_branch": "main",
            "target_branch": None,  # Auto-generated
            "create_pull_request": True,
            "pull_request_title": "Docs: {{trigger_event.payload.issue.title}}",
            "pull_request_description": "Documentation updates for #{{trigger_event.payload.issue.number}}\n\nCloses #{{trigger_event.payload.issue.number}}",
        },
        "is_preset": True,
    },
    {
        "name": "Bug Reproduction Assistant",
        "description": "Automatically attempt to reproduce reported bugs, gather diagnostics, and provide detailed analysis.",
        "icon": "bug",
        "trigger_event_source": None,  # Will be set to tracker_id when instantiated
        "trigger_event_type": "issue.labeled",
        "trigger_config": {
            "filter_conditions": {"labels": ["bug", "needs-reproduction"]}
        },
        "prompt_template": """You are a bug analysis specialist.

A bug has been reported:
Title: {{trigger_event.payload.issue.title}}
Description: {{trigger_event.payload.issue.description}}
Repository: {{trigger_event.payload.repository.name}}
Steps to Reproduce: {{trigger_event.payload.issue.steps_to_reproduce}}

Your task:
1. Clone the repository
2. Attempt to reproduce the bug following the provided steps
3. Gather diagnostics:
   - Stack traces
   - Environment information
   - Related log entries
4. Analyze the root cause
5. Suggest potential fixes or workarounds
6. Document your findings in a detailed comment

If you can reproduce the bug, provide clear evidence.
If you cannot, explain what might be missing from the reproduction steps.""",
        "agent_type": "codex",
        "agent_config": {
            "sandbox_type": "exec",
            "enable_auto_lint": False,
        },
        "allowed_mcp_servers": [],
        "allowed_mcp_tools": [
            {"name": "get_issue"},
            {"name": "add_comment"},
            {"name": "update_issue"},
        ],
        "git_clone_config": {
            "enabled": True,
            "repositories": [],  # Will be configured per instance
            "git_user_name": "Preloop AI",
            "git_user_email": "hello@preloop.ai",
            "source_branch": "main",
            "target_branch": None,
            "create_pull_request": False,
        },
        "is_preset": True,
    },
    {
        "name": "Release Notes Generator",
        "description": "Automatically generate release notes from merged pull requests, commits, and closed issues.",
        "icon": "megaphone",
        "trigger_event_source": None,  # Will be set to tracker_id when instantiated
        "trigger_event_type": "tag.created",
        "prompt_template": """You are a release notes specialist.

A new release tag has been created:
Tag: {{trigger_event.payload.tag.name}}
Repository: {{trigger_event.payload.repository.name}}

Your task:
1. Use search_issues to find all pull requests and issues closed since the last release
2. Categorize changes:
   - New Features
   - Improvements
   - Bug Fixes
   - Breaking Changes
   - Security Updates
   - Documentation Updates
3. Generate comprehensive release notes in Markdown format
4. Create an issue with the release notes
5. Tag it appropriately

Format release notes professionally with:
- Clear section headers
- Bullet points for each change
- Links to relevant PRs and issues
- Credits to contributors""",
        "agent_type": "codex",
        "agent_config": {
            "sandbox_type": "exec",
            "enable_auto_lint": False,
        },
        "allowed_mcp_servers": [],
        "allowed_mcp_tools": [
            {"name": "search_issues"},
            {"name": "get_issue"},
            {"name": "create_issue"},
            {"name": "add_comment"},
        ],
        "git_clone_config": None,
        "is_preset": True,
    },
    {
        "name": "Security Vulnerability Scanner",
        "description": "Scan pull requests and new code for potential security vulnerabilities and common security anti-patterns.",
        "icon": "shield-lock",
        "trigger_event_source": None,  # Will be set to tracker_id when instantiated
        "trigger_event_type": "pull_request.opened",
        "prompt_template": """You are a security analysis expert.

A pull request has been opened:
Title: {{trigger_event.payload.pull_request.title}}
Repository: {{trigger_event.payload.repository.name}}

Your task:
1. Clone the repository and checkout the PR branch
2. Scan the code changes for security issues:
   - SQL injection vulnerabilities
   - XSS vulnerabilities
   - Authentication/Authorization issues
   - Insecure cryptography
   - Hardcoded secrets or credentials
   - Unsafe deserialization
   - Path traversal vulnerabilities
   - Command injection risks
3. Check dependencies for known vulnerabilities
4. Review security-sensitive operations
5. Provide a security report with severity levels
6. Suggest remediation steps

Comment on the PR with your findings.
Mark critical security issues prominently.""",
        "agent_type": "codex",
        "agent_config": {
            "sandbox_type": "exec",
            "enable_auto_lint": True,
        },
        "allowed_mcp_servers": [],
        "allowed_mcp_tools": [
            {"name": "get_issue"},
            {"name": "add_comment"},
            {"name": "update_issue"},
        ],
        "git_clone_config": {
            "enabled": True,
            "repositories": [],  # Will be configured per instance
            "git_user_name": "Preloop AI",
            "git_user_email": "hello@preloop.ai",
            "source_branch": None,  # Use PR branch
            "target_branch": None,
            "create_pull_request": False,
        },
        "is_preset": True,
    },
]
