import os
import json
import requests

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
    
    # Process raw tags from either key format
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
            
        # Emit custom tags directly without creating a fake standard parent
        for custom_item in tag_entry.get("custom_tags", []):
            formatted_tags.append({
                "type": "custom_tag",
                "item": custom_item,
                "quantity": 1
            })

    # Derive unique groups list using exact classification rules
    groups = list({classify_tag_group(tag) for tag in formatted_tags})

    return {
        "id": photo.get("id"),
        "datetime": photo.get("datetime"),
        "filename": photo.get("filename"),
        "tags": formatted_tags,
        "groups": groups
    }

def fetch_and_build_geojson():
    # Adjust URL or API endpoint based on your OpenLitterMap setup
    url = os.environ.get("OLM_API_URL", "https://openlittermap.com/api/v1/user/photos")
    response = requests.get(url)
    response.raise_for_status()
    data = response.json()

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
    with open("data/litter.geojson", "w", encoding="utf-8") as f:
        json.dump(geojson, f, indent=2)

if __name__ == "__main__":
    fetch_and_build_geojson()
