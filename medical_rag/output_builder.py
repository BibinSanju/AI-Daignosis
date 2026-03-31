from __future__ import annotations

import json
import re

from .data_ingestion import normalize_symptom_label
from .retrieval import RetrievedDocument

DEFAULT_MAX_SYMPTOM_WEIGHT = 7.0
CRITICAL_SYMPTOM_WEIGHT = 7.0
ELEVATED_SYMPTOM_WEIGHT = 6.0


def build_final_output(
    llm_response_text: str,
    user_symptoms: str,
    retrieved_documents: list[RetrievedDocument],
    normalized_query_symptoms: list[str] | None = None,
    symptom_weights: dict[str, float] | None = None,
) -> dict:
    parsed_payload = _safe_json_loads(llm_response_text)
    normalized_output = _normalize_llm_output(
        parsed_payload,
        user_symptoms,
        retrieved_documents,
        normalized_query_symptoms=normalized_query_symptoms,
    )

    top_candidate = normalized_output["possible_diseases"][0] if normalized_output["possible_diseases"] else None
    top_confidence = float(top_candidate["confidence"]) if top_candidate else 0.0
    retrieved_by_name = {
        document.disease.lower(): document for document in retrieved_documents
    }
    top_document = (
        retrieved_by_name.get(str(top_candidate["name"]).lower())
        if top_candidate
        else None
    )

    severity_score = compute_severity_score(
        matched_symptoms=top_candidate["matched_symptoms"] if top_candidate else [],
        top_confidence=top_confidence,
        top_document=top_document,
        symptom_weights=symptom_weights,
    )
    severity_level = severity_level_from_score(severity_score)

    normalized_output["severity_score"] = severity_score
    normalized_output["severity_level"] = severity_level
    normalized_output["recommended_action"] = recommended_action_from_level(severity_level)
    return normalized_output


def compute_severity_score(
    matched_symptoms: list[str],
    top_confidence: float,
    top_document: RetrievedDocument | None,
    symptom_weights: dict[str, float] | None = None,
) -> float:
    symptom_weights = symptom_weights or {}
    max_known_weight = max(symptom_weights.values(), default=DEFAULT_MAX_SYMPTOM_WEIGHT)
    matched_weights = [
        symptom_weights.get(normalize_symptom_label(symptom), 0.0)
        for symptom in matched_symptoms
    ]
    matched_weights = [weight for weight in matched_weights if weight > 0]

    symptom_risk = _symptom_risk_component(
        matched_weights=matched_weights,
        matched_symptom_count=len(matched_symptoms),
        max_known_weight=max_known_weight,
    )
    disease_weight_score = _safe_float(
        top_document.metadata.get("severity_score", 0.0) if top_document else 0.0
    )
    disease_risk = min(max(disease_weight_score / max_known_weight, 0.0), 1.0)
    disease_symptom_count = _safe_int(
        top_document.metadata.get("symptom_count", 0) if top_document else 0
    )
    coverage_component = (
        min(len(matched_symptoms) / disease_symptom_count, 1.0)
        if disease_symptom_count > 0
        else 0.0
    )
    retrieval_similarity = top_document.similarity if top_document else 0.0
    evidence_confidence = min(
        max((_clamp_confidence(top_confidence) + retrieval_similarity) / 2.0, 0.0),
        1.0,
    )

    score = (
        (0.65 * symptom_risk)
        + (0.10 * disease_risk)
        + (0.15 * coverage_component)
        + (0.05 * evidence_confidence)
    ) * 10.0

    score = _apply_risk_floor(
        score=score,
        highest_matched_weight=max(matched_weights, default=0.0),
        disease_risk=disease_risk,
        evidence_confidence=evidence_confidence,
        matched_symptom_count=len(matched_symptoms),
        disease_symptom_count=disease_symptom_count,
    )
    return round(min(max(score, 0.0), 10.0), 2)


def severity_level_from_score(score: float) -> str:
    if score >= 7.5:
        return "high"
    if score >= 5.0:
        return "medium"
    return "low"


def recommended_action_from_level(level: str) -> str:
    if level == "high":
        return "Seek urgent medical attention and a clinician review as soon as possible."
    if level == "medium":
        return "Schedule a doctor consultation soon for further evaluation."
    return "Monitor symptoms, rest, hydrate, and arrange a routine medical consultation if symptoms persist."


def _normalize_llm_output(
    parsed_payload: dict,
    user_symptoms: str,
    retrieved_documents: list[RetrievedDocument],
    normalized_query_symptoms: list[str] | None = None,
) -> dict:
    allowed_by_name = {
        document.disease.lower(): document for document in retrieved_documents
    }

    normalized_candidates: list[dict] = []
    for raw_candidate in parsed_payload.get("possible_diseases", []):
        if not isinstance(raw_candidate, dict):
            continue

        raw_name = str(raw_candidate.get("name", "")).strip()
        if not raw_name:
            continue

        retrieved_document = allowed_by_name.get(raw_name.lower())
        if retrieved_document is None:
            continue

        matched_symptoms = _normalize_matched_symptoms(
            raw_candidate.get("matched_symptoms", []),
            retrieved_document,
            user_symptoms,
            normalized_query_symptoms=normalized_query_symptoms,
        )
        normalized_candidates.append(
            {
                "name": retrieved_document.disease,
                "confidence": _clamp_confidence(raw_candidate.get("confidence", 0.0)),
                "matched_symptoms": matched_symptoms,
                "reason": str(raw_candidate.get("reason", "")).strip()
                or "Grounded in retrieved Chroma context only.",
            }
        )

    if not normalized_candidates:
        normalized_candidates = _fallback_candidates(
            user_symptoms,
            retrieved_documents,
            normalized_query_symptoms=normalized_query_symptoms,
        )

    normalized_candidates.sort(key=lambda item: item["confidence"], reverse=True)
    return {
        "possible_diseases": normalized_candidates[:5],
        "severity_score": 0.0,
        "severity_level": "",
        "recommended_action": "",
    }


def _normalize_matched_symptoms(
    raw_matched_symptoms: object,
    retrieved_document: RetrievedDocument,
    user_symptoms: str,
    normalized_query_symptoms: list[str] | None = None,
) -> list[str]:
    allowed_symptoms = {
        symptom.strip().lower(): symptom.strip()
        for symptom in str(retrieved_document.metadata.get("symptoms", "")).split(",")
        if symptom.strip()
    }
    query_symptoms = _extract_query_symptoms(user_symptoms, normalized_query_symptoms)

    normalized: list[str] = []
    if isinstance(raw_matched_symptoms, list):
        for symptom in raw_matched_symptoms:
            symptom_text = str(symptom).strip().lower()
            if symptom_text in allowed_symptoms and allowed_symptoms[symptom_text] not in normalized:
                normalized.append(allowed_symptoms[symptom_text])

    if normalized:
        return normalized

    for query_symptom in query_symptoms:
        if query_symptom in allowed_symptoms and allowed_symptoms[query_symptom] not in normalized:
            normalized.append(allowed_symptoms[query_symptom])

    return normalized


def _fallback_candidates(
    user_symptoms: str,
    retrieved_documents: list[RetrievedDocument],
    normalized_query_symptoms: list[str] | None = None,
) -> list[dict]:
    query_symptoms = _extract_query_symptoms(user_symptoms, normalized_query_symptoms)
    fallback: list[dict] = []

    for document in retrieved_documents[:5]:
        available_symptoms = [
            symptom.strip()
            for symptom in str(document.metadata.get("symptoms", "")).split(",")
            if symptom.strip()
        ]
        matched_symptoms = [
            symptom
            for symptom in available_symptoms
            if symptom.lower() in query_symptoms
        ]
        heuristic_confidence = round(
            min(0.95, (0.15 * len(matched_symptoms)) + (0.5 * document.similarity)),
            2,
        )
        fallback.append(
            {
                "name": document.disease,
                "confidence": heuristic_confidence,
                "matched_symptoms": matched_symptoms,
                "reason": "Fallback candidate built strictly from retrieved context.",
            }
        )

    fallback.sort(key=lambda item: item["confidence"], reverse=True)
    return fallback


def _extract_query_symptoms(
    user_symptoms: str,
    normalized_query_symptoms: list[str] | None = None,
) -> set[str]:
    normalized_text = user_symptoms.lower().replace("_", " ")
    parts = re.split(r",| and |\n", normalized_text)
    extracted = {part.strip() for part in parts if part.strip()}
    for symptom in normalized_query_symptoms or []:
        extracted.add(str(symptom).strip().lower())
    return extracted


def _clamp_confidence(value: object) -> float:
    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        return 0.0

    if numeric_value > 1.0:
        numeric_value = numeric_value / 100.0
    return round(min(max(numeric_value, 0.0), 1.0), 2)


def _symptom_risk_component(
    matched_weights: list[float],
    matched_symptom_count: int,
    max_known_weight: float,
) -> float:
    if matched_weights:
        average_weight = sum(matched_weights) / len(matched_weights)
        highest_weight = max(matched_weights)
        weighted_risk = (0.7 * average_weight) + (0.3 * highest_weight)
        return min(max(weighted_risk / max_known_weight, 0.0), 1.0)

    # Fall back to a count-only signal when no weight is available for a match.
    return min(max(matched_symptom_count, 0) / 5.0, 1.0) * 0.5


def _apply_risk_floor(
    score: float,
    highest_matched_weight: float,
    disease_risk: float,
    evidence_confidence: float,
    matched_symptom_count: int,
    disease_symptom_count: int,
) -> float:
    if matched_symptom_count == 0:
        return score

    if (
        highest_matched_weight >= CRITICAL_SYMPTOM_WEIGHT
        and evidence_confidence >= 0.55
        and disease_symptom_count > 0
        and disease_symptom_count <= 5
    ):
        return max(score, 7.5)

    if (
        highest_matched_weight >= ELEVATED_SYMPTOM_WEIGHT
        and disease_risk >= 0.55
        and evidence_confidence >= 0.30
    ):
        return max(score, 6.5)

    if disease_risk >= 0.70 and evidence_confidence >= 0.60 and matched_symptom_count >= 2:
        return max(score, 6.0)

    return score


def _safe_float(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _safe_int(value: object) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _safe_json_loads(text: str) -> dict:
    candidate = text.strip()
    if not candidate:
        return {}

    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return {}
        try:
            return json.loads(candidate[start : end + 1])
        except json.JSONDecodeError:
            return {}
