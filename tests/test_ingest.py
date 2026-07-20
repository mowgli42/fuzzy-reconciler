"""Ingest format sniffing + mapping tests."""

from fuzzy_reconciler.ingest import detect_mapping, ingest_rows, sniff_and_parse


def test_detect_mapping_aliases_and_regex():
    cols = ["POI_Name", "latitude", "longitude", "last_analyzed", "facility_type", "height_m"]
    mapping = detect_mapping(cols)
    assert mapping["name"] == "POI_Name"
    assert mapping["lat"] == "latitude"
    assert mapping["lon"] == "longitude"
    assert mapping["analyzed_at"] == "last_analyzed"
    assert mapping["category"] == "facility_type"


def test_sniff_csv_and_preview_limit():
    csv_text = "POI_Name,latitude,longitude,facility_type\nAlpha,28.1,-80.6,tower\nBeta,28.2,-80.7,sensor\n"
    rows, fmt = sniff_and_parse(csv_text, "sites.csv")
    assert fmt == "csv"
    assert len(rows) == 2
    preview = ingest_rows(rows, "A", source_format=fmt, source_filename="sites.csv")
    assert preview.row_count == 2
    assert preview.metrics.total_rows == 2
    assert preview.metrics.geo_valid == 2
    assert preview.detected_mapping["name"] == "POI_Name"
    assert len(preview.preview_rows) == 2


def test_sniff_jsonl():
    text = '{"name":"A","lat":1,"lon":2}\n{"name":"B","lat":3,"lon":4}\n'
    rows, fmt = sniff_and_parse(text, "x.jsonl")
    assert fmt == "jsonl"
    assert len(rows) == 2
