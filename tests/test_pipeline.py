from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

from core.config import load_settings
from evaluation.metrics import _token_f1
from ingestion.cleaning import build_clean_dataframe
from ingestion.corruption import corrupt_clean_dataframe
from ingestion.crossref import load_raw_records
from observability.quality import build_freshness_report, run_data_quality_checks
from retrieval.qa import answer_question


class PipelineCheck(unittest.TestCase):
    def test_clean_corrupt_repair_signals(self) -> None:
        settings = load_settings()
        records = load_raw_records(settings.paths.raw_records_json)
        run_date = datetime.now(timezone.utc)
        clean = build_clean_dataframe(records, run_date)
        self.assertEqual(24, len(clean))
        self.assertEqual(0, clean["paper_id"].duplicated().sum())
        self.assertEqual(
            (run_date.date() - datetime.fromisoformat(clean.iloc[0]["published"]).date()).days,
            clean.iloc[0]["age_days"],
        )
        with TemporaryDirectory() as folder:
            log_path = Path(folder) / "log.json"
            corrupted = corrupt_clean_dataframe(clean, log_path)
            self.assertEqual(6, len(json.loads(log_path.read_text())))
            self.assertEqual(24, len(clean))
            temp_settings = replace(settings, paths=replace(settings.paths, quality_dir=Path(folder)))
            self.assertFalse(run_data_quality_checks(corrupted, temp_settings, "test_corrupt")["success"])
            self.assertFalse(build_freshness_report(
                corrupted, settings, Path(folder) / "freshness.json"
            )["is_fresh"])
        repaired = build_clean_dataframe(records, run_date)
        self.assertTrue(clean.equals(repaired))

    def test_token_f1_counts_repeated_tokens(self) -> None:
        self.assertEqual(0.5, _token_f1("a a", "a b"))
        self.assertEqual(0.0, _token_f1("", "a"))

    def test_rag_answer_uses_retrieved_context(self) -> None:
        prompts = []
        llm = SimpleNamespace(invoke=lambda prompt: prompts.append(prompt)
                              or SimpleNamespace(content="The paper studies quality gates."))
        paper = SimpleNamespace(paper_id="doi-1", title="Quality Gates", score=0.9,
                                content="Title: Quality Gates\nSummary: The paper studies quality gates.")
        index = SimpleNamespace(search=lambda question: [paper])
        result = answer_question("Summarize Quality Gates", index, llm)
        self.assertEqual("The paper studies quality gates.", result.answer)
        self.assertIn("paper_id: doi-1", prompts[0])


if __name__ == "__main__":
    unittest.main()
