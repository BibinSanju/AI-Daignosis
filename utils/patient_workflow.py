from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from medical_rag.pipeline import MedicalRAGPipeline
from utils.speech import transcribe_audio


APP_DIR = Path(__file__).resolve().parent.parent
DATASET_PATH = APP_DIR / "latest data med" / "dataset.csv"
SYMPTOM_SEVERITY_PATH = APP_DIR / "latest data med" / "Symptom-severity.csv"
CHROMA_PATH = APP_DIR / "storage" / "chroma"


@lru_cache(maxsize=1)
def get_rag_pipeline() -> MedicalRAGPipeline:
    pipeline = MedicalRAGPipeline(
        dataset_csv=DATASET_PATH,
        symptom_severity_csv=SYMPTOM_SEVERITY_PATH,
        chroma_path=CHROMA_PATH,
    )
    pipeline.build_index()
    return pipeline


def clear_rag_pipeline_cache() -> None:
    get_rag_pipeline.cache_clear()


def analyze_patient_audio(audio_path: Path) -> dict[str, Any]:
    transcription = transcribe_audio(str(audio_path))
    analysis = get_rag_pipeline().analyze(transcription["translated_text"])
    return {
        "source_transcript": transcription["source_text"],
        "translated_text": transcription["translated_text"],
        "diagnosis": analysis["diagnosis"],
        "matched_dataset_symptoms": analysis["normalized_symptoms"],
        "symptom_matches": analysis["symptom_matches"],
        "retrieved_disease_candidates": analysis["retrieved_documents"],
    }
