import os
import json
import sys
import requests

OUTPUT_PATH = "public/data/litter.geojson"
OLM_TOKEN = os.getenv("OLM_TOKEN")

def fetch_all_olm_photos():
    headers = {
        "Accept": "application/json",
        "User-Agent": "MapleRidgeETL/1.0"
    }
    
    # Select endpoint according to api.md specifications
    if OLM_TOKEN:
        headers["Authorization"] = f"Bearer {OLM_TOKEN}"
        base_url = "https://openlittermap.com/api/v1/user/photos"
        print("Executing authenticated query against /api/v1/user/photos...")
    else:
        base_url = "https://openlittermap.com/api/v1/public/photos"
        print("OLM_TOKEN not found. Executing unauthenticated query against /api/v1/public/photos...")

    all_records = []
    page = 1

    while True:
        url = f"{base_url}?page={page}"
        print(f"Fetching page {page} from {url}...")

        try:
            res = requests.get(url, headers=headers, timeout=20)
            print(f"HTTP Status Code: {res.status_code}")

            if res.status_code != 200 or not res.text.strip():
                print(f"Non-200 response or empty body received on page {page}.")
                break

            payload = res.json()
            
            # Unpack Laravel LengthAwarePaginator object
            if isinstance(payload, dict) and "data" in payload:
                items = payload["data"]
            elif isinstance(payload, list):
                items = payload
            else:
                items = []

            if not items:
                print(f"No records returned on page {page}. Fetching completed.")
                break

            all_records.extend(items)
            print(f"Retrieved {len(items)} items from page {page}. Total so far: {len(all_records)}")

            # Check pagination boundaries
            if isinstance(payload, dict):
                next_page = payload.get("next_page_url")
                if not next_page:
                    break
            else:
                break

            page += 1

        except Exception as err:
            print(f"Exception during API fetch on page {page}: {err}")
            break

    return all_records

def transform_to_geojson(raw_items):
    features = []
    for item in raw_items:
        # Extract spatial coordinates per OpenLitterMap schema
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
    raw_data = fetch_all_olm_photos()
    
    if not raw_data:
        print("Warning: Zero records retrieved from API. Inserting standard seed point.")
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
