import os
import requests

OLM_EMAIL = os.getenv("OLM_EMAIL")
OLM_PASSWORD = os.getenv("OLM_PASSWORD")

def debug_routes():
    if not OLM_EMAIL or not OLM_PASSWORD:
        print("FAIL: Missing OLM_EMAIL or OLM_PASSWORD secrets.")
        return

    # Auth Phase
    auth_url = "https://openlittermap.com/api/auth/token"
    auth_res = requests.post(
        auth_url, 
        json={"email": OLM_EMAIL, "password": OLM_PASSWORD},
        headers={"Content-Type": "application/json", "Accept": "application/json"}
    )
    
    if auth_res.status_code not in (200, 201):
        print(f"Auth failed: {auth_res.status_code} - {auth_res.text[:150]}")
        return

    token = auth_res.json().get("token")
    print(f"Token acquired successfully: {token[:8]}***")

    # Probe routes
    routes = [
        "https://openlittermap.com/api/v1/photos",
        "https://openlittermap.com/api/v1/user/photos",
        "https://openlittermap.com/api/v1/user",
        "https://openlittermap.com/api/v2/photos"
    ]

    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {token}",
        "User-Agent": "MapleRidgeETL-Debug/1.0"
    }

    for route in routes:
        print(f"\n--- Probing Route: {route} ---")
        try:
            res = requests.get(route, headers=headers, timeout=10)
            c_type = res.headers.get("Content-Type", "Unknown")
            print(f"Status: {res.status_code} | Content-Type: {c_type}")
            print(f"Body snippet: {res.text[:120]}")
        except Exception as err:
            print(f"Request failed: {err}")

if __name__ == "__main__":
    debug_routes()
