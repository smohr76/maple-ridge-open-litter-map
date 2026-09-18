import os
import requests

OLM_EMAIL = os.getenv("OLM_EMAIL")
OLM_PASSWORD = os.getenv("OLM_PASSWORD")

def run_diagnostics():
    if not OLM_EMAIL or not OLM_PASSWORD:
        print("Error: Missing credentials.")
        return

    # Step 1: Acquire Token
    auth_url = "https://openlittermap.com/api/auth/token"
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    auth_res = requests.post(auth_url, json={"email": OLM_EMAIL, "password": OLM_PASSWORD}, headers=headers)
    
    if auth_res.status_code not in (200, 201):
        print(f"Auth Failed: {auth_res.status_code} - {auth_res.text[:200]}")
        return

    token = auth_res.json().get("token")
    print(f"Token Acquired: {token[:10]}...")

    # Step 2: Probe Candidate Endpoints
    candidate_urls = [
        "https://openlittermap.com/api/v1/photos",
        "https://openlittermap.com/api/v1/user/photos",
        "https://openlittermap.com/api/v2/user/photos",
        "https://openlittermap.com/api/v3/user/photos",
        "https://openlittermap.com/api/v3/user/profile",
        "https://openlittermap.com/api/user"
    ]

    req_headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {token}",
        "User-Agent": "Mozilla/5.0 (ETL Diagnostic)"
    }

    for url in candidate_urls:
        print(f"\n--- Testing: {url} ---")
        try:
            res = requests.get(url, headers=req_headers, timeout=10)
            content_type = res.headers.get("Content-Type", "Unknown")
            print(f"Status: {res.status_code} | Content-Type: {content_type}")
            print(f"Body snippet (first 150 chars): {res.text[:150]}")
        except Exception as e:
            print(f"Error requesting {url}: {e}")

if __name__ == "__main__":
    run_diagnostics()
