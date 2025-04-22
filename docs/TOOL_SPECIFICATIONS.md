# SpaceBridge MCP Tool Specifications

## Issue Management Tools

### 1. `search_issues`

**Purpose**: Performs hybrid search using vector similarity and direct API queries to find relevant issues across all configured trackers.

**Parameters**:
- `organization`: String (required) - Organization identifier
- `project`: String (required) - Project identifier
- `query`: String (required) - Natural language search query
- `limit`: Integer (optional, default=10) - Maximum number of results to return
- `trackers`: List[String] (optional) - Specific issue trackers to search (defaults to all configured for project)
- `status`: List[String] (optional) - Filter by issue status
- `labels`: List[String] (optional) - Filter by issue labels/tags
- `created_after`: DateTime (optional) - Filter by creation date
- `created_before`: DateTime (optional) - Filter by creation date
- `updated_after`: DateTime (optional) - Filter by update date
- `updated_before`: DateTime (optional) - Filter by update date
- `assigned_to`: String (optional) - Filter by assignee

**Returns**:
- List of issue objects with standardized fields
- Relevance score for each result
- Source tracker information

### 2. `find_duplicate`

**Purpose**: Identifies potential duplicate issues using similarity similarity.

**Parameters**:
- `organization`: String (required) - Organization identifier
- `project`: String (required) - Project identifier
- `title`: String (required) - Issue title to check
- `description`: String (required) - Issue description to check
- `threshold`: Float (optional, default=0.85) - Similarity threshold for considering issues as duplicates
- `limit`: Integer (optional, default=5) - Maximum number of potential duplicates to return

**Returns**:
- List of potential duplicate issues
- Similarity score for each result
- Reasoning for why each issue might be a duplicate

### 3. `update_issue`

**Purpose**: Updates fields in existing issues across supported trackers.

**Parameters**:
- `organization`: String (required) - Organization identifier
- `project`: String (required) - Project identifier
- `issue_id`: String (required) - Issue identifier
- `title`: String (optional) - New issue title
- `description`: String (optional) - New issue description
- `status`: String (optional) - New issue status
- `priority`: String (optional) - New issue priority
- `labels`: List[String] (optional) - New issue labels/tags
- `assignee`: String (optional) - New assignee
- `custom_fields`: Dict (optional) - Tracker-specific custom fields

**Returns**:
- Updated issue object
- Change summary

### 4. `create_issue`

**Purpose**: Creates new issues with duplicate detection.

**Parameters**:
- `organization`: String (required) - Organization identifier
- `project`: String (required) - Project identifier
- `title`: String (required) - Issue title
- `description`: String (required) - Issue description
- `tracker`: String (optional) - Specific tracker to create issue in (defaults to project's primary tracker)
- `status`: String (optional) - Issue status
- `priority`: String (optional) - Issue priority
- `labels`: List[String] (optional) - Issue labels/tags
- `assignee`: String (optional) - Issue assignee
- `custom_fields`: Dict (optional) - Tracker-specific custom fields
- `check_duplicates`: Boolean (optional, default=true) - Whether to check for potential duplicates

**Returns**:
- Created issue object
- Duplicate warnings if any were found

### 5. `summarize_issues`

**Purpose**: Generates concise summaries of multiple issues.

**Parameters**:
- `organization`: String (required) - Organization identifier
- `project`: String (required) - Project identifier
- `issue_ids`: List[String] (required) - List of issue identifiers to summarize
- `format`: String (optional, default="paragraph") - Output format ("paragraph", "bullets", "table")
- `max_length`: Integer (optional, default=200) - Maximum length of each summary

**Returns**:
- Summary of each issue
- Combined summary of patterns and insights across all issues

### 6. `suggest_assignee`

**Purpose**: Recommends appropriate assignees based on expertise and workload.

**Parameters**:
- `organization`: String (required) - Organization identifier
- `project`: String (required) - Project identifier
- `issue_id`: String (required) - Issue identifier
- `limit`: Integer (optional, default=3) - Maximum number of suggestions to return
- `consider_workload`: Boolean (optional, default=true) - Whether to factor in current workload

**Returns**:
- List of suggested assignees
- Reasoning for each suggestion
- Expertise match score
- Current workload indicator

### 7. `estimate_issue`

**Purpose**: Provides time/effort estimates based on historical data.

**Parameters**:
- `organization`: String (required) - Organization identifier
- `project`: String (required) - Project identifier
- `issue_id`: String (required) - Issue identifier
- `confidence_level`: String (optional, default="medium") - Confidence level ("low", "medium", "high")

**Returns**:
- Estimated effort in hours or points
- Confidence interval
- Similar historical issues used for estimation
- Factors considered in the estimate

### 8. `prioritize_issues`

**Purpose**: Suggests priority levels based on impact analysis.

**Parameters**:
- `organization`: String (required) - Organization identifier
- `project`: String (required) - Project identifier
- `issue_ids`: List[String] (required) - List of issue identifiers to prioritize
- `factors`: List[String] (optional) - Specific factors to consider ("impact", "urgency", "effort", "dependencies")

**Returns**:
- Suggested priority level for each issue
- Reasoning for each priority assignment
- Relative ranking of issues

### 9. `issue_health_check`

**Purpose**: Analyzes issues for completeness and clarity.

**Parameters**:
- `organization`: String (required) - Organization identifier
- `project`: String (required) - Project identifier
- `issue_id`: String (required) - Issue identifier

**Returns**:
- Overall health score
- Specific improvement suggestions
- Missing information
- Clarity assessment

### 10. `sync_related_issues`

**Purpose**: Manages dependencies between issues across trackers.

**Parameters**:
- `organization`: String (required) - Organization identifier
- `project`: String (required) - Project identifier
- `issue_id`: String (required) - Issue identifier
- `relation_type`: String (required) - Type of relation ("blocks", "is-blocked-by", "relates-to", etc.)
- `related_issue_ids`: List[String] (required) - List of related issue identifiers

**Returns**:
- Status of each relationship update
- Summary of changes made

## Organization and Project Management Tools

### 11. `get_organization`

**Purpose**: Retrieves organization details and configuration.

**Parameters**:
- `organization`: String (required) - Organization identifier

**Returns**:
- Organization details including name, description, etc.
- List of projects within the organization
- Organization-wide settings

### 12. `create_organization`

**Purpose**: Creates a new organization in the system.

**Parameters**:
- `name`: String (required) - Organization name
- `identifier`: String (required) - Unique identifier for the organization
- `description`: String (optional) - Organization description
- `settings`: Dict (optional) - Organization-wide settings

**Returns**:
- Created organization object
- Access information

### 13. `update_organization`

**Purpose**: Updates organization details and settings.

**Parameters**:
- `organization`: String (required) - Organization identifier
- `name`: String (optional) - New organization name
- `description`: String (optional) - New organization description
- `settings`: Dict (optional) - Updated organization-wide settings

**Returns**:
- Updated organization object
- Change summary

### 14. `list_organizations`

**Purpose**: Lists all organizations accessible to the user.

**Parameters**:
- `limit`: Integer (optional, default=100) - Maximum number of organizations to return
- `offset`: Integer (optional, default=0) - Pagination offset

**Returns**:
- List of organization objects
- Pagination information

### 15. `get_project`

**Purpose**: Retrieves project details including issue tracker configuration.

**Parameters**:
- `organization`: String (required) - Organization identifier
- `project`: String (required) - Project identifier

**Returns**:
- Project details including name, description, etc.
- Issue tracker configuration
- Project statistics

### 16. `create_project`

**Purpose**: Creates a new project with issue tracker integration details.

**Parameters**:
- `organization`: String (required) - Organization identifier
- `name`: String (required) - Project name
- `identifier`: String (required) - Unique identifier for the project
- `description`: String (optional) - Project description
- `tracker_configurations`: List[Dict] (optional) - Issue tracker configurations
- `settings`: Dict (optional) - Project-specific settings

**Returns**:
- Created project object
- Setup status for each configured tracker

### 17. `update_project`

**Purpose**: Updates project settings including issue tracker credentials.

**Parameters**:
- `organization`: String (required) - Organization identifier
- `project`: String (required) - Project identifier
- `name`: String (optional) - New project name
- `description`: String (optional) - New project description
- `tracker_configurations`: List[Dict] (optional) - Updated issue tracker configurations
- `settings`: Dict (optional) - Updated project-specific settings

**Returns**:
- Updated project object
- Change summary

### 18. `list_projects`

**Purpose**: Lists all projects within an organization.

**Parameters**:
- `organization`: String (required) - Organization identifier
- `limit`: Integer (optional, default=100) - Maximum number of projects to return
- `offset`: Integer (optional, default=0) - Pagination offset

**Returns**:
- List of project objects
- Pagination information

### 19. `test_connection`

**Purpose**: Tests connectivity to configured issue trackers.

**Parameters**:
- `organization`: String (required) - Organization identifier
- `project`: String (required) - Project identifier
- `tracker`: String (optional) - Specific tracker to test (defaults to all configured for project)

**Returns**:
- Connection status for each tracker
- Detailed error information if connection fails
- API rate limit information

### 20. `sync_project_metadata`

**Purpose**: Synchronizes project metadata with the issue tracker.

**Parameters**:
- `organization`: String (required) - Organization identifier
- `project`: String (required) - Project identifier
- `tracker`: String (optional) - Specific tracker to sync with (defaults to all configured for project)
- `metadata_types`: List[String] (optional) - Specific metadata types to sync ("statuses", "priorities", "labels", etc.)

**Returns**:
- Synchronization status for each metadata type
- Summary of changes made
- Last sync timestamp
