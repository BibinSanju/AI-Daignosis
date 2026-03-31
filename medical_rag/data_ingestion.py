from __future__ import annotations

import csv
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class MedicalDocument:
    doc_id: str
    disease: str
    symptoms: list[str]
    severity_score: float
    severity_level: str
    severity_description: str
    chunk_text: str
    metadata: dict[str, str | int | float]


def load_medical_documents(
    dataset_csv: str | Path,
    symptom_severity_csv: str | Path | None = None,
) -> list[MedicalDocument]:
    dataset_path = Path(dataset_csv)
    symptom_weights = load_symptom_weights(symptom_severity_csv)

    with dataset_path.open(newline="", encoding="utf-8") as file_obj:
        reader = csv.DictReader(file_obj)
        if not reader.fieldnames:
            raise ValueError(f"Dataset has no header row: {dataset_path}")

        symptom_columns = [
            column_name for column_name in reader.fieldnames if column_name.lower().startswith("symptom_")
        ]
        disease_to_symptoms: dict[str, set[str]] = defaultdict(set)

        for row in reader:
            disease = str(row.get("Disease", "")).strip()
            if not disease:
                continue

            for column_name in symptom_columns:
                symptom_value = str(row.get(column_name, "")).strip()
                if symptom_value:
                    disease_to_symptoms[disease].add(_normalize_symptom_label(symptom_value))

    documents: list[MedicalDocument] = []
    for disease, symptoms in sorted(disease_to_symptoms.items()):
        ordered_symptoms = sorted(symptoms)
        severity_score = _compute_average_symptom_weight(ordered_symptoms, symptom_weights)
        severity_level = _severity_level_from_weight(severity_score)
        severity_description = _build_severity_description(
            severity_score=severity_score,
            severity_level=severity_level,
            symptoms=ordered_symptoms,
            symptom_weights=symptom_weights,
        )
        chunk_text = (
            f"Disease: {disease}. "
            f"Symptoms: {', '.join(ordered_symptoms)}. "
            f"Severity: {severity_description}"
        )
        documents.append(
            MedicalDocument(
                doc_id=_slugify(disease),
                disease=disease,
                symptoms=ordered_symptoms,
                severity_score=round(severity_score, 2),
                severity_level=severity_level,
                severity_description=severity_description,
                chunk_text=chunk_text,
                metadata={
                    "disease": disease,
                    "symptoms": ", ".join(ordered_symptoms),
                    "symptom_count": len(ordered_symptoms),
                    "severity_level": severity_level,
                    "severity_score": round(severity_score, 2),
                },
            )
        )

    return documents


def _load_symptom_weights(csv_path: Path) -> dict[str, float]:
    symptom_weights: dict[str, float] = {}

    with csv_path.open(newline="", encoding="utf-8") as file_obj:
        reader = csv.DictReader(file_obj)
        for row in reader:
            symptom = _normalize_symptom_label(str(row.get("Symptom", "")))
            if not symptom:
                continue

            try:
                symptom_weights[symptom] = float(row.get("weight", 0) or 0)
            except ValueError:
                symptom_weights[symptom] = 0.0

    return symptom_weights


def load_symptom_weights(csv_path: str | Path | None) -> dict[str, float]:
    if not csv_path:
        return {}

    path = Path(csv_path)
    if not path.exists():
        return {}

    return _load_symptom_weights(path)


def _normalize_symptom_label(value: str) -> str:
    normalized = re.sub(r"[\s_]+", " ", value.strip().lower())
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def normalize_symptom_label(value: str) -> str:
    return _normalize_symptom_label(value)


def _compute_average_symptom_weight(
    symptoms: list[str],
    symptom_weights: dict[str, float],
) -> float:
    if not symptoms:
        return 0.0

    weights = [symptom_weights.get(symptom, 0.0) for symptom in symptoms]
    if not weights:
        return 0.0

    return sum(weights) / len(weights)


def _severity_level_from_weight(weight: float) -> str:
    if weight >= 4.0:
        return "high"
    if weight >= 2.5:
        return "medium"
    return "low"


def _build_severity_description(
    severity_score: float,
    severity_level: str,
    symptoms: list[str],
    symptom_weights: dict[str, float],
) -> str:
    weights = [symptom_weights.get(symptom, 0.0) for symptom in symptoms]
    max_weight = max(weights) if weights else 0.0
    return (
        f"{severity_level} symptom burden derived from symptom-weight data "
        f"(average symptom weight {severity_score:.2f}, max symptom weight {max_weight:.2f})"
    )


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    return slug or "medical-document"
