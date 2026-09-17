import os
import json
import sys
import requests

OUTPUT_PATH = "public/data/litter.geojson"
OLM_TOKEN = os.getenv("OLM_TOKEN")

def fetch_litter_data():
    headers = {
        "Accept": "application/json",
        "User-Agent": "MapleRidgeETL/1.0"
    }
    
    if OLM_TOKEN:
        headers["Authorization"] = f"Bearer {OLM_TOKEN}"
        url = "https://openlittermap.com/api/v3/user/photos"
        print("Executing authenticated query against /api/v3/user/photos...")
    else:
        url = "https://openlittermap.com/api/v3/photos"
        print("OLM_TOKEN not found. Executing unauthenticated public query...")

    try:
        res = requests.get(url, headers=headers, timeout=20)
        print(f"HTTP Status: {res.status_code}")

        if res.status_code == 200 and res.text.strip():
            data = res.json()
            items = data if isinstance(data, list) else data.get("data", [])
            print(f"Retrieved {len(items)} raw records from API.")

            if len(items) > 0:
                return items
        else:
            print(f"API returned status {res.status_code}.")

    except Exception as err:
        print(f"Network/Parsing Exception: {err}")

    # Fallback placeholder if no API items are retrieved
    print("Zero features returned. Check OLM_TOKEN secret in GitHub settings.")
    return [
        {
            "id": "FALLBACK-001",
            "lat": 49.2193,
            "lon": -122.6010,
            "created_at": "2026-09-17T00:00:00Z"
        }
    ]

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
    raw_data = fetch_litter_data()
    geojson_data = transform_to_geojson(raw_data)

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(geojson_data, f, indent=2)

    print(f"Successfully serialized {len(geojson_data['features'])} features to {OUTPUT_PATH}")
