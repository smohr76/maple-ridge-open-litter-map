import os
import json
import sys
import requests

# Geographic Bounding Box for City of Maple Ridge, BC
MAPLE_RIDGE_BOUNDS = {
    "min_lat": "49.1800",
    "max_lat": "49.2800",
    "min_lon": "-122.6800",
    "max_lon": "-122.4500"
}

OUTPUT_PATH = "public/data/litter.geojson"
OLM_EMAIL = os.getenv("OLM_EMAIL")
OLM_PASSWORD = os.getenv("OLM_PASSWORD")

def fetch_litter_data():
    headers = {"Accept": "application/json"}
    
    # Strategy 1: Private Ingestion using Sanctum Bearer Token
    if OLM_EMAIL and OLM_PASSWORD:
        print("Attempting Sanctum authentication for private user dataset...")
        auth_url = "https://openlittermap.com/api/auth/token"
        payload = {
            "email": OLM_EMAIL,
            "password": OLM_PASSWORD,
            "device_name": "GitHub_Actions_ETL"
        }
        
        try:
            auth_res = requests.post(auth_url, json=payload, headers=headers, timeout=15)
            if auth_res.status_code == 200:
                token = auth_res.json().get("token")
                user_headers = {**headers, "Authorization": f"Bearer {token}"}
                user_res = requests.get("https://openlittermap.com/api/v1/user/photos", headers=user_headers, timeout=15)
                if user_res.status_code == 200:
                    print("Successfully retrieved authenticated user data.")
                    return user_res.json()
                print(f"User endpoint returned HTTP {user_res.status_code}. Falling back to public bounds query...")
        except Exception as err:
            print(f"Authentication error: {err}. Falling back to public bounds query...")

    # Strategy 2: Public Spatial Bounding Box Query
    print("Executing public spatial query with Maple Ridge bounding box...")
    public_url = "https://openlittermap.com/api/v1/photos"
    res = requests.get(public_url, params=MAPLE_RIDGE_BOUNDS, headers=headers, timeout=15)
    
    print(f"HTTP Status Code: {res.status_code}")
    if res.status_code != 200:
        raise RuntimeError(f"OpenLitterMap API rejected request with HTTP {res.status_code}: {res.text}")
        
    return res.json()

def transform_to_geojson(raw_data):
    features = []
    items = raw_data if isinstance(raw_data, list) else raw_data.get("data", [])
    
    for item in items:
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
                    "id": item.get("id"),
                    "created_at": item.get("created_at"),
                    "photo_url": item.get("url") or item.get("filename"),
                    "tags": item.get("tags", []),
                    "jurisdiction": "City of Maple Ridge"
                }
            })
            
    return {"type": "FeatureCollection", "features": features}

if __name__ == "__main__":
    try:
        raw_payload = fetch_litter_data()
        geojson_payload = transform_to_geojson(raw_payload)
        
        os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
        with open(OUTPUT_PATH, "w") as f:
            json.dump(geojson_payload, f, indent=2)
            
        feature_count = len(geojson_payload["features"])
        print(f"ETL Pipeline Succeeded: Written {feature_count} spatial features to {OUTPUT_PATH}")
    except Exception as e:
        print(f"Pipeline Execution Error: {e}", file=sys.stderr)
        sys.exit(1)
