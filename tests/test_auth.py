import os
import sys
import requests

def run_auth_diagnostics():
    email = os.getenv("OLM_EMAIL")
    password = os.getenv("OLM_PASSWORD")

    print("=== STEP 1: Asserting Environment Variables ===")
    if not email or not password:
        print("FAIL: OLM_EMAIL or OLM_PASSWORD is missing in workflow environment.")
        sys.exit(1)
    print(f"SUCCESS: Environment variables detected for user: {email[:3]}***")

    # Array of API endpoint candidates based on OpenLitterMap route specs
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

    print("\n=== STEP 2: Testing Sanctum Auth Matrix ===")
    for url in endpoints:
        print(f"\nTarget Endpoint: {url}")
        payloads = [
            {"email": email, "password": password},
            {"identifier": email, "password": password}
        ]

        for i, payload in enumerate(payloads, 1):
            try:
                res = requests.post(url, json=payload, headers=headers, timeout=10)
                print(f"  [Payload {i}] Status: {res.status_code} | Content-Type: {res.headers.get('Content-Type')}")
                
                if res.status_code in (200, 201):
                    try:
                        data = res.json()
                        print(f"  SUCCESS! Response Keys: {list(data.keys())}")
                        return
                    except Exception:
                        print("  FAIL: Response returned status 200/201 but body was non-JSON.")
                else:
                    print(f"  Body Preview: {res.text[:120]}")
            except Exception as e:
                print(f"  Request Error: {e}")

    print("\nDIAGNOSTIC COMPLETE: No valid authentication route returned JSON.")
    sys.exit(1)

if __name__ == "__main__":
    run_auth_diagnostics()
