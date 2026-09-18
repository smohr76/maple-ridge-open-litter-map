import os
import sys
import json
import requests

OLM_EMAIL = os.getenv("OLM_EMAIL")
OLM_PASSWORD = os.getenv("OLM_PASSWORD")
OUTPUT_PATH = "public/data/litter.geojson"

def fetch_and_build_geojson():
    if not OLM_EMAIL or not OLM_PASSWORD:
        print("CRITICAL ERROR: OLM_EMAIL or OLM_PASSWORD secrets are missing from the runtime environment.")
        sys.exit(1)

    # Step 1: Negotiate Sanctum Token
    auth_url = "https://openlittermap.com/api/auth/token"
    auth_headers = {"Content-Type": "application/json", "Accept": "application/json"}
    
    print("Authenticating with OpenLitterMap API...")
    auth_res = requests.post(auth_url, json={"email": OLM_EMAIL, "password": OLM_PASSWORD}, headers=auth_headers, timeout=15)
    
    if auth_res.status_code not in (200, 201):
        print(f"CRITICAL ERROR: Authentication failed with status {auth_res.status_code}: {auth_res.text[:200]}")
        sys.exit(1)

    token = auth_res.json().get("token")
    if not token:
        print("CRITICAL ERROR: Sanctum authentication token not found in response payload.")
        sys.exit(1)

    print("Authentication successful.")

    # Step 2: Paginated Fetch from API v3 Endpoint
    data_url = "https://openlittermap.com/api/v3/user/photos"
    req_headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {token}",
        "User-Agent": "MapleRidgeETL/1.0"
    }

    photos = []
    page = 1
    max_pages = 50  # Hard safety cap (5,000 photos max) to prevent infinite loops

    while page <= max_pages:
        print(f"Requesting data from: {data_url} (page {page})")
        res = requests.get(data_url, headers=req_headers, params={"per_page": 100, "page": page}, timeout=20)

        if res.status_code != 200:
            print(f"CRITICAL ERROR: Data endpoint returned status {res.status_code}: {res.text[:200]}")
            sys.exit(1)

        try:
            payload = res.json()
        except json.JSONDecodeError:
            print(f"CRITICAL ERROR: Failed to parse response as JSON. Content-Type: {res.headers.get('Content-Type')}")
            sys.exit(1)

        page_photos = payload.get("photos", [])
        
        # Break immediately if page returns no records
        if not isinstance(page_photos, list) or len(page_photos) == 0:
            print(f"No additional items returned on page {page}. Concluding pagination.")
            break

        photos.extend(page_photos)

        # Pagination metadata evaluation
        pagination = payload.get("pagination", {})
        last_page = pagination.get("last_page")
        
        # Exit if last_page is explicitly specified and reached
        if last_page is not None and page >= int(last_page):
            print(f"Reached reported last_page ({last_page}). Concluding pagination.")
            break

        page += 1

    # Step 3: Validate Non-Empty Payload (Fail-Fast Rule)
    if len(photos) == 0:
        print("CRITICAL ERROR: Zero records retrieved from /api/v3/user/photos. Pipeline execution aborted.")
        sys.exit(1)

    print(f"Retrieved {len(photos)} total photo records from API across {page} request(s).")

    # Step 4: Map Spatial Records to RFC 7946 GeoJSON Features
    features = []
    for photo in photos:
        lat = photo.get("lat")
        lon = photo.get("lon")

        if lat is None or lon is None:
            continue

        # Extract nested OLM v3 tags
        raw_tags = photo.get("new_tags") or []
        formatted_tags = []

        for t in raw_tags:
            if not isinstance(t, dict):
                continue

            category_dict = t.get("category") or {}
            object_dict = t.get("object") or {}

            # Primary tag entry (handles standard items and loose tags)
            formatted_tags.append({
                "category": category_dict.get("key", "unclassified"),
                "item": object_dict.get("key", "unclassified"),
                "quantity": t.get("quantity", 1),
                "picked_up": t.get("picked_up", False),
                "type": "standard"
            })

            # Process extra_tags array (brands, materials, custom tags)
            extra_tags = t.get("extra_tags") or []
            for extra in extra_tags:
                if not isinstance(extra, dict):
                    continue
                
                tag_info = extra.get("tag") or {}
                tag_type = extra.get("type", "extra")
                
                formatted_tags.append({
                    "category": tag_type,
                    "item": tag_info.get("key", "unclassified"),
                    "quantity": extra.get("quantity", t.get("quantity", 1)),
                    "picked_up": t.get("picked_up", False),
                    "type": tag_type
                })

        try:
            feature = {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [float(lon), float(lat)]  # GeoJSON mandates [Longitude, Latitude]
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
            print(f"WARNING: Skipping invalid coordinate pair ({lat}, {lon}): {err}")

    # Step 5: Write Payload to Disk
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(geojson_doc, f, indent=2)

    print(f"SUCCESS: Successfully processed {len(features)} spatial features to {OUTPUT_PATH}.")

if __name__ == "__main__":
    fetch_and_build_geojson()
