#!/usr/bin/env python3
import requests
import json

API_KEY = "ayNItuvWTUyLf1fgGcSLRPOwr74QTJFKALwg9RgM"
BASE_URL = "http://localhost:8000/api/v1"  # API v1 path

headers = {"Authorization": f"Bearer {API_KEY}"}


def pretty_print(data):
    """Print JSON data in a readable format"""
    print(json.dumps(data, indent=2))


def test_search(org_id, project_id, query, limit=10, semantic=False):
    """Test search with given parameters"""
    print(f"\n=== Search Test: '{query}' ===")
    params = {
        "organization": org_id,
        "project": project_id,
        "query": query,
        "limit": limit,
        "semantic": "true" if semantic else "false",
    }

    response = requests.get(f"{BASE_URL}/issues/search", headers=headers, params=params)

    print(f"Status: {response.status_code}")

    if response.status_code == 200:
        results = response.json()
        items = results.get("items", [])
        print(f"Found {len(items)} results")

        if items:
            for i, item in enumerate(items[:3]):  # Show top 3 items
                print(f"{i + 1}. {item.get('title')} (Project: {item.get('project')})")

            return items
    else:
        print(f"Error: {response.text}")

    return []


# First get the organization
print("=== Getting Organizations ===")
response = requests.get(f"{BASE_URL}/organizations", headers=headers)
if response.status_code != 200:
    print(f"Error getting organizations: {response.status_code}")
    exit(1)

orgs = response.json().get("items", [])
spacecode_org = next((org for org in orgs if org.get("name") == "Spacecode"), None)

if not spacecode_org:
    print("Spacecode organization not found")
    exit(1)

org_id = spacecode_org.get("id")
print(f"Using organization: {spacecode_org.get('name')} ({org_id})")

# Use the special project ID we know has issues
project_id = "fd690dd8-a670-48c8-9ce6-b04f29b90a33"
print(f"Using special project ID: {project_id}")

# Test empty search to get all issues
all_issues = test_search(org_id, project_id, "", limit=100)
if not all_issues:
    print("No issues found in the database")
    exit(1)

print(f"\nTotal issues in database: {len(all_issues)}")
print("\nTesting various search terms...")

# Test various search terms
search_terms = [
    "Agent",
    "Connector",
    "update",
    "prompt",
    "instructions",
    "investigate",
    "padkeeper",
    "duplicate",
    "action",
    "point",
    "generation",
]

# Count how many terms get results
terms_with_results = 0

for term in search_terms:
    results = test_search(org_id, project_id, term)
    if results:
        terms_with_results += 1

print(
    f"\nSummary: {terms_with_results} out of {len(search_terms)} terms returned results"
)

# Also test semantic search
print("\n=== Testing Semantic Search ===")
semantic_results = test_search(
    org_id, project_id, "closing instructions", semantic=True
)
if semantic_results:
    print("Semantic search is working!")
else:
    print("Semantic search returned no results")

# Test getting specific issue details
if all_issues:
    issue_id = all_issues[0].get("id")
    print(f"\n=== Getting Issue Details for {issue_id} ===")
    response = requests.get(f"{BASE_URL}/issues/{issue_id}", headers=headers)

    if response.status_code == 200:
        issue = response.json()
        print(f"Title: {issue.get('title')}")
        print(f"Status: {issue.get('status')}")
        description = issue.get("description", "")[:100]
        print(f"Description: {description}...")
    else:
        print(f"Error: {response.status_code}")
