import os
import json
import requests

# Retrieve the API token securely from environment variables
OLM_TOKEN = os.getenv("OLM_API_TOKEN")
OUTPUT_PATH = "public/data/litter.geojson"

headers = {
    "Accept": "application/json"
}

# Add Bearer Token if configured in secrets
if OLM_TOKEN:
    headers["Authorization"] = f"Bearer {OLM_TOKEN}"

# Endpoint: GET /api/v3/user/photos
url = "https://openlittermap.com/api/v3/user/photos?per_page=100"

try:
    response = requests.get(url, headers=headers, timeout=15)
    response.raise_for_status()
    data = response.json()
except Exception as e:
    print(f"Error fetching data from OpenLitterMap API: {e}")
    data = {}

features = []

# Parse API response array into a standard GeoJSON FeatureCollection
items = data.get("data", []) if isinstance(data, dict) else []

for item in items:
    lat = item.get("lat")
    lon = item.get("lon")
    
    if lat is not None and lon is not None:
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [float(lon), float(lat)]
            },
            "properties": {
                "id": item.get("id"),
                "datetime": item.get("created_at"),
                "picked_up": item.get("picked_up", True),
                "photo_url": item.get("filename"),  # Direct CDN image URL
                "tags": item.get("new_tags", [])
            }
        })

geojson_payload = {
    "type": "FeatureCollection",
    "features": features
}

# Ensure destination directory exists and write output payload
os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
    json.dump(geojson_payload, f, indent=2)

print(f"Successfully serialized {len(features)} spatial features to {OUTPUT_PATH}")
