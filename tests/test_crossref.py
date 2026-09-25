from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
import requests

from core.utils import read_json, write_json
from ingestion.crossref import fetch_source_records, load_raw_records, parse_crossref_payload


ROOT = Path(__file__).resolve().parents[1]


def payload(**fields):
    return {"message": {"items": [{"DOI": "10.1234/example", "title": ["A paper"], **fields}]}}


def test_normalization():
    record, = parse_crossref_payload(payload(**{
        "DOI": " HTTPS://DX.DOI.ORG/10.1234/EXAMPLE ",
        "title": [" A\n  paper\t title "],
        "abstract": "<jats:p>A <jats:italic>test</jats:italic> &amp; result.</jats:p><jats:p>Next.</jats:p>",
        "author": [{"given": " An ", "family": " Nguyen "}, {"name": "Research Group"}, {}],
        "subject": [" Machine\n Learning ", ""],
        "published": {"date-parts": [[2026, 5, 20]]},
        "created": {"date-time": "2026-05-21T10:00:00Z"},
        "link": [{"content-type": "application/pdf", "URL": "https://example.org/paper.pdf"}],
    }))
    assert record.paper_id == "10.1234/example"
    assert record.title == "A paper title"
    assert record.summary == "A test & result. Next."
    assert record.authors == ["An Nguyen", "Research Group"]
    assert record.categories == ["Machine Learning"]
    assert record.primary_category == "Machine Learning"
    assert record.published == "2026-05-20"
    assert record.updated == "2026-05-21"
    assert record.pdf_url == "https://example.org/paper.pdf"


@pytest.mark.parametrize("parts,expected", [([2024], "2024-01-01"), ([2024, 2], "2024-02-01"), ([2024, 2, 29], "2024-02-29"), ([2025, 2, 29], ""), ([], "")])
def test_dates(parts, expected):
    record, = parse_crossref_payload(payload(published={"date-parts": [parts]}))
    assert record.published == expected


def test_invalid_items_and_missing_optional_fields():
    data = payload()
    data["message"]["items"].extend([None, {}, {"DOI": "bad", "title": ["Title"]}])
    record, = parse_crossref_payload(data)
    assert record.authors == record.categories == []
    assert record.summary == record.published == ""
    with pytest.raises(ValueError, match="message.items"):
        parse_crossref_payload({})


def test_bundled_snapshot_matches_records():
    records = parse_crossref_payload(read_json(ROOT / "data/raw/crossref_response.json"))
    assert len(records) == 24
    assert [asdict(record) for record in records] == read_json(ROOT / "data/raw/crossref_records.json")


@pytest.fixture
def settings(tmp_path):
    result = SimpleNamespace(
        refresh_source=True, source_query="test query", source_filter="has-abstract:true", max_results=24,
        paths=SimpleNamespace(raw_api_response=tmp_path / "response.json", raw_records_json=tmp_path / "records.json"),
    )
    write_json(result.paths.raw_api_response, payload())
    return result


def test_offline_does_not_call_api(settings):
    settings.refresh_source = False
    with patch("ingestion.crossref.requests.get") as get:
        records = fetch_source_records(settings)
    get.assert_not_called()
    assert load_raw_records(settings.paths.raw_records_json) == records


@pytest.mark.parametrize("failure", [requests.ConnectionError("offline"), requests.Timeout("timeout"), 429, 503])
def test_fallback_preserves_snapshot(settings, failure, caplog):
    before = settings.paths.raw_api_response.read_bytes()
    if isinstance(failure, int):
        response = requests.Response()
        response.status_code = failure
        failure = requests.HTTPError(response=response)
    with patch("ingestion.crossref.requests.get", side_effect=failure):
        records = fetch_source_records(settings)
    assert records[0].paper_id == "10.1234/example"
    assert settings.paths.raw_api_response.read_bytes() == before
    assert load_raw_records(settings.paths.raw_records_json) == records
    assert "offline snapshot" in caplog.text


def test_live_success(settings):
    response = Mock()
    response.json.return_value = payload(title=["New title"])
    with patch("ingestion.crossref.requests.get", return_value=response) as get:
        records = fetch_source_records(settings)
    assert get.call_args.kwargs["params"] == {"query": "test query", "filter": "has-abstract:true", "rows": 24}
    assert get.call_args.kwargs["timeout"] == (5, 20)
    assert records[0].title == "New title"
    assert read_json(settings.paths.raw_api_response) == response.json.return_value


def test_missing_snapshot_reports_cause(settings):
    settings.paths.raw_api_response.unlink()
    with patch("ingestion.crossref.requests.get", side_effect=requests.ConnectionError("offline")):
        with pytest.raises(RuntimeError, match="no offline snapshot"):
            fetch_source_records(settings)


def test_other_http_errors_propagate(settings):
    response = requests.Response()
    response.status_code = 400
    with patch("ingestion.crossref.requests.get", side_effect=requests.HTTPError(response=response)):
        with pytest.raises(requests.HTTPError):
            fetch_source_records(settings)
