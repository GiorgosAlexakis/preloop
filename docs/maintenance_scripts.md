# SpaceBridge Maintenance Scripts

This document describes the available maintenance scripts for SpaceBridge database operations.

## Cleanup Out-of-Scope Issues

**Script:** `spacebridge/scripts/cleanup_out_of_scope_issues.py`

### Purpose

Removes issues, comments, and embeddings that are no longer within the configured tracker scope rules. This is useful for:

- Cleaning up after updating tracker scope rules
- Maintaining database hygiene
- Ensuring data consistency with current scope configuration

### How It Works

The script follows the same scope rule logic as the SpaceSync scanner:

1. **Organization Inclusion (Required)**: Organization must be in an INCLUDE rule
2. **Project Exclusion (Disqualifying)**: Project must NOT be in an EXCLUDE rule
3. **Project Inclusion (If Any Exist)**: If PROJECT INCLUDE rules exist, project must be in them

### Usage

```bash
# Dry run - see what would be deleted without making changes
python -m spacebridge.scripts.cleanup_out_of_scope_issues --dry-run

# Delete out-of-scope issues for a specific account
python -m spacebridge.scripts.cleanup_out_of_scope_issues --account-id <uuid>

# Delete out-of-scope issues for a specific tracker
python -m spacebridge.scripts.cleanup_out_of_scope_issues --tracker-id <uuid>

# Delete without confirmation prompt (use with caution!)
python -m spacebridge.scripts.cleanup_out_of_scope_issues --yes
```

### Options

- `--account-id <uuid>`: Filter by account ID (UUID)
- `--tracker-id <uuid>`: Filter by tracker ID (UUID)
- `--dry-run`: Show what would be deleted without actually deleting
- `--yes` / `-y`: Skip confirmation prompt

### Example Output

```
================================================================================
Found 25 out-of-scope issues:
================================================================================

Tracker: GitHub Production (abc-123-def)
  Project: old-project
    - PROJ-1: Fix authentication bug in login flow...
    - PROJ-2: Update dependencies for security patch...
    ... and 3 more issues

Tracker: GitLab Test (xyz-789-uvw)
  Project: deprecated-service
    - TEST-10: Implement new API endpoint for user management...
    ... and 19 more issues

================================================================================
Summary:
  Issues to delete: 25
  Comments to delete: 47
  Embeddings to delete: 50
================================================================================

⚠️  Are you sure you want to delete these issues? This cannot be undone. [y/N]:
```

### What Gets Deleted

When you confirm deletion, the script removes:

1. **Issues**: All issues that don't match current scope rules
2. **Comments**: All comments associated with those issues
3. **Embeddings**: All embeddings associated with those issues

### Safety Features

- **Dry Run Mode**: Test the script without making changes
- **Confirmation Prompt**: Requires explicit confirmation before deletion
- **Detailed Summary**: Shows exactly what will be deleted
- **Grouping**: Results grouped by tracker and project for clarity

### When to Use

Use this script:

- After updating tracker scope rules to narrow the scope
- When deactivating projects or organizations
- During periodic database maintenance
- Before major data migrations

### Best Practices

1. **Always run with `--dry-run` first** to review what will be deleted
2. **Backup your database** before running in production
3. **Run during low-traffic periods** to minimize impact
4. **Document the reason** for running the cleanup in your change log
5. **Verify scope rules** are correctly configured before running

### Technical Details

The script:
- Uses the same `get_accessible_projects()` helper as the API endpoints
- Applies TrackerScopeRule filtering consistently with the scanner
- Deletes related records in the correct order (comments → embeddings → issues)
- Uses batch operations for efficiency
- Commits changes only after successful deletion of all records

### Testing

Run the test suite:

```bash
pytest tests/scripts/test_cleanup_out_of_scope_issues.py -v
```

### See Also

- `spacebridge/api/common.py`: Contains the shared `get_accessible_projects()` helper
- `spacesync/spacesync/scanner/core.py`: Reference implementation of scope rule logic
- `SpaceModels/spacemodels/models/tracker_scope_rule.py`: TrackerScopeRule model definition
