import os
import sys
import time
import json
import tempfile
import requests

LOGIN_URL = "https://openlittermap.com/api/auth/token"
PHOTOS_URL = "https://openlittermap.com/api/v3/user/photos"

assert "v3" in PHOTOS_URL, "PHOTOS_URL must use the v3 endpoint — v1 was removed by OpenLitterMap"


def request_with_retry(method, url, *, max_retries=3, base_delay=1.0, **kwargs):
    """Retry transient HTTP failures with exponential backoff."""
    last_error = None

    for attempt in range(max_retries):
        try:
            response = requests.request(method, url, **kwargs)
            if response.status_code in (429, 500, 502, 503, 504):
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    print(f"[WARN] transient HTTP {response.status_code} from {url}; retrying in {delay}s")
                    time.sleep(delay)
                    continue
            return response
        except requests.RequestException as exc:
            last_error = exc
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)
                print(f"[WARN] request failure for {url}: {exc}; retrying in {delay}s")
                time.sleep(delay)
                continue

    if last_error is not None:
        raise last_error
    raise RuntimeError(f"Request to {url} failed after {max_retries} attempts")


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
        "has_substances": "substances" in groups,
    }


def get_auth_token(email, password, retries=2, delay=3):
    payload = {"email": email, "password": password}
    headers = {"Accept": "application/json"}

    for attempt in range(retries + 1):
        try:
            print(f"[INFO] Authenticating against OLM ({LOGIN_URL})...")
            response = request_with_retry(
                "POST",
                LOGIN_URL,
                json=payload,
                headers=headers,
                timeout=30,
                max_retries=3,
                base_delay=delay,
            )
            if response.status_code == 200:
                data = response.json()
                token = data.get("token") or data.get("access_token")
                if token:
                    print("[SUCCESS] Obtained session token.")
                    return token
        except requests.RequestException as exc:
            print(f"[WARN] Auth attempt {attempt + 1} failed: {exc}")
        time.sleep(delay)

    print("[CRITICAL ERROR] Failed to authenticate with OLM.")
    sys.exit(1)


def fetch_all_photos(token):
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }

    all_photos = []
    current_page = 1
    max_safety_pages = 200

    while current_page <= max_safety_pages:
        params = {"page": current_page}
        print(f"[INFO] Fetching page {current_page} from {PHOTOS_URL}...")

        try:
            response = request_with_retry(
                "GET",
                PHOTOS_URL,
                headers=headers,
                params=params,
                timeout=30,
                max_retries=3,
                base_delay=1.0,
            )
            if response.status_code != 200:
                print(f"[ERROR] HTTP {response.status_code} received on page {current_page}. Terminating fetch.")
                break

            data = response.json()

            if isinstance(data, dict):
                photos_page = data.get("photos") or data.get("data") or []
            elif isinstance(data, list):
                photos_page = data
            else:
                photos_page = []

            if not photos_page:
                print(f"[INFO] Page {current_page} returned 0 records. Reached end of dataset.")
                break

            all_photos.extend(photos_page)
            print(f"[INFO] Page {current_page}: fetched {len(photos_page)} photos (Cumulative total: {len(all_photos)}).")

            current_page += 1
            time.sleep(0.5)

        except requests.RequestException as exc:
            print(f"[ERROR] Network exception on page {current_page}: {exc}")
            break

    if current_page > max_safety_pages:
        print(f"[WARN] Circuit breaker triggered at max safety limit ({max_safety_pages} pages).")

    return all_photos


def validate_geojson(geojson):
    if not isinstance(geojson, dict):
        raise ValueError("GeoJSON payload must be a dictionary.")

    if geojson.get("type") != "FeatureCollection":
        raise ValueError("GeoJSON must have type 'FeatureCollection'.")

    features = geojson.get("features")
    if not isinstance(features, list):
        raise ValueError("GeoJSON 'features' key must be a list.")

    if not features:
        raise ValueError("GeoJSON contains no feature records; refusing to publish an empty dataset.")

    for index, feature in enumerate(features):
        if not isinstance(feature, dict):
            raise ValueError(f"Feature #{index} is not an object.")
        if feature.get("type") != "Feature":
            raise ValueError(f"Feature #{index} is missing type 'Feature'.")

        geometry = feature.get("geometry")
        if not isinstance(geometry, dict):
            raise ValueError(f"Feature #{index} geometry is missing.")
        if geometry.get("type") != "Point":
            raise ValueError(f"Feature #{index} geometry must be a Point.")

        coords = geometry.get("coordinates")
        if not isinstance(coords, (list, tuple)) or len(coords) != 2:
            raise ValueError(f"Feature #{index} coordinates must be a [lon, lat] pair.")

        try:
            lon = float(coords[0])
            lat = float(coords[1])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Feature #{index} coordinates are not numeric: {coords}") from exc

        if not (-180 <= lon <= 180):
            raise ValueError(f"Feature #{index} longitude out of range: {lon}")
        if not (-90 <= lat <= 90):
            raise ValueError(f"Feature #{index} latitude out of range: {lat}")

        properties = feature.get("properties") or {}
        if not isinstance(properties, dict):
            raise ValueError(f"Feature #{index} properties must be an object.")

    return True


def write_geojson_atomically(path, geojson):
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, exist_ok=True)

    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=directory,
        prefix=".tmp-",
        suffix=".json",
        delete=False,
    ) as temp_file:
        json.dump(geojson, temp_file, indent=2)
        temp_file.write("\n")
        temp_file.flush()
        os.fsync(temp_file.fileno())
        temp_path = temp_file.name

    os.replace(temp_path, path)
    print(f"[SUCCESS] Wrote GeoJSON atomically -> {path}")


def backup_existing_data(path):
    if not os.path.exists(path):
        return None
    with open(path, "rb") as original:
        return original.read()


def restore_backup(path, backup_bytes):
    if backup_bytes is None:
        return
    with open(path, "wb") as restored:
        restored.write(backup_bytes)
    print(f"[WARN] Restored previous valid dataset from backup: {path}")


def write_last_success_marker(path=".last_success.txt"):
    with open(path, "w", encoding="utf-8") as marker:
        marker.write(time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    print(f"[SUCCESS] Wrote last success marker -> {path}")


def fetch_and_build_geojson():
    email = os.environ.get("OLM_EMAIL", "").strip()
    password = os.environ.get("OLM_PASSWORD", "").strip()

    if not email or not password:
        print("[CRITICAL ERROR] Missing OLM_EMAIL or OLM_PASSWORD environment variables.")
        sys.exit(1)

    token = get_auth_token(email, password)
    raw_photos = fetch_all_photos(token)

    print(f"\n[DIAGNOSTIC] Total raw photo records fetched from API: {len(raw_photos)}")

    features = []
    for photo in raw_photos:
        coords = photo.get("geometry", {}).get("coordinates") or [photo.get("lon"), photo.get("lat")]
        if not coords or coords[0] is None or coords[1] is None:
            continue

        properties = build_photo_properties(photo)
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [float(coords[0]), float(coords[1])],
            },
            "properties": properties,
        })

    geojson = {
        "type": "FeatureCollection",
        "features": features,
    }

    print(f"[DIAGNOSTIC] Total valid georeferenced features compiled: {len(features)}")

    try:
        validate_geojson(geojson)
    except ValueError as exc:
        print(f"[CRITICAL ERROR] GeoJSON validation failed: {exc}")
        sys.exit(1)

    target_paths = ["data/litter.geojson", "public/data/litter.geojson"]

    for path in target_paths:
        backup = backup_existing_data(path)
        try:
            write_geojson_atomically(path, geojson)
        except Exception as exc:
            print(f"[CRITICAL ERROR] Failed to write GeoJSON to {path}: {exc}")
            restore_backup(path, backup)
            sys.exit(1)

    write_last_success_marker()


if __name__ == "__main__":
    fetch_and_build_geojson()

