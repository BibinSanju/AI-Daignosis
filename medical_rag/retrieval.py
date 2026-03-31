from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .embedding_store import MedicalVectorStore


@dataclass(frozen=True)
class RetrievedDocument:
    disease: str
    document: str
    metadata: dict[str, Any]
    distance: float
    similarity: float


def retrieve_top_k(
    vector_store: MedicalVectorStore,
    symptom_text: str,
    top_k: int = 5,
) -> list[RetrievedDocument]:
    raw_results = vector_store.query(symptom_text, n_results=top_k)

    documents = raw_results.get("documents", [[]])[0]
    metadatas = raw_results.get("metadatas", [[]])[0]
    distances = raw_results.get("distances", [[]])[0]

    retrieved_documents: list[RetrievedDocument] = []
    for document, metadata, distance in zip(documents, metadatas, distances):
        metadata = metadata or {}
        cosine_distance = float(distance or 0.0)
        similarity = max(0.0, min(1.0, 1.0 - cosine_distance))
        retrieved_documents.append(
            RetrievedDocument(
                disease=str(metadata.get("disease", "Unknown disease")),
                document=str(document),
                metadata=metadata,
                distance=cosine_distance,
                similarity=round(similarity, 4),
            )
        )

    return retrieved_documents


def format_retrieved_context(retrieved_documents: list[RetrievedDocument]) -> str:
    if not retrieved_documents:
        return "No retrieved medical documents were found."

    context_blocks: list[str] = []
    for index, document in enumerate(retrieved_documents, start=1):
        symptoms = str(document.metadata.get("symptoms", ""))
        severity_level = str(document.metadata.get("severity_level", "unknown"))
        severity_score = document.metadata.get("severity_score", 0.0)
        context_blocks.append(
            "\n".join(
                [
                    f"Document {index}:",
                    f"Disease: {document.disease}",
                    f"Similarity: {document.similarity}",
                    f"Symptoms: {symptoms}",
                    f"Severity level: {severity_level}",
                    f"Severity score: {severity_score}",
                    f"Chunk: {document.document}",
                ]
            )
        )

    return "\n\n".join(context_blocks)
