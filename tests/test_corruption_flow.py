from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pandas as pd
import pytest

from core.config import load_settings
from core.utils import read_json, write_json
from pipelines import corruption_flow as flow


def test_repair_and_repeated_flow_preserve_raw_and_isolate_collections(tmp_path, monkeypatch):
    settings = replace(load_settings(tmp_path), refresh_test_set=False)
    monkeypatch.setattr(flow, "load_settings", lambda: settings)
    original = Path(__file__).resolve().parents[1] / "data/raw/crossref_records.json"
    write_json(settings.paths.raw_records_json, read_json(original))
    raw_bytes = settings.paths.raw_records_json.read_bytes()
    index = Mock()
    monkeypatch.setattr(flow, "LocalEmbeddingIndex", index)

    def evaluate(settings, index, test_path, metrics_path, answers_path):
        samples = read_json(test_path)
        summary = {"samples": len(samples), "retrieval_hit_rate": 0.5, "mean_token_f1": 0.4,
                   "judge_accuracy": 0.3, "mean_judge_score": 2, "heuristic_judgments": len(samples)}
        return SimpleNamespace(summary=summary, answers=[{"id": item["id"]} for item in samples])

    monkeypatch.setattr(flow, "evaluate_pipeline", evaluate)
    flow.main()
    assert settings.paths.raw_records_json.read_bytes() == raw_bytes
    baseline = pd.read_json(settings.paths.clean_json)
    repaired = pd.read_json(settings.paths.repaired_clean_json)
    pd.testing.assert_frame_equal(baseline, repaired)
    assert not pd.read_json(settings.paths.corrupted_clean_json).equals(baseline)
    paths = [call.args[2] for call in index.build.call_args_list]
    assert paths == [settings.paths.embeddings_json, settings.paths.corrupted_embeddings_json, settings.paths.repaired_embeddings_json]
    first_repair = settings.paths.repaired_clean_json.read_bytes()
    flow.main()
    assert settings.paths.repaired_clean_json.read_bytes() == first_repair
    assert settings.paths.raw_records_json.read_bytes() == raw_bytes
    report = settings.paths.comparison_report.read_text(encoding="utf-8")
    assert "| Data Quality Gate | PASSED | FAILED | PASSED |" in report
    assert "VERIFIED" in report


def test_missing_raw_fails_before_build(tmp_path, monkeypatch):
    monkeypatch.setattr(flow, "load_settings", lambda: load_settings(tmp_path))
    with pytest.raises(FileNotFoundError, match="Raw records"):
        flow.main()
