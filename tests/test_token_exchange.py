import os
import sys
import requests
from test_auth import test_credentials_and_endpoints

def test_token_permissions():
    url, payload, auth_response = test_credentials_and_endpoints()

    if not auth_response:
        print("\nSkipping Token Scope Test: Authentication failed.")
        sys.exit(1)

    print("\n=== TEST 3: Token Exchange & Scope Assertion ===")
    token = auth_response.get("token") or auth_response.get("access_token")

    if not token:
        print("FAIL: Auth response JSON did not contain 'token' or 'access_token' key.")
        print(f"Full Response: {auth_response}")
        sys.exit(1)

    print(f"SUCCESS: Extracted Bearer Token (Length: {len(token)})")

    # Test token against authenticated user endpoints
    test_routes = [
        "https://openlittermap.com/api/v1/user/photos",
        "https://openlittermap.com/api/v1/user"
    ]

    auth_headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {token}",
        "User-Agent": "MapleRidgeETL-Test/1.0"
    }

    for route in test_routes:
        print(f"\nQuerying Protected Route: {route}")
        try:
            res = requests.get(route, headers=auth_headers, timeout=10)
            print(f"Status Code: {res.status_code}")
            if res.status_code == 200:
                print("SUCCESS: Protected route accessible!")
                print(f"Response Preview: {res.text[:200]}")
            else:
                print(f"FAIL: Status {res.status_code}. Body: {res.text[:150]}")
        except Exception as e:
            print(f"ERROR: {e}")

if __name__ == "__main__":
    test_token_permissions()
