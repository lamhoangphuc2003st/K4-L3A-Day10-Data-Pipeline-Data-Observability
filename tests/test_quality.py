from types import SimpleNamespace

import pandas as pd
import pytest

from core.utils import read_json
from observability.quality import build_freshness_report, run_data_quality_checks


@pytest.fixture
def settings(tmp_path):
    return SimpleNamespace(freshness_threshold_days=180, paths=SimpleNamespace(quality_dir=tmp_path))


def papers(count=8):
    return pd.DataFrame({
        "paper_id": [f"10.1234/{i}" for i in range(count)],
        "title": ["A paper"] * count,
        "text_for_embedding": ["Title: A paper\nSummary: Research"] * count,
        "summary": ["a" * 30] * count,
        "published": ["2026-01-01"] * count,
        "age_days": [180] * count,
    })


def test_valid_data_uses_real_gx_and_writes_json(settings):
    frame = papers()
    original = frame.copy(deep=True)
    report = run_data_quality_checks(frame, settings, "baseline")
    assert report["success"]
    assert report["statistics"]["evaluated_expectations"] == 7
    assert report["freshness"]["is_fresh"]
    assert read_json(settings.paths.quality_dir / "baseline.json")["success"]
    pd.testing.assert_frame_equal(frame, original)


@pytest.mark.parametrize("column,value", [
    ("paper_id", None), ("paper_id", "10.1234/1"), ("title", " \t "),
    ("text_for_embedding", None), ("summary", "a" * 29), ("summary", None),
])
def test_bad_data_fails_expectations(settings, column, value):
    frame = papers()
    frame.loc[0, column] = value
    original = frame.copy(deep=True)
    report = run_data_quality_checks(frame, settings, "bad.json")
    assert not report["success"]
    assert report["statistics"]["unsuccessful_expectations"] >= 1
    pd.testing.assert_frame_equal(frame, original)


@pytest.mark.parametrize("count,success", [(0, False), (4, False), (5, True), (5000, True), (5001, False)])
def test_row_count_boundaries(settings, count, success):
    report = run_data_quality_checks(papers(count), settings, "volume")
    assert report["success"] is success


def test_missing_columns_fail_gate(settings):
    report = run_data_quality_checks(papers().drop(columns="title"), settings, "missing")
    assert not report["success"]
    assert report["missing_columns"] == ["title"]


@pytest.mark.parametrize("stale_rows,is_fresh", [(0, True), (2, True), (3, False)])
def test_freshness_boundary_and_dates(settings, stale_rows, is_fresh, caplog):
    frame = papers()
    frame.loc[frame.index[:stale_rows], "age_days"] = 181
    frame.loc[0, "published"] = "2025-01-01"
    path = settings.paths.quality_dir / "freshness.json"
    report = build_freshness_report(frame, settings, path)
    assert report["stale_rows"] == stale_rows
    assert report["stale_ratio"] == stale_rows / 8
    assert report["is_fresh"] is is_fresh
    assert report["oldest_published"] == "2025-01-01"
    assert report["latest_published"] == "2026-01-01"
    assert read_json(path) == report
    assert ("Update the corpus" in caplog.text) is (not is_fresh)


def test_staleness_warns_without_failing_mandatory_checks(settings):
    frame = papers()
    frame["age_days"] = 181
    report = run_data_quality_checks(frame, settings, "stale")
    assert report["success"]
    assert not report["freshness"]["is_fresh"]
    assert report["warnings"]


@pytest.mark.parametrize("frame", [papers(0), papers().drop(columns="age_days"), papers().assign(age_days="unknown")])
def test_unknown_freshness_is_not_reported_as_fresh(settings, frame):
    report = build_freshness_report(frame, settings, settings.paths.quality_dir / "unknown.json")
    assert not report["is_fresh"]
    assert report["warnings"]
