from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock

import pandas as pd
import pytest

from core.config import load_settings
from core.utils import read_json, write_json
from pipelines import phase1


@pytest.fixture
def pipeline(tmp_path, monkeypatch):
    settings = replace(load_settings(tmp_path), refresh_source=False, refresh_test_set=False)
    monkeypatch.setattr(phase1, "load_settings", lambda: settings)
    frame = pd.DataFrame([{"paper_id": "10.1234/a", "title": "Paper"}])
    monkeypatch.setattr(phase1, "build_clean_dataframe", Mock(return_value=frame))
    fetch = Mock(return_value=["raw"])
    monkeypatch.setattr(phase1, "fetch_source_records", fetch)
    monkeypatch.setattr(phase1, "load_raw_records", Mock(return_value=["cached"]))
    quality = Mock(return_value={"success": True, "results": []})
    monkeypatch.setattr(phase1, "run_data_quality_checks", quality)
    monkeypatch.setattr(phase1, "build_freshness_report", Mock(return_value={"is_fresh": True}))
    samples = [{"ground_truth_doc_ids": ["10.1234/a"]}]

    def build_test_set(df, path):
        write_json(path, samples)
        return samples

    build = Mock(side_effect=build_test_set)
    monkeypatch.setattr(phase1, "build_test_set", build)
    index = Mock()
    index._build_documents.return_value = [{"content": "Paper"}]
    monkeypatch.setattr(phase1, "LocalEmbeddingIndex", index)
    evaluate = Mock(return_value=SimpleNamespace(summary={"samples": 1}, answers=[
        {"judge": {"reasoning": "Fallback heuristic judge used because the LLM evaluator was unavailable."}},
    ]))
    monkeypatch.setattr(phase1, "evaluate_pipeline", evaluate)
    return settings, fetch, quality, build, index, evaluate


def test_pipeline_writes_clean_data_and_report(pipeline):
    settings, fetch, quality, build, index, evaluate = pipeline
    phase1.main()
    fetch.assert_called_once()
    index.build.assert_called_once()
    evaluate.assert_called_once()
    assert read_json(settings.paths.clean_json)[0]["paper_id"] == "10.1234/a"
    assert settings.paths.clean_csv.exists()
    report = settings.paths.baseline_report.read_text(encoding="utf-8")
    assert "PASS" in report and "token-overlap fallback" in report


def test_quality_failure_stops_index_and_evaluation(pipeline):
    settings, fetch, quality, build, index, evaluate = pipeline
    quality.return_value = {"success": False}
    with pytest.raises(RuntimeError, match="Data quality gate failed"):
        phase1.main()
    build.assert_not_called()
    index.build.assert_not_called()
    evaluate.assert_not_called()


def test_reuse_raw_benchmark_and_matching_index(pipeline):
    settings, fetch, quality, build, index, evaluate = pipeline
    write_json(settings.paths.raw_records_json, [])
    write_json(settings.paths.eval_testset, [{"ground_truth_doc_ids": ["10.1234/a"]}])
    settings.paths.chroma_dir.mkdir(parents=True)
    write_json(settings.paths.embeddings_json, {
        "embedding_model": settings.embedding_model,
        "collection_name": settings.baseline_collection_name,
        "persist_path": str(settings.paths.chroma_dir),
        "documents": index._build_documents.return_value,
    })
    phase1.main()
    fetch.assert_not_called()
    build.assert_not_called()
    index.build.assert_not_called()
    index.load.assert_called_once_with(settings)


def test_benchmark_rebuilt_when_sources_missing(pipeline):
    settings, fetch, quality, build, index, evaluate = pipeline
    write_json(settings.paths.eval_testset, [{"ground_truth_doc_ids": ["missing"]}])
    phase1.main()
    build.assert_called_once()
