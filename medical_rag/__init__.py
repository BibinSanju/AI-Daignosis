from __future__ import annotations


__all__ = ["MedicalRAGPipeline"]


def __getattr__(name: str):
    if name == "MedicalRAGPipeline":
        from .pipeline import MedicalRAGPipeline

        return MedicalRAGPipeline
    raise AttributeError(f"module 'medical_rag' has no attribute {name!r}")
