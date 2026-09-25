from collections import Counter
from types import SimpleNamespace

import pytest

from core.utils import read_json, write_json
from evaluation import metrics


def samples():
    return [{"id": f"{kind}-{i}", "type": kind, "question_type": kind,
             "question": "Question?", "ground_truth": "Answer", "ground_truth_doc_ids": ["paper"]}
            for kind in ("summary", "authors", "date", "category", "multi_hop") for i in range(3)]


def test_balanced_subset(monkeypatch):
    monkeypatch.setenv("EVAL_MAX_SAMPLES", "10")
    original = samples()
    chosen = metrics._select_evaluation_samples(original)
    assert Counter(item["type"] for item in chosen) == dict.fromkeys(
        ["summary", "authors", "date", "category", "multi_hop"], 2)
    assert len({item["id"] for item in chosen}) == 10
    assert original == samples()


@pytest.mark.parametrize("limit", ["0", "100"])
def test_full_benchmark(monkeypatch, limit):
    monkeypatch.setenv("EVAL_MAX_SAMPLES", limit)
    assert metrics._select_evaluation_samples(samples()) == samples()


@pytest.mark.parametrize("limit", ["-1", "invalid"])
def test_bad_limit(monkeypatch, limit):
    monkeypatch.setenv("EVAL_MAX_SAMPLES", limit)
    with pytest.raises(ValueError, match="EVAL_MAX_SAMPLES"):
        metrics._select_evaluation_samples(samples())


def test_evaluation_limits_calls_and_prints_progress(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("EVAL_MAX_SAMPLES", "5")
    calls = []

    def answer(*args, **kwargs):
        calls.append(args)
        return SimpleNamespace(answer="Answer", retrieved_doc_ids=["paper"], retrieved_contexts=["Answer"])

    monkeypatch.setattr(metrics, "answer_question", answer)
    monkeypatch.setattr(metrics, "_judge_answer", lambda *args: metrics.JudgeVerdict(score=5, correct=True, reasoning="test"))
    monkeypatch.setattr(metrics, "_run_ragas", lambda *args: {"skipped": "test"})
    test_path, results_path, answers_path = [tmp_path / name for name in ("test.json", "metrics.json", "answers.json")]
    write_json(test_path, samples())
    bundle = metrics.evaluate_pipeline(None, None, test_path, results_path, answers_path)
    assert len(calls) == bundle.summary["samples"] == 5
    assert bundle.summary["total_test_samples"] == 15
    assert len(read_json(answers_path)) == 5
    assert read_json(test_path) == samples()
    assert "[eval 5/5] Completed." in capsys.readouterr().out
