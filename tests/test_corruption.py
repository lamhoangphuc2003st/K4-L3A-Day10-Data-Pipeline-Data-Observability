from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from core.utils import read_json
from ingestion import corruption
from ingestion.cleaning import build_clean_dataframe
from ingestion.crossref import load_raw_records
from observability.quality import run_data_quality_checks


@pytest.fixture
def clean(monkeypatch):
    run_date = datetime(2026, 9, 25, tzinfo=UTC)
    monkeypatch.setattr(corruption, "now_utc", lambda: run_date)
    root = Path(__file__).resolve().parents[1]
    return build_clean_dataframe(load_raw_records(root / "data/raw/crossref_records.json"), run_date)


def test_all_six_faults_and_audit(clean, tmp_path):
    original = clean.copy(deep=True)
    path = tmp_path / "results/corruption_log.json"
    result = corruption.corrupt_clean_dataframe(clean, path)
    pd.testing.assert_frame_equal(clean, original)
    log = read_json(path)
    actions = {action["action"]: action for action in log["actions"]}
    assert set(actions) == {"drop_latest_records", "blank_summary", "inject_text_noise",
                            "truncate_title", "stale_date", "duplicate_rows"}
    assert all(action["affected_rows"] == len(action["changes"]) > 0 for action in actions.values())
    dropped = {change["paper_id"] for change in actions["drop_latest_records"]["changes"]}
    latest = clean.sort_values("published", ascending=False).head(4)
    assert dropped == set(latest.paper_id)
    assert not dropped.intersection(result.paper_id)
    blanks = result[result.summary.eq("")]
    assert len(blanks) >= 4
    assert blanks.summary_chars.eq(0).all()
    assert blanks.text_for_embedding.str.contains("Summary: ").all()
    assert result.title.str.len().lt(10).sum() >= 4
    assert result.text_for_embedding.str.contains(corruption.NOISE, regex=False).sum() >= 4
    stale = result[result.published.eq("2021-09-25")]
    assert len(stale) / len(result) > 0.25
    assert stale.age_days.eq(1826).all()
    assert stale.text_for_embedding.str.contains("Published: 2021-09-25").all()
    assert result.paper_id.duplicated().sum() == 4
    assert log["input_rows"] == log["output_rows"] == len(result) == 24
    for change in actions["duplicate_rows"]["changes"]:
        assert result.iloc[change["output_row"]].paper_id == change["paper_id"]


def test_repeatable_with_duplicate_dataframe_index(clean, tmp_path):
    clean.index = [0] * len(clean)
    first = corruption.corrupt_clean_dataframe(clean, tmp_path / "one.json")
    second = corruption.corrupt_clean_dataframe(clean, tmp_path / "two.json")
    pd.testing.assert_frame_equal(first, second)
    assert read_json(tmp_path / "one.json") == read_json(tmp_path / "two.json")


def test_two_rows_retain_noise_and_all_faults(clean, tmp_path):
    result = corruption.corrupt_clean_dataframe(clean.head(2), tmp_path / "log.json")
    assert len(result) == 2
    assert result.summary.eq("").all()
    assert result.title.str.len().lt(10).all()
    assert result.age_days.gt(180).all()
    assert result.text_for_embedding.str.contains(corruption.NOISE, regex=False).all()
    assert result.paper_id.nunique() == 1


@pytest.mark.parametrize("count", [0, 1])
def test_too_few_rows_rejected(clean, tmp_path, count):
    with pytest.raises(ValueError, match="At least two"):
        corruption.corrupt_clean_dataframe(clean.head(count), tmp_path / "log.json")
    assert not (tmp_path / "log.json").exists()


def test_bad_input_rejected(clean, tmp_path):
    with pytest.raises(ValueError, match="Missing corruption columns"):
        corruption.corrupt_clean_dataframe(clean.drop(columns="summary"), tmp_path / "log.json")
    clean.loc[0, "published"] = "bad"
    with pytest.raises(ValueError, match="valid publication dates"):
        corruption.corrupt_clean_dataframe(clean, tmp_path / "log.json")


def test_quality_gate_detects_corruption(clean, tmp_path):
    settings = SimpleNamespace(freshness_threshold_days=180, paths=SimpleNamespace(quality_dir=tmp_path))
    result = corruption.corrupt_clean_dataframe(clean, tmp_path / "log.json")
    report = run_data_quality_checks(result, settings, "corrupted")
    assert not report["success"]
    assert not report["freshness"]["is_fresh"]
    assert report["statistics"]["unsuccessful_expectations"] >= 2
