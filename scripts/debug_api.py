import os
import requests

OLM_EMAIL = os.getenv("OLM_EMAIL")
OLM_PASSWORD = os.getenv("OLM_PASSWORD")

def run_diagnostics():
    if not OLM_EMAIL or not OLM_PASSWORD:
        print("ERROR: OLM_EMAIL or OLM_PASSWORD missing from secrets registry.")
        return

    # Step 1: Sanctum Token Exchange
    auth_url = "https://openlittermap.com/api/auth/token"
    auth_headers = {"Content-Type": "application/json", "Accept": "application/json"}
    
    auth_res = requests.post(auth_url, json={"email": OLM_EMAIL, "password": OLM_PASSWORD}, headers=auth_headers, timeout=15)
    
    if auth_res.status_code not in (200, 201):
        print(f"Auth Failed: {auth_res.status_code} - {auth_res.text[:150]}")
        return

    token = auth_res.json().get("token")
    print(f"Auth Succeeded. Bearer Token: {token[:8]}***")

    # Step 2: Probe Known OpenLitterMap Endpoints
    candidate_urls = [
        "https://openlittermap.com/api/v1/photos",
        "https://openlittermap.com/api/v1/user",
        "https://openlittermap.com/api/v1/user/stats",
        "https://openlittermap.com/api/v1/public/photos"
    ]

    req_headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {token}",
        "User-Agent": "MapleRidgeETL-Debug/1.0"
    }

    for url in candidate_urls:
        print(f"\n--- Testing Endpoint: {url} ---")
        try:
            res = requests.get(url, headers=req_headers, timeout=10)
            c_type = res.headers.get("Content-Type", "Unknown")
            print(f"HTTP Status: {res.status_code} | Content-Type: {c_type}")
            print(f"Body Preview (120 chars): {res.text[:120]}")
        except Exception as err:
            print(f"Request Exception: {err}")

if __name__ == "__main__":
    run_diagnostics()
