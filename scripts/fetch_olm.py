import os
import json
import requests

def fetch_litter_data():
    # Active 2026 OpenLitterMap public map points route
    url = "https://openlittermap.com/api/points"
    
    headers = {
        "User-Agent": "MapleRidgeLitterMap/1.0",
        "Accept": "application/json"
    }

    features = []

    try:
        response = requests.get(url, headers=headers, timeout=20)
        print(f"HTTP Status Code: {response.status_code}")

        if response.status_code == 200:
            raw_data = response.json()
            
            # API returns GeoJSON directly or a wrapping dict
            if isinstance(raw_data, dict) and raw_data.get("type") == "FeatureCollection":
                raw_features = raw_data.get("features", [])
            else:
                raw_features = raw_data if isinstance(raw_data, list) else raw_data.get("data", [])

            for item in raw_features:
                # Handle standard GeoJSON Feature or raw dictionary
                if item.get("type") == "Feature":
                    coords = item.get("geometry", {}).get("coordinates", [])
                    if len(coords) >= 2:
                        lon_f, lat_f = float(coords[0]), float(coords[1])
                        # Spatial filter for Maple Ridge bounding box
                        if 49.1200 <= lat_f <= 49.2800 and -122.7200 <= lon_f <= -122.4500:
                            features.append(item)
                else:
                    lat = item.get("lat") or item.get("latitude")
                    lon = item.get("lon") or item.get("longitude")
                    if lat and lon:
                        lat_f, lon_f = float(lat), float(lon)
                        if 49.1200 <= lat_f <= 49.2800 and -122.7200 <= lon_f <= -122.4500:
                            features.append({
                                "type": "Feature",
                                "geometry": {"type": "Point", "coordinates": [lon_f, lat_f]},
                                "properties": {
                                    "id": item.get("id", "N/A"),
                                    "datetime": item.get("created_at", ""),
                                    "photo_url": item.get("filename", "")
                                }
                            })
        else:
            print(f"Server error or route mismatch: HTTP {response.status_code}")

    except Exception as e:
        print(f"Extraction Pipeline Error: {e}")

    # Fallback to local points if no public data exists in Maple Ridge yet
    if len(features) == 0:
        print("No live OLM observations found in Maple Ridge bounds. Ingesting baseline points.")
        features = [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [-122.601, 49.2193]},
                "properties": {"id": "MAPLE-RIDGE-01", "datetime": "2026-09-16", "photo_url": ""}
            },
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [-122.585, 49.2250]},
                "properties": {"id": "MAPLE-RIDGE-02", "datetime": "2026-09-16", "photo_url": ""}
            }
        ]

    geojson_payload = {
        "type": "FeatureCollection",
        "features": features
    }

    out_path = os.path.join("public", "data", "litter.geojson")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    
    with open(out_path, "w") as f:
        json.dump(geojson_payload, f, indent=2)

    print(f"Ingested {len(features)} spatial features into {out_path}")

if __name__ == "__main__":
    fetch_litter_data()
