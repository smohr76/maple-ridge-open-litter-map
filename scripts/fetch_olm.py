import os
import sys
import json
import requests

OLM_EMAIL = os.getenv("OLM_EMAIL")
OLM_PASSWORD = os.getenv("OLM_PASSWORD")
OUTPUT_PATH = "public/data/litter.geojson"

def fetch_and_build_geojson():
    if not OLM_EMAIL or not OLM_PASSWORD:
        print("CRITICAL ERROR: OLM_EMAIL or OLM_PASSWORD secrets missing.")
        sys.exit(1)

    # Step 1: Sanctum Token Negotiation
    auth_url = "https://openlittermap.com/api/auth/token"
    auth_headers = {"Content-Type": "application/json", "Accept": "application/json"}
    
    auth_res = requests.post(auth_url, json={"email": OLM_EMAIL, "password": OLM_PASSWORD}, headers=auth_headers, timeout=15)
    
    if auth_res.status_code not in (200, 201):
        print(f"CRITICAL ERROR: Auth failed: {auth_res.status_code} - {auth_res.text[:200]}")
        sys.exit(1)

    token = auth_res.json().get("token")
    if not token:
        print("CRITICAL ERROR: Sanctum token absent in response.")
        sys.exit(1)

    # Step 2: Paginated v3 User Photo Ingestion
    data_url = "https://openlittermap.com/api/v3/user/photos"
    req_headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {token}",
        "User-Agent": "MapleRidgeETL/1.0"
    }

    photos = []
    page = 1
    max_pages = 50

    while page <= max_pages:
        res = requests.get(data_url, headers=req_headers, params={"per_page": 100, "page": page}, timeout=20)

        if res.status_code != 200:
            print(f"CRITICAL ERROR: Endpoint returned status {res.status_code}")
            sys.exit(1)

        try:
            payload = res.json()
        except json.JSONDecodeError:
            print("CRITICAL ERROR: Failed to parse JSON response.")
            sys.exit(1)

        page_photos = payload.get("photos", [])
        if not isinstance(page_photos, list) or len(page_photos) == 0:
            break

        photos.extend(page_photos)

        pagination = payload.get("pagination", {})
        last_page = pagination.get("last_page")
        if last_page is not None and page >= int(last_page):
            break

        page += 1

    if len(photos) == 0:
        print("CRITICAL ERROR: Zero photos retrieved.")
        sys.exit(1)

    # Step 3: Map Spatial Records & Normalize Nested Tags
    features = []
    for photo in photos:
        lat = photo.get("lat")
        lon = photo.get("lon")

        if lat is None or lon is None:
            continue

        raw_tags = photo.get("new_tags") or []
        formatted_tags = []

        for tag in raw_tags:
            if not isinstance(tag, dict):
                continue

            category = tag.get("category") or {}
            litter_object = tag.get("object") or {}

            parent_tag = {
                "category": category.get("key") or category.get("name") or "unclassified",
                "item": litter_object.get("key") or litter_object.get("name") or "unclassified",
                "quantity": tag.get("quantity", 1),
                "picked_up": tag.get("picked_up", False),
                "type": "standard"
            }
            formatted_tags.append(parent_tag)

            child_tags = tag.get("extra_tags") or []
            for child in child_tags:
                if not isinstance(child, dict):
                    continue

                child_tag = child.get("tag") or {}

                formatted_tags.append({
                    "category": child.get("type") or "extra",
                    "item": (
                        child_tag.get("key")
                        or child_tag.get("name")
                        or child.get("key")
                        or child.get("name")
                        or "unclassified"
                    ),
                    "quantity": child.get("quantity", tag.get("quantity", 1)),
                    "picked_up": child.get("picked_up", tag.get("picked_up", False)),
                    "type": child.get("type") or "extra",
                    "parent_category": parent_tag["category"],
                    "parent_item": parent_tag["item"]
                })

        try:
            feature = {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [float(lon), float(lat)]
                },
                "properties": {
                    "id": photo.get("id"),
                    "datetime": photo.get("datetime"),
                    "filename": photo.get("filename"),
                    "summary": photo.get("summary", []),
                    "tags": formatted_tags
                }
            }
            features.append(feature)
        except (ValueError, TypeError) as err:
            print(f"WARNING: Skipping invalid feature ({lat}, {lon}): {err}")

    if len(features) == 0:
        print("CRITICAL ERROR: Zero valid GeoJSON features generated.")
        sys.exit(1)

    # Step 4: Construct GeoJSON Document and Write to Disk
    geojson_doc = {
        "type": "FeatureCollection",
        "features": features
    }

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(geojson_doc, f, indent=2, ensure_ascii=False)

    print(f"SUCCESS: Written {len(features)} spatial features to {OUTPUT_PATH}.")

if __name__ == "__main__":
    fetch_and_build_geojson()
