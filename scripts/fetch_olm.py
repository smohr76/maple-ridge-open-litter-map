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
    category = str(tag.get("category") or "").lower()
    parent_category = str(tag.get("parent_category") or "").lower()
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


def _value_key(value, default="unclassified"):
    """Return a useful key from either an OLM object or a scalar value."""
    if isinstance(value, dict):
        return value.get("key") or value.get("name") or value.get("slug") or default
    return value if value not in (None, "") else default


def resolve_new_tags_format(tag_entry):
    """Normalize one new_tags entry without dropping entries lacking a CLO id.

    Some API responses contain a complete category/object pair but omit
    category_litter_object_id.  The old implementation treated those entries
    as empty, which made valid object points disappear during flattening.
    """
    if not isinstance(tag_entry, dict):
        return []

    formatted = []
    category = tag_entry.get("category") or {}
    obj = tag_entry.get("object") or tag_entry.get("item") or {}
    category_key = _value_key(category)
    object_key = _value_key(obj)

    has_standard_tag = (
        tag_entry.get("category_litter_object_id") is not None
        or tag_entry.get("category_id") is not None
        or tag_entry.get("object_id") is not None
        or tag_entry.get("category") is not None
        or tag_entry.get("object") is not None
        or tag_entry.get("item") is not None
    )
    if has_standard_tag:
        formatted.append({
            "type": "standard",
            "category": category_key,
            "item": object_key,
            "quantity": tag_entry.get("quantity", 1),
        })

    for extra in tag_entry.get("extra_tags") or []:
        if not isinstance(extra, dict):
            continue
        tag_info = extra.get("tag") or extra.get("object") or extra.get("item")
        formatted.append({
            "type": extra.get("type", "extra"),
            "category": extra.get("category") or extra.get("type", "extra"),
            "item": _value_key(tag_info),
            "quantity": extra.get("quantity", tag_entry.get("quantity", 1)),
            "parent_category": category_key,
            "parent_item": object_key,
        })
    return formatted


def resolve_summary_format(tag_entry, keys):
    """Normalize summary.tags[] while retaining entries with partial IDs."""
    if not isinstance(tag_entry, dict):
        return []

    formatted = []
    category_id = tag_entry.get("category_id")
    object_id = tag_entry.get("object_id")
    category_name = keys.get("categories", {}).get(str(category_id))
    object_name = keys.get("objects", {}).get(str(object_id))

    # clo_id is not consistently present; category/object IDs are sufficient
    # evidence that this is a real standard object.
    if (
        tag_entry.get("clo_id") is not None
        or category_id is not None
        or object_id is not None
    ):
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

    custom_tags = tag_entry.get("custom_tags") or []
    custom_ids = list(custom_tags.keys()) if isinstance(custom_tags, dict) else custom_tags
    for custom_id in custom_ids:
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

    if new_tags is not None:
        for entry in new_tags or []:
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
    """Fetches user photos using the Bearer token with explicit content negotiation."""
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
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
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [float(coords[0]), float(coords[1])]},
            "properties": properties
        })

    geojson = {"type": "FeatureCollection", "features": features}

    os.makedirs("data", exist_ok=True)
    out_path = "data/litter.geojson"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(geojson, f, indent=2)

    print(f"[SUCCESS] Successfully generated {out_path} with {len(features)} features.")


if __name__ == "__main__":
    fetch_and_build_geojson()
