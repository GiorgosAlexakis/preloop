#!/usr/bin/env python3

import requests

# Test JSON auth (new endpoint)
print("Testing JSON auth (new endpoint)...")
try:
    response = requests.post(
        "http://localhost:8000/api/v1/auth/token/json",
        json={"username": "admin", "password": "admin"},
    )
    print(f"Status code: {response.status_code}")
    print(f"Response: {response.text}")
except Exception as e:
    print(f"Error: {e}")

# Test form auth
print("\nTesting form auth...")
try:
    response = requests.post(
        "http://localhost:8000/api/v1/auth/token",
        data={"username": "admin", "password": "admin"},
    )
    print(f"Status code: {response.status_code}")
    print(f"Response: {response.text}")
except Exception as e:
    print(f"Error: {e}")

# Test with successful token
print("\nTesting protected endpoint...")
try:
    # Get token first
    auth_response = requests.post(
        "http://localhost:8000/api/v1/auth/token",
        data={"username": "admin", "password": "admin"},
    )
    if auth_response.status_code == 200:
        token_data = auth_response.json()
        access_token = token_data.get("access_token")

        # Use token to access protected endpoint
        response = requests.get(
            "http://localhost:8000/api/v1/organizations",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        print(f"Status code: {response.status_code}")
        print(f"Response: {response.text}")
    else:
        print(f"Failed to get token: {auth_response.text}")
except Exception as e:
    print(f"Error: {e}")
