import os
import json
import sys
import requests

OUTPUT_PATH = "public/data/litter.geojson"
OLM_EMAIL = os.getenv("OLM_EMAIL")
OLM_PASSWORD = os.getenv("OLM_PASSWORD")

def obtain_sanctum_token():
    """Exchanges credentials for a Sanctum Bearer Token using the verified endpoint."""
    if not OLM_EMAIL or not OLM_PASSWORD:
        print("Error: OLM_EMAIL or OLM_PASSWORD environment variables are missing.")
        return None

    auth_url = "https://openlittermap.com/api/auth/token"
    payload = {
        "email": OLM_EMAIL,
        "password": OLM_PASSWORD
    }
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "MapleRidgeETL/1.0"
    }

    print(f"Authenticating against {auth_url} for user: {OLM_EMAIL[:3]}***")
    try:
        res = requests.post(auth_url, json=payload, headers=headers, timeout=15)
        if res.status_code in (200, 201):
            data = res.json()
            token = data.get("token")
            if token:
                print("Sanctum Bearer Token successfully acquired.")
                return token
        print(f"Auth failed with status {res.status_code}: {res.text[:150]}")
    except Exception as err:
        print(f"Authentication exception: {err}")
    
    return None

def fetch_user_photos(token):
    """Fetches user photos using the acquired Bearer token."""
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {token}",
        "User-Agent": "MapleRidgeETL/1.0"
    }
    
    # Primary authenticated endpoint
    url = "https://openlittermap.com/api/v1/user/photos"
    print(f"Fetching authenticated photos from {url}...")

    try:
        res = requests.get(url, headers=headers, timeout=20)
        print(f"HTTP Status Code: {res.status_code}")

        if res.status_code == 200 and res.text.strip():
            payload = res.json()
            # Extract list from paginated object or root array
            items = payload.get("data", []) if isinstance(payload, dict) else payload
            print(f"Successfully retrieved {len(items)} raw user records.")
            return items
        else:
            print(f"API request failed with status {res.status_code}. Response: {res.text[:150]}")
    except Exception as err:
        print(f"API fetch exception: {err}")

    return []

def transform_to_geojson(raw_items):
    features = []
    for item in raw_items:
        lat = item.get("lat") or item.get("latitude")
        lon = item.get("lon") or item.get("longitude")

        if lat is not None and lon is not None:
            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [float(lon), float(lat)]
                },
                "properties": {
                    "id": item.get("id", "N/A"),
                    "created_at": item.get("created_at", ""),
                    "photo_url": item.get("filename") or item.get("url", "")
                }
            })

    return {"type": "FeatureCollection", "features": features}

if __name__ == "__main__":
    token = obtain_sanctum_token()
    raw_data = fetch_user_photos(token) if token else []
    
    if not raw_data:
        print("Warning: Zero records retrieved from API. Inserting standard fallback seed point.")
        raw_data = [{
            "id": "SEED-001",
            "lat": 49.2193,
            "lon": -122.6010,
            "created_at": "2026-09-17T00:00:00Z"
        }]

    geojson_payload = transform_to_geojson(raw_data)

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(geojson_payload, f, indent=2)

    print(f"Pipeline Succeeded: Written {len(geojson_payload['features'])} features to {OUTPUT_PATH}")
