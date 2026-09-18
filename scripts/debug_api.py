import os
import requests

OLM_EMAIL = os.getenv("OLM_EMAIL")
OLM_PASSWORD = os.getenv("OLM_PASSWORD")

def run_diagnostics():
    if not OLM_EMAIL or not OLM_PASSWORD:
        print("CRITICAL: OLM_EMAIL or OLM_PASSWORD secrets are missing from runtime env.")
        return

    # Phase 1: Sanctum Token Exchange
    auth_url = "https://openlittermap.com/api/auth/token"
    auth_payload = {"email": OLM_EMAIL, "password": OLM_PASSWORD}
    auth_headers = {"Content-Type": "application/json", "Accept": "application/json"}
    
    print(f"Authenticating against: {auth_url}")
    auth_res = requests.post(auth_url, json=auth_payload, headers=auth_headers, timeout=15)
    
    if auth_res.status_code not in (200, 201):
        print(f"Auth Failure - Status: {auth_res.status_code} | Body: {auth_res.text[:150]}")
        return

    token = auth_res.json().get("token")
    print(f"Authentication Successful. Bearer Token: {token[:8]}***")

    # Phase 2: Endpoint Surface Probing
    candidate_urls = [
        "https://openlittermap.com/api/v1/photos",
        "https://openlittermap.com/api/v1/user",
        "https://openlittermap.com/api/v1/user/photos",
        "https://openlittermap.com/api/v1/public/photos?page=1"
    ]

    request_headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {token}",
        "User-Agent": "MapleRidgeETL-Diagnostic/1.0"
    }

    for url in candidate_urls:
        print(f"\n--- Testing Endpoint: {url} ---")
        try:
            res = requests.get(url, headers=request_headers, timeout=10)
            content_type = res.headers.get("Content-Type", "Unknown")
            print(f"HTTP Status: {res.status_code} | Content-Type: {content_type}")
            print(f"Body Preview (150 chars): {res.text[:150]}")
        except Exception as err:
            print(f"Network error probing {url}: {err}")

if __name__ == "__main__":
    run_diagnostics()
