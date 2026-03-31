from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Sequence


@dataclass(frozen=True)
class SymptomMatch:
    query_phrase: str
    matched_symptom: str
    similarity: float


class SymptomMatcher:
    def __init__(
        self,
        embed_texts: Callable[[Sequence[str]], list[list[float]]],
        symptom_inventory: Sequence[str],
        minimum_similarity: float = 0.60,
    ) -> None:
        self.embed_texts = embed_texts
        self.symptom_inventory = list(dict.fromkeys(symptom_inventory))
        self.minimum_similarity = minimum_similarity
        self.symptom_embeddings = self.embed_texts(self.symptom_inventory)

    def match(self, user_text: str, max_matches: int = 8) -> list[SymptomMatch]:
        candidate_phrases = _extract_candidate_phrases(user_text)
        if not candidate_phrases:
            candidate_phrases = [user_text.strip()]

        phrase_embeddings = self.embed_texts(candidate_phrases)
        matches: list[SymptomMatch] = []

        for phrase, embedding in zip(candidate_phrases, phrase_embeddings):
            best_symptom = ""
            best_similarity = -1.0
            for symptom, symptom_embedding in zip(self.symptom_inventory, self.symptom_embeddings):
                similarity = _dot_product(embedding, symptom_embedding)
                if similarity > best_similarity:
                    best_similarity = similarity
                    best_symptom = symptom

            required_similarity = _minimum_similarity_for_phrase(
                phrase,
                base_threshold=self.minimum_similarity,
            )
            if best_symptom and best_similarity >= required_similarity:
                matches.append(
                    SymptomMatch(
                        query_phrase=phrase,
                        matched_symptom=best_symptom,
                        similarity=round(best_similarity, 4),
                    )
                )

        deduplicated: list[SymptomMatch] = []
        seen_symptoms: set[str] = set()
        for match in sorted(matches, key=lambda item: item.similarity, reverse=True):
            symptom_key = match.matched_symptom.lower()
            if symptom_key in seen_symptoms:
                continue
            deduplicated.append(match)
            seen_symptoms.add(symptom_key)
            if len(deduplicated) >= max_matches:
                break

        return deduplicated


def _extract_candidate_phrases(text: str) -> list[str]:
    cleaned_text = text.strip().lower()
    if not cleaned_text:
        return []

    raw_parts = re.split(r",| and | with | along with | but |;|\.|\n", cleaned_text)
    split_phrases = [_clean_phrase(part) for part in raw_parts]

    candidate_phrases: list[str] = []
    non_empty_split_phrases = [phrase for phrase in split_phrases if phrase]
    if len(non_empty_split_phrases) <= 1:
        candidate_phrases.append(_clean_phrase(cleaned_text))
    candidate_phrases.extend(non_empty_split_phrases)

    unique_phrases: list[str] = []
    seen: set[str] = set()
    for phrase in candidate_phrases:
        if not phrase or phrase in seen:
            continue
        unique_phrases.append(phrase)
        seen.add(phrase)
    return unique_phrases


def _clean_phrase(text: str) -> str:
    cleaned = re.sub(
        r"\b(i have|i am having|i'm having|i feel|i am feeling|suffering from|have|having|got|experiencing|my|a|an|the)\b",
        " ",
        text,
    )
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .,;:-")
    return cleaned


def _minimum_similarity_for_phrase(phrase: str, base_threshold: float) -> float:
    token_count = len([token for token in phrase.split() if token])
    if token_count <= 1:
        return max(base_threshold, 0.78)
    return base_threshold


def _dot_product(left: Sequence[float], right: Sequence[float]) -> float:
    return sum(l * r for l, r in zip(left, right))
