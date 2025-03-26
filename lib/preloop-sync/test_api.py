#!/usr/bin/env python3
import json

import requests

API_KEY = "ayNItuvWTUyLf1fgGcSLRPOwr74QTJFKALwg9RgM"
BASE_URL = "http://localhost:8000/api/v1"  # API v1 path

headers = {"Authorization": f"Bearer {API_KEY}"}


def pretty_print(data):
    """Print JSON data in a readable format"""
    print(json.dumps(data, indent=2))


# Test health endpoint first
print("\n=== Health Check ===")
response = requests.get(f"{BASE_URL}/health", headers=headers)
print(f"Status: {response.status_code}")
try:
    print(response.json())
except Exception:
    print(f"Raw response: {response.text[:200]}")

# Test organizations endpoint
print("\n=== Organizations ===")
response = requests.get(f"{BASE_URL}/organizations", headers=headers)
print(f"Status: {response.status_code}")
try:
    orgs_response = response.json()
    # pretty_print(orgs_response)

    # Extract organizations from the response
    orgs = orgs_response.get("items", [])
    if orgs:
        print(f"Found {len(orgs)} organizations")

        # Look for the Spacecode organization
        org_id = None
        for org in orgs:
            if org.get("name") == "Spacecode":
                org_id = org.get("id")
                print(f"Found Spacecode organization with ID: {org_id}")
                break

        # If not found, use the first organization
        if not org_id:
            org_id = orgs[0].get("id")
            print(
                f"Spacecode organization not found, using: {orgs[0].get('name')} with ID: {org_id}"
            )

        # Find organization name for the selected ID
        org_name = next(
            (org.get("name") for org in orgs if org.get("id") == org_id), "Unknown"
        )

        # Test projects endpoint for this organization
        print(f"\n=== Projects for Organization {org_name} ===")
        response = requests.get(
            f"{BASE_URL}/organizations/{org_id}/projects", headers=headers
        )
        print(f"Status: {response.status_code}")
        projects_response = response.json()
        # pretty_print(projects_response)

        # Extract projects from the response
        projects = projects_response.get("items", [])
        if projects:
            print(f"Found {len(projects)} projects")

            # Search for projects with issues - try all of them
            print("\n=== Checking all projects for issues ===")
            for project in projects:
                project_id = project.get("id")
                project_name = project.get("name")

                # Try empty search to get all issues
                params = {
                    "organization": org_id,
                    "project": project_id,
                    "query": "",
                    "limit": 100,
                    "semantic": "false",  # Use string value for boolean
                }
                print(f"  Request URL: {BASE_URL}/issues/search with params: {params}")

                response = requests.get(
                    f"{BASE_URL}/issues/search", headers=headers, params=params
                )

                print(f"  Response: {response.status_code}")
                if response.status_code != 200:
                    print(f"  Error details: {response.text}")

                if response.status_code == 200:
                    search_results = response.json()
                    search_items = search_results.get("items", [])

                    if search_items:
                        print(
                            f"Found {len(search_items)} issues in project {project_name} (ID: {project_id})"
                        )
                        # Print first issue details
                        if len(search_items) > 0:
                            print(f"  First issue: {search_items[0].get('title')}")
                            print(f"  Status: {search_items[0].get('status')}")

                            # Test full text search with this project
                            search_terms = [
                                "Agent",
                                "Connector",
                                "update",
                                "instructions",
                                "prompt",
                                "investigate",
                            ]
                            print(
                                f"\n=== Testing search queries for project {project_name} ==="
                            )

                            for term in search_terms:
                                term_params = {
                                    "organization": org_id,
                                    "project": project_id,
                                    "query": term,
                                    "limit": 5,
                                    "semantic": "false",
                                }
                                response = requests.get(
                                    f"{BASE_URL}/issues/search",
                                    headers=headers,
                                    params=term_params,
                                )

                                if response.status_code == 200:
                                    term_results = response.json()
                                    term_items = term_results.get("items", [])
                                    if term_items:
                                        print(
                                            f"  Term '{term}': Found {len(term_items)} matches"
                                        )
                                        print(
                                            f"    First match: {term_items[0].get('title')}"
                                        )
                                    else:
                                        print(f"  Term '{term}': No matches")
                                else:
                                    print(
                                        f"  Term '{term}': Error {response.status_code}"
                                    )

                            # Get specific issue detail
                            issue_id = search_items[0].get("id")
                            print(f"\n=== Getting issue detail for {issue_id} ===")
                            response = requests.get(
                                f"{BASE_URL}/issues/{issue_id}", headers=headers
                            )
                            if response.status_code == 200:
                                issue_detail = response.json()
                                print(f"  Title: {issue_detail.get('title')}")
                                print(f"  Status: {issue_detail.get('status')}")
                                print(
                                    f"  Description: {issue_detail.get('description')[:100]}..."
                                )
                                print(f"  URL: {issue_detail.get('url')}")
                            else:
                                print(
                                    f"  Error getting issue detail: {response.status_code}"
                                )

                            # Don't need to check more projects once we find one with issues
                            break
                    else:
                        print(
                            f"No issues found in project {project_name} (ID: {project_id})"
                        )
                else:
                    print(
                        f"Error searching issues for project {project_name}: {response.status_code}"
                    )

            # Final test - try a cross-project search
            print("\n=== Cross-project search test ===")

            # Check for a project with UUID fd690dd8-a670-48c8-9ce6-b04f29b90a33 which we know has issues
            special_project_id = "fd690dd8-a670-48c8-9ce6-b04f29b90a33"
            print(f"Directly testing project with ID: {special_project_id}")

            cross_params = {
                "organization": org_id,
                "project": special_project_id,  # Special project ID from DB query
                "query": "",  # Empty query to get all
                "limit": 20,
                "semantic": "false",
            }

            response = requests.get(
                f"{BASE_URL}/issues/search", headers=headers, params=cross_params
            )

            if response.status_code == 200:
                all_results = response.json()
                all_items = all_results.get("items", [])
                print(f"Found {len(all_items)} issues across projects")
                if all_items:
                    for i, item in enumerate(all_items[:3]):
                        print(
                            f"  {i + 1}. {item.get('title')} (Project: {item.get('project')})"
                        )
            else:
                print(f"Error in cross-project search: {response.status_code}")

        else:
            print("No projects found for this organization")
    else:
        print("No organizations found")
except json.JSONDecodeError:
    print("Error parsing JSON response")
    print(f"Raw response: {response.text[:200]}")
except Exception as e:
    print(f"Error: {str(e)}")
    print(f"Raw response: {response.text[:200]}")
