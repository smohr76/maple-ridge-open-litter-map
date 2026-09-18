import os
import sys
import requests

def test_credentials_and_endpoints():
    email = os.getenv("OLM_EMAIL")
    password = os.getenv("OLM_PASSWORD")

    print("=== TEST 1: Environment Variable Assertion ===")
    if not email or not password:
        print("FAIL: OLM_EMAIL or OLM_PASSWORD is not set in the environment.")
        sys.exit(1)
    print(f"SUCCESS: Found credentials for email: {email[:3]}***@***")

    # Potential Sanctum endpoint variants used by OpenLitterMap backend
    endpoints = [
        "https://openlittermap.com/api/auth/token",
        "https://openlittermap.com/api/v1/auth/token",
        "https://openlittermap.com/api/v1/login"
    ]

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "MapleRidgeETL-Test/1.0"
    }

    print("\n=== TEST 2: Endpoint Reachability & Auth Variant Matrix ===")
    for url in endpoints:
        print(f"\nTesting Route: {url}")
        
        # Test standard payload signatures
        payloads = [
            {"email": email, "password": password},
            {"identifier": email, "password": password}
        ]

        for idx, payload in enumerate(payloads, start=1):
            try:
                res = requests.post(url, json=payload, headers=headers, timeout=10)
                print(f"  [Payload Schema {idx}] Status: {res.status_code}")
                print(f"  [Payload Schema {idx}] Content-Type: {res.headers.get('Content-Type')}")
                
                # Check for valid JSON response
                if res.status_code in (200, 201):
                    try:
                        data = res.json()
                        print(f"  SUCCESS: Received valid JSON response keys: {list(data.keys())}")
                        return url, payload, data
                    except Exception:
                        print("  FAIL: Status 200/201 returned non-JSON text.")
                else:
                    print(f"  Response Body Preview: {res.text[:150]}")
            except Exception as e:
                print(f"  ERROR hitting endpoint: {e}")

    print("\nCONCLUSION: All authentication variants failed.")
    return None, None, None

if __name__ == "__main__":
    test_credentials_and_endpoints()
