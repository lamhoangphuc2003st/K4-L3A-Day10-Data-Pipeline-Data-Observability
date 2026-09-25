from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import requests

from core.config import load_settings
from ingestion.cleaning import build_clean_dataframe
from ingestion.crossref import fetch_source_records, parse_crossref_payload
from observability.quality import _freshness_payload, run_data_quality_checks


def test_snapshot_and_cleaning():
    settings = load_settings()
    payload = __import__("json").loads(settings.paths.raw_api_response.read_text(encoding="utf-8"))
    records = parse_crossref_payload(payload)
    assert len(records) == 24
    df = build_clean_dataframe(records + records[:1], datetime(2026, 9, 25, tzinfo=UTC))
    assert len(df) == 24
    assert df.paper_id.is_unique
    assert not df.summary.str.contains(r"<[^>]*>").any()
    assert df.iloc[0].text_for_embedding.startswith("Title: ")


def test_api_429_uses_offline_snapshot(tmp_path: Path):
    settings = load_settings()
    paths = replace(settings.paths, raw_records_json=tmp_path / "records.json")
    settings = replace(settings, refresh_source=True, paths=paths)
    response = requests.Response()
    response.status_code = 429
    response.url = "https://api.crossref.org/works"
    with patch("ingestion.crossref.requests.get", return_value=response), patch("ingestion.crossref.time.sleep"):
        records = fetch_source_records(settings)
    assert len(records) == 24
    assert paths.raw_records_json.exists()


def test_freshness_boundary_and_invalid_dates():
    settings = load_settings()
    run_date = datetime(2026, 9, 25, tzinfo=UTC)
    df = pd.DataFrame({"published": ["2026-03-28", "2026-09-24", "2026-09-24", "2026-09-24"]})
    assert _freshness_payload(df, settings, run_date)["is_fresh"]
    df.loc[1, "published"] = "2026-03-28"
    assert not _freshness_payload(df, settings, run_date)["is_fresh"]
    df.loc[1, "published"] = "invalid"
    report = _freshness_payload(df, settings, run_date)
    assert report["invalid_date_rows"] == 1
    assert not report["is_fresh"]


def test_quality_gate_rejects_duplicate_and_blank_summary(tmp_path: Path):
    settings = load_settings()
    payload = __import__("json").loads(settings.paths.raw_api_response.read_text(encoding="utf-8"))
    df = build_clean_dataframe(parse_crossref_payload(payload), datetime(2026, 9, 25, tzinfo=UTC))
    paths = replace(settings.paths, quality_dir=tmp_path)
    settings = replace(settings, paths=paths)
    assert run_data_quality_checks(df, settings, "clean")["success"]
    bad = df.copy()
    bad.loc[0, "summary"] = ""
    bad.loc[1, "paper_id"] = bad.loc[0, "paper_id"]
    report = run_data_quality_checks(bad, settings, "bad")
    assert not report["success"]
    assert (tmp_path / "bad_quality_report.json").exists()
