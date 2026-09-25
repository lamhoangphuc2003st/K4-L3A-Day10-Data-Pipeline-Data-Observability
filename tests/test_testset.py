import pandas as pd
import pytest

from core.utils import read_json, write_json
from evaluation.testset import build_test_set


def papers():
    return pd.DataFrame([
        {"paper_id": "10.1234/a", "title": "Retrieval Research", "summary": "The study evaluates retrieval accuracy.",
         "authors": ["An Nguyen", "Bo Le"], "categories": ["Information Retrieval"], "published": "2026-05-20"},
        {"paper_id": "10.1234/b", "title": "Database Research", "summary": "The study evaluates database reliability.",
         "authors": ["Chi Tran"], "categories": ["Data Systems"], "published": "2026-04-15"},
    ])


def test_all_types_are_grounded_and_serialized(tmp_path):
    df = papers()
    original = df.copy(deep=True)
    output = tmp_path / "eval/test_set.json"
    samples = build_test_set(df, output)
    assert read_json(output) == samples
    assert len(samples) == 9
    assert len({sample["id"] for sample in samples}) == len(samples)
    assert {sample["type"] for sample in samples} == {"summary", "authors", "date", "category", "multi_hop"}
    documents = df.set_index("paper_id").to_dict(orient="index")
    for sample in samples:
        assert {"id", "type", "question", "ground_truth", "ground_truth_doc_ids"} <= sample.keys()
        assert sample["question_type"] == sample["type"]
        assert sample["question"] and sample["ground_truth"]
        sources = [documents[doi] for doi in sample["ground_truth_doc_ids"]]
        kind = sample["type"]
        if kind == "multi_hop":
            assert len(sources) == 2
            assert all(source["summary"] in sample["ground_truth"] for source in sources)
            assert all(source["title"] in sample["question"] for source in sources)
        else:
            assert len(sources) == 1
            source = sources[0]
            expected = {"summary": source["summary"], "authors": ", ".join(source["authors"]),
                        "date": source["published"][:7], "category": ", ".join(source["categories"])}
            assert sample["ground_truth"] == expected[kind]
    pd.testing.assert_frame_equal(df, original)


def test_reproducible_order_and_duplicate_ids(tmp_path):
    df = papers()
    expected = build_test_set(df, tmp_path / "one.json")
    repeated = pd.concat([df.iloc[::-1], df.iloc[:1]], ignore_index=True)
    assert build_test_set(repeated, tmp_path / "two.json") == expected


@pytest.mark.parametrize("field,value", [("authors", []), ("summary", " "), ("published", "bad"), ("categories", [])])
def test_incomplete_metadata_is_not_used_to_invent_answers(tmp_path, field, value):
    df = papers()
    df.at[0, field] = value
    output = tmp_path / "test_set.json"
    write_json(output, [{"existing": True}])
    with pytest.raises(ValueError, match="At least two"):
        build_test_set(df, output)
    assert read_json(output) == [{"existing": True}]


def test_no_cross_disciplinary_pair(tmp_path):
    df = papers()
    df.at[1, "categories"] = df.at[0, "categories"]
    with pytest.raises(ValueError, match="distinct subject areas"):
        build_test_set(df, tmp_path / "test_set.json")


def test_missing_columns_and_empty_input(tmp_path):
    with pytest.raises(ValueError, match="Missing benchmark columns"):
        build_test_set(pd.DataFrame(), tmp_path / "test_set.json")
    with pytest.raises(ValueError, match="At least two"):
        build_test_set(papers().iloc[:0], tmp_path / "test_set.json")
