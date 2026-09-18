import os
import sys
import time
import json
import requests

def safe_fetch_json(url, headers=None, retries=1, delay=3):
    """
    Fetches data from a URL with HTTP status checks, non-empty body validation,
    and single retry capability on transient failures.
    """
    attempt = 0
    while attempt <= retries:
        try:
            response = requests.get(url, headers=headers, timeout=30)
            
            status_code = response.status_code
            raw_text = response.text.strip() if response.text else ""

            # Validate HTTP 200 and non-empty payload
            if status_code == 200 and raw_text:
                try:
                    return response.json()
                except json.JSONDecodeError as err:
                    print(f"[ERROR] Failed to parse JSON on attempt {attempt + 1}: {err}")
            
            # Log raw output sample for diagnostics
            print(f"[WARN] Request returned HTTP {status_code}. Raw response preview (first 200 chars):")
            print(raw_text[:200] if raw_text else "<EMPTY RESPONSE BODY>")

        except requests.RequestException as exc:
            print(f"[WARN] Network request failed on attempt {attempt + 1}: {exc}")

        attempt += 1
        if attempt <= retries:
            print(f"[INFO] Retrying request in {delay} seconds (Attempt {attempt + 1}/{retries + 1})...")
            time.sleep(delay)

    print(f"[CRITICAL ERROR] Failed to retrieve valid JSON from {url} after {retries + 1} attempts.")
    sys.exit(1)


def classify_tag_group(tag):  
    category = tag.get("category")  
    parent_category = tag.get("parent_category")  
    item = str(tag.get("item", "")).lower()  
    tag_type = tag.get("type")  
 
    if tag_type == "custom_tag" and any(kw in item for kw in ("thc", "cannabis", "weed")):  
        return "substances"  
    if category in ("smoking", "alcohol"):  
        return "substances"  
    if parent_category in ("smoking", "alcohol"):  
        return "substances"  
    if category == "pets" and item in ("dogshit", "dogshit_in_bag"):  
        return "pet_waste"  
    return "litter"


def build_photo_properties(photo):
    formatted_tags = []
    
    raw_tags = photo.get("new_tags") or photo.get("summary", {}).get("tags", [])
    
    for tag_entry in raw_tags:
        clo_id = tag_entry.get("clo_id")
        
        # Standalone custom tag fix: Only emit standard tag if clo_id exists
        if clo_id is not None:
            formatted_tags.append({
                "type": "standard",
                "category": tag_entry.get("category"),
                "parent_category": tag_entry.get("parent_category"),
                "item": tag_entry.get("item"),
                "quantity": tag_entry.get("quantity", 1)
            })
            
        for custom_item in tag_entry.get("custom_tags", []):
            formatted_tags.append({
                "type": "custom_tag",
                "item": custom_item,
                "quantity": 1
            })

    groups = list({classify_tag_group(tag) for tag in formatted_tags})

    return {
        "id": photo.get("id"),
        "datetime": photo.get("datetime"),
        "filename": photo.get("filename"),
        "tags": formatted_tags,
        "groups": groups
    }


def fetch_and_build_geojson():
    url = os.environ.get("OLM_API_URL", "https://openlittermap.com/api/v1/user/photos")
    token = os.environ.get("OLM_API_TOKEN")

    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    print(f"[INFO] Requesting OLM data from {url}...")
    data = safe_fetch_json(url, headers=headers, retries=1, delay=3)

    features = []
    photos = data.get("photos", []) if isinstance(data, dict) else data

    for photo in photos:
        coords = photo.get("geometry", {}).get("coordinates") or [photo.get("lon"), photo.get("lat")]
        if not coords or coords[0] is None or coords[1] is None:
            continue

        properties = build_photo_properties(photo)

        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [float(coords[0]), float(coords[1])]
            },
            "properties": properties
        }
        features.append(feature)

    geojson = {
        "type": "FeatureCollection",
        "features": features
    }

    os.makedirs("data", exist_ok=True)
    out_path = "data/litter.geojson"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(geojson, f, indent=2)

    print(f"[SUCCESS] Wrote {len(features)} features to {out_path}.")


if __name__ == "__main__":
    fetch_and_build_geojson()
