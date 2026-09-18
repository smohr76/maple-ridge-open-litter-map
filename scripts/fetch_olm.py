import os
import sys
import time
import json
import requests

LOGIN_URL = "https://openlittermap.com/api/auth/token"
PHOTOS_URL = "https://openlittermap.com/api/v1/user/photos"

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


def get_auth_token(email, password, retries=1, delay=3):
    """
    Authenticates against OLM API and retrieves a fresh Bearer token dynamically.
    """
    payload = {"email": email, "password": password}
    headers = {"Accept": "application/json"}
    attempt = 0

    while attempt <= retries:
        try:
            print(f"[INFO] Authenticating against OLM ({LOGIN_URL})...")
            response = requests.post(LOGIN_URL, json=payload, headers=headers, timeout=30)
            
            raw_text = response.text.strip() if response.text else ""
            print(f"[DEBUG Auth] HTTP Status: {response.status_code}")
            print(f"[DEBUG Auth] Content-Type: {response.headers.get('Content-Type')}")

            if response.status_code == 200 and raw_text:
                try:
                    data = response.json()
                    token = data.get("token") or data.get("access_token")
                    if token:
                        print("[SUCCESS] Successfully obtained OLM session token.")
                        return token
                    print(f"[ERROR] Auth response missing token key. Payload keys: {list(data.keys())}")
                except json.JSONDecodeError as decode_err:
                    print(f"[ERROR] Failed to parse auth JSON response: {decode_err}")
            
            print(f"[WARN] Auth attempt failed. Raw response preview: {raw_text[:300]!r}")

        except requests.RequestException as exc:
            print(f"[WARN] Auth connection error on attempt {attempt + 1}: {exc}")

        attempt += 1
        if attempt <= retries:
            print(f"[INFO] Retrying authentication in {delay}s...")
            time.sleep(delay)

    print("[CRITICAL ERROR] Failed to authenticate with provided OLM_EMAIL and OLM_PASSWORD.")
    sys.exit(1)


def fetch_photos(token, retries=1, delay=3):
    """
    Fetches user photos using the Bearer token with explicit content negotiation
    and isolated JSON parsing diagnostic logging.
    """
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json"  # Enforces Laravel API JSON payload routing
    }
    attempt = 0

    while attempt <= retries:
        try:
            print(f"[INFO] Fetching user photos from {PHOTOS_URL} (Attempt {attempt + 1}/{retries + 1})...")
            response = requests.get(PHOTOS_URL, headers=headers, timeout=30)
            
            raw_text = response.text.strip() if response.text else ""

            # Explicit diagnostic logging
            print(f"[DEBUG Photos] HTTP Status: {response.status_code}")
            print(f"[DEBUG Photos] Content-Type: {response.headers.get('Content-Type')}")
            print(f"[DEBUG Photos] Raw response preview (first 300 chars): {raw_text[:300]!r}")

            if response.status_code == 200 and raw_text:
                try:
                    return response.json()
                except json.JSONDecodeError as decode_err:
                    print(f"[ERROR] Response body is not valid JSON despite HTTP 200: {decode_err}")
            else:
                print(f"[WARN] Non-200 HTTP response received: {response.status_code}")

        except requests.RequestException as exc:
            if isinstance(exc, json.JSONDecodeError):
                print(f"[ERROR] JSON Decode Error caught under RequestException tree: {exc}")
            else:
                print(f"[WARN] Network connection failed on attempt {attempt + 1}: {exc}")

        attempt += 1
        if attempt <= retries:
            print(f"[INFO] Retrying data fetch in {delay}s...")
            time.sleep(delay)

    print("[CRITICAL ERROR] Failed to retrieve valid JSON photo data from OLM API.")
    sys.exit(1)


def build_photo_properties(photo):
    formatted_tags = []
    raw_tags = photo.get("new_tags") or photo.get("summary", {}).get("tags", [])
    
    for tag_entry in raw_tags:
        clo_id = tag_entry.get("clo_id")
        
        # Standalone custom tag fix: skip standard tag emission if clo_id is None
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

    # Deduplicate group categories
    groups = list({classify_tag_group(tag) for tag in formatted_tags})

    return {
        "id": photo.get("id"),
        "datetime": photo.get("datetime"),
        "filename": photo.get("filename"),
        "tags": formatted_tags,
        "groups": groups
    }


def fetch_and_build_geojson():
    email = os.environ.get("OLM_EMAIL", "").strip()
    password = os.environ.get("OLM_PASSWORD", "").strip()

    if not email or not password:
        print("[CRITICAL ERROR] OLM_EMAIL or OLM_PASSWORD environment variables are missing.")
        sys.exit(1)

    token = get_auth_token(email, password)
    data = fetch_photos(token)

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

    print(f"[SUCCESS] Successfully generated {out_path} with {len(features)} features.")


if __name__ == "__main__":
    fetch_and_build_geojson()
