from __future__ import annotations

from dataclasses import dataclass
import re

from core.config import Settings
from core.utils import first_sentence
from retrieval.index import LocalEmbeddingIndex, SearchResult


@dataclass(frozen=True)
class AnswerResult:
    question: str
    answer: str
    retrieved_doc_ids: list[str]
    retrieved_contexts: list[str]
    retrieved_titles: list[str]


def _extract_answer(question: str, top_result: SearchResult) -> str:
    lowered = question.lower()
    metadata = top_result.metadata
    if "who authored" in lowered or "list the authors" in lowered:
        return metadata["authors_joined"]
    if "when was" in lowered or "publication date" in lowered or "published on" in lowered:
        return metadata["published"]
    if "categories" in lowered or "subject categories" in lowered:
        return metadata["categories_joined"] or "No subject categories are listed by Crossref."
    return first_sentence(metadata["summary"])


def answer_question(question: str, settings: Settings, index: LocalEmbeddingIndex, top_k: int | None = None) -> AnswerResult:
    titles = re.findall(r"'([^']+)'", question)
    exact_matches = [match for title in titles if (match := index.lookup(title))]
    retrieved = index.search(question, top_k=top_k)
    exact_results = [SearchResult(
        paper_id=match["paper_id"], title=match["title"], score=1.0,
        content=match["content"], metadata=match["metadata"],
    ) for match in exact_matches]
    if exact_results:
        exact_ids = {item.paper_id for item in exact_results}
        retrieved = (exact_results + [item for item in retrieved if item.paper_id not in exact_ids])[: (top_k or settings.top_k)]
    if not retrieved:
        answer = "I don't know from the indexed corpus."
    elif "shared" in question.lower() and "research area" in question.lower() and len(exact_results) >= 2:
        categories = [set(item.metadata["categories_joined"].split(", ")) for item in exact_results[:2]]
        answer = ", ".join(sorted(categories[0] & categories[1])) or "No shared research area found."
    elif "both paper titles" in question.lower() and len(exact_results) >= 2:
        ignored = {"the", "and", "for", "with", "from", "into", "via", "using", "based", "this", "that"}
        words = [set(re.findall(r"[a-z0-9]+", item.title.lower())) - ignored for item in exact_results[:2]]
        shared_words = words[0] & words[1]
        answer = sorted(shared_words, key=lambda word: (-len(word), word))[0] if shared_words else "No shared title term found."
    else:
        answer = _extract_answer(question, retrieved[0])
    return AnswerResult(
        question=question,
        answer=answer,
        retrieved_doc_ids=[item.paper_id for item in retrieved],
        retrieved_contexts=[item.content for item in retrieved],
        retrieved_titles=[item.title for item in retrieved],
    )
