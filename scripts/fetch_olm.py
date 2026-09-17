import os
import json
import requests

OLM_EMAIL = os.getenv("OLM_EMAIL")
OLM_PASSWORD = os.getenv("OLM_PASSWORD")
OUTPUT_PATH = "public/data/litter.geojson"

def get_auth_token(email, password):
    auth_url = "https://openlittermap.com/api/auth/token"
    payload = {
        "email": email,
        "password": password,
        "device_name": "GitHub_Actions_ETL"
    }
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    
    response = requests.post(auth_url, json=payload, headers=headers, timeout=15)
    response.raise_for_status()
    return response.json().get("token")

def fetch_user_data(token):
    data_url = "https://openlittermap.com/api/v1/user/photos"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json"
    }
    
    response = requests.get(data_url, headers=headers, timeout=15)
    response.raise_for_status()
    return response.json()

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
                    "tags": item.get("tags", [])
                }
            })
            
    return {"type": "FeatureCollection", "features": features}

if __name__ == "__main__":
    if not OLM_EMAIL or not OLM_PASSWORD:
        raise ValueError("Missing OLM_EMAIL or OLM_PASSWORD environment variables.")
        
    token = get_auth_token(OLM_EMAIL, OLM_PASSWORD)
    user_photos = fetch_user_data(token)
    geojson_payload = transform_to_geojson(user_photos)
    
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(geojson_payload, f, indent=2)
