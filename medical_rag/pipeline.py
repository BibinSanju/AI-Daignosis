from __future__ import annotations

import os
from pathlib import Path

from .data_ingestion import MedicalDocument, load_medical_documents, load_symptom_weights
from .embedding_store import MedicalVectorStore
from .llm_reasoning import GroqMedicalReasoner
from .output_builder import build_final_output
from .retrieval import RetrievedDocument, retrieve_top_k
from .symptom_matcher import SymptomMatch, SymptomMatcher


class MedicalRAGPipeline:
    def __init__(
        self,
        dataset_csv: str | Path,
        symptom_severity_csv: str | Path | None = None,
        chroma_path: str | Path = "storage/chroma",
        collection_name: str = "medical_knowledge",
        embedding_model_name: str = "all-MiniLM-L6-v2",
        groq_model_name: str = "llama3-70b-8192",
    ) -> None:
        self.dataset_csv = Path(dataset_csv)
        self.symptom_severity_csv = (
            Path(symptom_severity_csv) if symptom_severity_csv else None
        )
        self.vector_store = MedicalVectorStore(
            persist_directory=chroma_path,
            collection_name=collection_name,
            embedding_model_name=embedding_model_name,
        )
        self.groq_model_name = groq_model_name
        self._reasoner: GroqMedicalReasoner | None = None
        self._documents: list[MedicalDocument] | None = None
        self._symptom_matcher: SymptomMatcher | None = None
        self._symptom_weights: dict[str, float] = {}

    def build_index(self) -> list[MedicalDocument]:
        self._symptom_weights = load_symptom_weights(self.symptom_severity_csv)
        documents = load_medical_documents(
            dataset_csv=self.dataset_csv,
            symptom_severity_csv=self.symptom_severity_csv,
        )
        self.vector_store.index_documents(documents)
        self._documents = documents
        symptom_inventory = sorted(
            {
                symptom
                for document in documents
                for symptom in document.symptoms
            }
        )
        self._symptom_matcher = SymptomMatcher(
            embed_texts=self.vector_store.embed_texts,
            symptom_inventory=symptom_inventory,
        )
        return documents

    def diagnose(self, symptom_text: str) -> dict:
        return self.analyze(symptom_text)["diagnosis"]

    def retrieve(self, symptom_text: str, top_k: int = 5) -> list[RetrievedDocument]:
        self._ensure_ready()

        symptom_matches = self._get_symptom_matcher().match(symptom_text)
        normalized_symptoms = [match.matched_symptom for match in symptom_matches]
        retrieval_query = self._build_retrieval_query(symptom_text, normalized_symptoms)

        return retrieve_top_k(
            vector_store=self.vector_store,
            symptom_text=retrieval_query,
            top_k=top_k,
        )

    def analyze(self, symptom_text: str) -> dict:
        self._ensure_ready()

        symptom_matches = self._get_symptom_matcher().match(symptom_text)
        normalized_symptoms = [match.matched_symptom for match in symptom_matches]
        retrieval_query = self._build_retrieval_query(symptom_text, normalized_symptoms)
        retrieved_documents = retrieve_top_k(
            vector_store=self.vector_store,
            symptom_text=retrieval_query,
            top_k=5,
        )

        try:
            llm_response = self._get_reasoner().reason(
                symptom_text,
                retrieved_documents,
                normalized_symptoms=normalized_symptoms,
            )
        except Exception:
            llm_response = "{}"

        diagnosis = build_final_output(
            llm_response_text=llm_response,
            user_symptoms=symptom_text,
            retrieved_documents=retrieved_documents,
            normalized_query_symptoms=normalized_symptoms,
            symptom_weights=self._symptom_weights,
        )

        return {
            "diagnosis": diagnosis,
            "normalized_symptoms": normalized_symptoms,
            "symptom_matches": [
                {
                    "query_phrase": match.query_phrase,
                    "matched_symptom": match.matched_symptom,
                    "similarity": match.similarity,
                }
                for match in symptom_matches
            ],
            "retrieved_documents": [
                {
                    "disease": document.disease,
                    "similarity": document.similarity,
                    "severity_level": document.metadata.get("severity_level", ""),
                    "severity_score": document.metadata.get("severity_score", 0.0),
                }
                for document in retrieved_documents
            ],
        }

    def _ensure_ready(self) -> None:
        if self._documents is None or self._symptom_matcher is None:
            self.build_index()

    def _get_symptom_matcher(self) -> SymptomMatcher:
        self._ensure_ready()
        return self._symptom_matcher  # type: ignore[return-value]

    @staticmethod
    def _build_retrieval_query(symptom_text: str, normalized_symptoms: list[str]) -> str:
        if not normalized_symptoms:
            return symptom_text
        return (
            f"User symptoms: {symptom_text}\n"
            f"Matched dataset symptoms: {', '.join(normalized_symptoms)}"
        )

    def _get_reasoner(self) -> GroqMedicalReasoner:
        if self._reasoner is None:
            self._load_local_env()
            self._reasoner = GroqMedicalReasoner(
                api_key=os.environ.get("GROQ_API_KEY"),
                model_name=self.groq_model_name,
            )
        return self._reasoner

    @staticmethod
    def _load_local_env() -> None:
        env_path = Path(__file__).resolve().parent.parent / ".env"
        if not env_path.exists():
            return

        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue

            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
