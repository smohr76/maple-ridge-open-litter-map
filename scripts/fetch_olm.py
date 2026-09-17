import os
import json
import requests

# Bounding Box for Maple Ridge, BC
MAPLE_RIDGE_BOUNDS = {
    "min_lat": 49.1800,
    "max_lat": 49.2800,
    "min_lon": -122.6800,
    "max_lon": -122.4500
}

OUTPUT_PATH = "public/data/litter.geojson"
OLM_EMAIL = os.getenv("OLM_EMAIL")
OLM_PASSWORD = os.getenv("OLM_PASSWORD")

def fetch_data():
    headers = {"Accept": "application/json"}
    
    # 1. Attempt Private User Query via Sanctum Auth
    if OLM_EMAIL and OLM_PASSWORD:
        token_res = requests.post(
            "https://openlittermap.com/api/auth/token",
            json={"email": OLM_EMAIL, "password": OLM_PASSWORD, "device_name": "ETL_Pipeline"},
            headers=headers,
            timeout=15
        )
        if token_res.status_code == 200:
            token = token_res.json().get("token")
            auth_headers = {**headers, "Authorization": f"Bearer {token}"}
            res = requests.get("https://openlittermap.com/api/v1/user/photos", headers=auth_headers, timeout=15)
            if res.status_code == 200:
                print("Successfully fetched private user dataset.")
                return res.json()

    # 2. Fallback to Public Spatial Query with Bounding Box
    print("Executing public spatial query with Maple Ridge bounding box...")
    res = requests.get("https://openlittermap.com/api/v1/photos", params=MAPLE_RIDGE_BOUNDS, headers=headers, timeout=15)
    
    if res.status_code != 200:
        raise RuntimeError(f"OpenLitterMap API returned HTTP {res.status_code}: {res.text}")
        
    return res.json()

def transform_to_geojson(raw_data):
    features = []
    items = raw_data if isinstance(raw_data, list) else raw_data.get("data", [])
    
    for item in items:
        lat = item.get("lat") or item.get("latitude")
        lon = item.get("lon") or item.get("longitude")
        if lat and lon:
            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [float(lon), float(lat)]
                },
                "properties": {
                    "id": item.get("id"),
                    "created_at": item.get("created_at"),
                    "photo_url": item.get("url") or item.get("filename"),
                    "tags": item.get("tags", [])
                }
            })
            
    return {"type": "FeatureCollection", "features": features}

if __name__ == "__main__":
    raw_payload = fetch_data()
    geojson_payload = transform_to_geojson(raw_payload)
    
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(geojson_payload, f, indent=2)
    print(f"Pipeline Succeeded: Processed {len(geojson_payload['features'])} features.")
