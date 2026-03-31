from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Sequence

import chromadb
from chromadb.config import DEFAULT_DATABASE, DEFAULT_TENANT, Settings
from sentence_transformers import SentenceTransformer

from .data_ingestion import MedicalDocument


os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
logging.getLogger("huggingface_hub").setLevel(logging.ERROR)
logging.getLogger("sentence_transformers").setLevel(logging.ERROR)
logging.getLogger("transformers").setLevel(logging.ERROR)


class MedicalVectorStore:
    def __init__(
        self,
        persist_directory: str | Path,
        collection_name: str = "medical_knowledge",
        embedding_model_name: str = "all-MiniLM-L6-v2",
    ) -> None:
        self.persist_directory = Path(persist_directory)
        self.persist_directory.mkdir(parents=True, exist_ok=True)
        self.collection_name = collection_name
        self.embedding_model_name = embedding_model_name

        self.client = chromadb.PersistentClient(
            path=str(self.persist_directory),
            settings=Settings(),
            tenant=DEFAULT_TENANT,
            database=DEFAULT_DATABASE,
        )
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        self.embedder = SentenceTransformer(self.embedding_model_name)

    def index_documents(self, documents: Sequence[MedicalDocument]) -> None:
        if not documents:
            return

        ids = [document.doc_id for document in documents]
        chunks = [document.chunk_text for document in documents]
        metadatas = [document.metadata for document in documents]
        embeddings = self.embed_texts(chunks)

        self.collection.upsert(
            ids=ids,
            documents=chunks,
            metadatas=metadatas,
            embeddings=embeddings,
        )

    def query(self, query_text: str, n_results: int = 5) -> dict:
        query_embedding = self.embed_texts([query_text])[0]
        return self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            include=["documents", "metadatas", "distances"],
        )

    def count(self) -> int:
        return self.collection.count()

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        embeddings = self.embedder.encode(
            list(texts),
            normalize_embeddings=True,
        )
        return embeddings.tolist()
