"""Unit tests for the pure data-normalization helpers in sync_data.py."""

import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "scripts" / "sync_data.py"
SPEC = importlib.util.spec_from_file_location("sync_data", MODULE_PATH)
sync_data = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(sync_data)


def test_classify_tag_group_identifies_substances():
    assert sync_data.classify_tag_group(
        {"type": "custom_tag", "item": "cannabis"}
    ) == "substances"
    assert sync_data.classify_tag_group({"category": "smoking"}) == "substances"


def test_classify_tag_group_identifies_pet_waste():
    assert sync_data.classify_tag_group(
        {"category": "pets", "item": "dogshit_in_bag"}
    ) == "pet_waste"


def test_classify_tag_group_defaults_to_litter():
    assert sync_data.classify_tag_group(
        {"category": "single_use", "item": "cup"}
    ) == "litter"


def test_resolve_new_tags_format_normalizes_standard_and_extra_tags():
    result = sync_data.resolve_new_tags_format(
        {
            "category_litter_object_id": 10,
            "category": {"key": "pets"},
            "object": {"key": "dogshit"},
            "quantity": 2,
            "extra_tags": [
                {
                    "type": "custom_tag",
                    "tag": {"key": "local_note"},
                    "quantity": 1,
                }
            ],
        }
    )

    assert result == [
        {
            "type": "standard",
            "category": "pets",
            "item": "dogshit",
            "quantity": 2,
        },
        {
            "type": "custom_tag",
            "category": "custom_tag",
            "item": "local_note",
            "quantity": 1,
            "parent_category": "pets",
            "parent_item": "dogshit",
        },
    ]


def test_resolve_summary_format_resolves_lookup_keys():
    result = sync_data.resolve_summary_format(
        {
            "clo_id": 123,
            "category_id": 1,
            "object_id": 2,
            "quantity": 3,
            "materials": [4],
            "brands": [5],
            "custom_tags": [6],
        },
        {
            "categories": {"1": "smoking"},
            "objects": {"2": "cigarette"},
            "materials": {"4": "paper"},
            "brands": {"5": "example_brand"},
            "custom_tags": {"6": "cleanup"},
        },
    )

    assert result[0]["category"] == "smoking"
    assert result[0]["item"] == "cigarette"
    assert result[1]["item"] == "paper"
    assert result[2]["item"] == "example_brand"
    assert result[3]["item"] == "cleanup"
    assert all(tag["quantity"] == 3 for tag in result)


def test_build_photo_properties_sets_flattened_group_flags():
    properties = sync_data.build_photo_properties(
        {
            "id": 42,
            "datetime": "2026-09-18T12:00:00Z",
            "filename": "photo.jpg",
            "new_tags": [
                {
                    "category_litter_object_id": 1,
                    "category": {"key": "smoking"},
                    "object": {"key": "cigarette"},
                }
            ],
        }
    )

    assert properties["id"] == 42
    assert properties["datetime"] == "2026-09-18T12:00:00Z"
    assert properties["has_substances"] is True
    assert properties["has_litter"] is False
    assert properties["has_pet_waste"] is False


def test_validate_geojson_rejects_invalid_feature():
    invalid = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [999, 99]},
                "properties": {"id": 1},
            }
        ],
    }

    try:
        sync_data.validate_geojson(invalid)
        assert False, "Expected ValueError for invalid longitude"
    except ValueError:
        pass


def test_write_last_success_marker_creates_timestamp_file(tmp_path):
    marker = tmp_path / "last_success.txt"
    sync_data.write_last_success_marker(str(marker))
    assert marker.exists()
    assert marker.read_text(encoding="utf-8").strip()
