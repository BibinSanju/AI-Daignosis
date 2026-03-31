from __future__ import annotations

import unittest
from pathlib import Path

from medical_rag.data_ingestion import load_medical_documents, load_symptom_weights
from medical_rag.output_builder import compute_severity_score, severity_level_from_score
from medical_rag.retrieval import RetrievedDocument


class SeverityScoringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        project_root = Path(__file__).resolve().parents[1]
        dataset_csv = project_root / "latest data med" / "dataset.csv"
        severity_csv = project_root / "latest data med" / "Symptom-severity.csv"

        cls.documents = {
            document.disease: document
            for document in load_medical_documents(dataset_csv, severity_csv)
        }
        cls.symptom_weights = load_symptom_weights(severity_csv)

    @classmethod
    def _retrieved_document(
        cls,
        disease_name: str,
        similarity: float = 0.78,
    ) -> RetrievedDocument:
        document = cls.documents[disease_name]
        return RetrievedDocument(
            disease=document.disease,
            document=document.chunk_text,
            metadata=document.metadata,
            distance=1.0 - similarity,
            similarity=similarity,
        )

    def test_critical_single_symptom_is_high(self) -> None:
        score = compute_severity_score(
            matched_symptoms=["chest pain"],
            top_confidence=0.72,
            top_document=self._retrieved_document("Heart attack"),
            symptom_weights=self.symptom_weights,
        )

        self.assertGreaterEqual(score, 7.5)
        self.assertEqual(severity_level_from_score(score), "high")

    def test_common_single_symptom_stays_low(self) -> None:
        score = compute_severity_score(
            matched_symptoms=["cough"],
            top_confidence=0.70,
            top_document=self._retrieved_document("Common Cold"),
            symptom_weights=self.symptom_weights,
        )

        self.assertLess(score, 5.0)
        self.assertEqual(severity_level_from_score(score), "low")

    def test_additional_matching_symptoms_raise_score(self) -> None:
        single_score = compute_severity_score(
            matched_symptoms=["cough"],
            top_confidence=0.70,
            top_document=self._retrieved_document("Common Cold"),
            symptom_weights=self.symptom_weights,
        )
        combined_score = compute_severity_score(
            matched_symptoms=["cough", "runny nose"],
            top_confidence=0.74,
            top_document=self._retrieved_document("Common Cold"),
            symptom_weights=self.symptom_weights,
        )

        self.assertGreater(combined_score, single_score)
        self.assertEqual(severity_level_from_score(combined_score), "medium")

    def test_broad_disease_does_not_match_heart_attack_severity(self) -> None:
        score = compute_severity_score(
            matched_symptoms=["high fever", "runny nose"],
            top_confidence=0.56,
            top_document=self._retrieved_document("Common Cold"),
            symptom_weights=self.symptom_weights,
        )

        self.assertLess(score, 7.5)
        self.assertEqual(severity_level_from_score(score), "medium")


if __name__ == "__main__":
    unittest.main()
