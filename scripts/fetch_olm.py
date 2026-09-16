import os
import json
import requests

def fetch_litter_data():
    # Public OpenLitterMap endpoint (No token required)
    url = "https://openlittermap.com/api/v1/photos"
    
    # Maple Ridge, BC bounding box constraints
    params = {
        "min_lat": 49.1200,
        "max_lat": 49.2800,
        "min_lon": -122.7200,
        "max_lon": -122.4500
    }

    headers = {"User-Agent": "MapleRidgeLitterMap/1.0"}

    try:
        res = requests.get(url, params=params, headers=headers, timeout=15)
        res.raise_for_status()
        raw_data = res.json()
    except Exception as e:
        print(f"API Request Error: {e}")
        raw_data = []

    items = raw_data if isinstance(raw_data, list) else raw_data.get("data", [])
    features = []

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
                    "id": item.get("id", "N/A"),
                    "datetime": item.get("created_at", ""),
                    "photo_url": item.get("url") or item.get("filename", "")
                }
            })

    geojson = {"type": "FeatureCollection", "features": features}

    out_path = os.path.join("public", "data", "litter.geojson")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(geojson, f, indent=2)

    print(f"Fetched {len(features)} points without authentication.")

if __name__ == "__main__":
    fetch_litter_data()
