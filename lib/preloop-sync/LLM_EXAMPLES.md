Examples for Windsurf, Claude and other LLMs

1. How to get only recently updated issues on Gitlab:
"""python
import gitlab
import datetime

# Connect to GitLab
# Use either personal access token or oauth token
gl = gitlab.Gitlab('https://gitlab.com', private_token='your_private_token')
# Or if you're using self-hosted GitLab
# gl = gitlab.Gitlab('https://gitlab.example.com', private_token='your_private_token')

# Authenticate
gl.auth()

# Define the timestamp (in ISO 8601 format)
# For example, issues updated after January 1, 2025
updated_after = '2025-01-01T00:00:00Z'

# Get all issues visible to the current user
# The 'all=True' parameter ensures pagination is handled automatically
issues = gl.issues.list(updated_after=updated_after, scope='all', state='all', all=True)

# Print the issues
for issue in issues:
    print(f"Issue #{issue.iid}: {issue.title}")
    print(f"  Updated at: {issue.updated_at}")
    print(f"  Project: {issue.references['full']}")
    print(f"  URL: {issue.web_url}")
    print("-" * 50)

# Optional: Count the total issues found
print(f"Total issues found: {len(list(issues))}")
"""

2. How to get only recently updated issues on GitHub:
"""python
from github import Github
import datetime

# Authenticate with GitHub
# You can use a personal access token
g = Github("your_personal_access_token")

# Define the timestamp (in ISO format)
# For example, issues updated after January 1, 2025
updated_after = "2025-01-01T00:00:00Z"

# Alternative: create timestamp from datetime object
# updated_after = datetime.datetime(2025, 1, 1).isoformat()

# Get all repositories the authenticated user has access to
# This includes user's repos, repos they contribute to, and organization repos they have access to
repos = g.get_user().get_repos()

# Loop through each repository and get issues updated after the timestamp
all_issues = []
for repo in repos:
    try:
        # Get all issues (including pull requests) updated after the timestamp
        # Note: In GitHub's API, issues include pull requests
        issues = repo.get_issues(state='all', since=datetime.datetime.fromisoformat(updated_after.replace('Z', '+00:00')))

        for issue in issues:
            # Check if the issue was updated after our timestamp
            # (since parameter filters by created_at, not updated_at)
            if issue.updated_at.isoformat() >= updated_after:
                all_issues.append({
                    'repo': repo.full_name,
                    'number': issue.number,
                    'title': issue.title,
                    'updated_at': issue.updated_at.isoformat(),
                    'url': issue.html_url,
                    'is_pull_request': hasattr(issue, 'pull_request') and issue.pull_request is not None
                })
    except Exception as e:
        print(f"Error accessing repo {repo.full_name}: {str(e)}")

# Print the issues
for issue in all_issues:
    print(f"Issue #{issue['number']}: {issue['title']}")
    print(f"  Updated at: {issue['updated_at']}")
    print(f"  Repository: {issue['repo']}")
    print(f"  URL: {issue['url']}")
    print(f"  Type: {'Pull Request' if issue['is_pull_request'] else 'Issue'}")
    print("-" * 50)

# Print the total count
print(f"Total issues and pull requests found: {len(all_issues)}")
"""

3. How to get only recently updated issues on Jira:
"""python
from jira import JIRA
import datetime

# Connect to Jira
# For Jira Cloud
jira = JIRA(
    server="https://your-domain.atlassian.net",
    basic_auth=("your-email@example.com", "your-api-token")  # Use API token, not password
)

# For Jira Server
# jira = JIRA(
#     server="https://jira.your-company.com",
#     basic_auth=("username", "password")
# )

# Define the timestamp (use Jira's JQL date format)
# For example, issues updated after January 1, 2025
updated_after = "2025-01-01 00:00"

# Create JQL query to find all issues updated after the timestamp
# This will find all issues the user can see across all projects
jql_query = f"updated >= '{updated_after}' ORDER BY updated DESC"

# Optional: Set the maximum results to retrieve (default is usually 50)
max_results = 1000

# Execute the query
# The maxResults parameter sets the batch size (up to 1000 per request)
# Using expand='changelog' will include change history (optional)
issues = jira.search_issues(jql_query, maxResults=max_results)

# Process and print the issues
print(f"Found {len(issues)} issues updated after {updated_after}")
for issue in issues:
    print(f"Issue {issue.key}: {issue.fields.summary}")
    print(f"  Updated at: {issue.fields.updated}")
    print(f"  Status: {issue.fields.status.name}")
    print(f"  Assignee: {issue.fields.assignee.displayName if issue.fields.assignee else 'Unassigned'}")
    print(f"  URL: {jira.server_url}/browse/{issue.key}")
    print("-" * 50)

# If there might be more issues than the max_results, implement pagination
# Jira will return up to maxResults issues per request

# Option 1: Using the startAt parameter for manual pagination
# total_issues = []
# start_at = 0
# while True:
#     batch = jira.search_issues(jql_query, startAt=start_at, maxResults=max_results)
#     total_issues.extend(batch)
#     if len(batch) < max_results:
#         break
#     start_at += len(batch)
#
# print(f"Total issues found with pagination: {len(total_issues)}")

# Option 2: Using the built-in pagination helper - this handles pagination automatically
# all_issues = jira.search_issues(jql_query, maxResults=False)  # Set maxResults=False to get all results
# print(f"Total issues found with automatic pagination: {len(all_issues)}")
"""
