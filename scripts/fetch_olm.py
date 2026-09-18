import os
import sys
import time
import json
import requests

LOGIN_URL = "https://openlittermap.com/api/auth/token"
PHOTOS_URL = "https://openlittermap.com/api/v3/user/photos"

# Fail-fast endpoint assertion guard
assert "v3" in PHOTOS_URL, "PHOTOS_URL must use the v3 endpoint — v1 was removed by OpenLitterMap"


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


def resolve_new_tags_format(tag_entry):
    """Handles the documented 'new_tags' shape (nested category/object objects), if present."""
    formatted = []
    clo_id = tag_entry.get("category_litter_object_id")
    category = tag_entry.get("category") or {}
    obj = tag_entry.get("object") or {}

    if clo_id is not None:
        formatted.append({
            "type": "standard",
            "category": category.get("key", "unclassified"),
            "item": obj.get("key", "unclassified"),
            "quantity": tag_entry.get("quantity", 1),
        })

    for extra in tag_entry.get("extra_tags") or []:
        tag_info = extra.get("tag") or {}
        formatted.append({
            "type": extra.get("type", "extra"),
            "category": extra.get("type", "extra"),
            "item": tag_info.get("key", "unclassified"),
            "quantity": extra.get("quantity", tag_entry.get("quantity", 1)),
            "parent_category": category.get("key"),
            "parent_item": obj.get("key"),
        })
    return formatted


def resolve_summary_format(tag_entry, keys):
    """Handles the confirmed real shape: summary.tags[] with numeric IDs resolved via summary.keys."""
    formatted = []
    clo_id = tag_entry.get("clo_id")
    category_name = keys.get("categories", {}).get(str(tag_entry.get("category_id")))
    object_name = keys.get("objects", {}).get(str(tag_entry.get("object_id")))

    if clo_id is not None:
        formatted.append({
            "type": "standard",
            "category": category_name or "unclassified",
            "item": object_name or "unclassified",
            "quantity": tag_entry.get("quantity", 1),
        })

    for mat_id in tag_entry.get("materials") or []:
        formatted.append({
            "type": "material",
            "category": "material",
            "item": keys.get("materials", {}).get(str(mat_id), "unclassified"),
            "quantity": tag_entry.get("quantity", 1),
            "parent_category": category_name,
            "parent_item": object_name,
        })

    brands = tag_entry.get("brands")
    brand_ids = list(brands.keys()) if isinstance(brands, dict) else (brands or [])
    for brand_id in brand_ids:
        formatted.append({
            "type": "brand",
            "category": "brand",
            "item": keys.get("brands", {}).get(str(brand_id), "unclassified"),
            "quantity": tag_entry.get("quantity", 1),
            "parent_category": category_name,
            "parent_item": object_name,
        })

    for custom_id in tag_entry.get("custom_tags") or []:
        formatted.append({
            "type": "custom_tag",
            "category": "custom_tag",
            "item": keys.get("custom_tags", {}).get(str(custom_id), "unclassified"),
            "quantity": tag_entry.get("quantity", 1),
            "parent_category": category_name,
            "parent_item": object_name,
        })

    return formatted


def build_photo_properties(photo):
    formatted_tags = []
    new_tags = photo.get("new_tags")

    if new_tags:
        for entry in new_tags:
            formatted_tags.extend(resolve_new_tags_format(entry))
    else:
        summary = photo.get("summary") or {}
        keys = summary.get("keys", {})
        for entry in summary.get("tags", []):
            formatted_tags.extend(resolve_summary_format(entry, keys))

    groups = list({classify_tag_group(tag) for tag in formatted_tags}) or ["litter"]

    return {
        "id": photo.get("id"),
        "datetime": photo.get("datetime"),
        "filename": photo.get("filename"),
        "tags": formatted_tags,
        "groups": groups,
        "has_litter": "litter" in groups,
        "has_pet_waste": "pet_waste" in groups,
        "has_substances": "substances" in groups
    }


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
    Fetches user photos using the Bearer token with explicit content negotiation.
    """
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json"
    }
    attempt = 0

    while attempt <= retries:
        try:
            print(f"[INFO] Fetching user photos from {PHOTOS_URL} (Attempt {attempt + 1}/{retries + 1})...")
            response = requests.get(PHOTOS_URL, headers=headers, timeout=30)
            
            raw_text = response.text.strip() if response.text else ""

            print(f"[DEBUG Photos] HTTP Status: {response.status_code}")
            print(f"[DEBUG Photos] Content-Type: {response.headers.get('Content-Type')}")

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
