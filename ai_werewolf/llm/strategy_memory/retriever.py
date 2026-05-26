from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Protocol

from openai import OpenAI

from ai_werewolf.config.application import StrategyMemoryConfig
from ai_werewolf.llm.strategy_memory.ingest import iter_markdown_chunks, stable_chunk_id
from ai_werewolf.llm.strategy_memory.schemas import RagHit, RagQuery, StrategyDocumentMetadata

logger = logging.getLogger(__name__)


class StrategyRetriever(Protocol):
    def retrieve(self, query: RagQuery, *, top_k: int) -> list[RagHit]:
        ...


class NullStrategyRetriever:
    def retrieve(self, query: RagQuery, *, top_k: int) -> list[RagHit]:
        return []


class InMemoryStrategyRetriever:
    def __init__(self, *, hits: list[RagHit]) -> None:
        self._hits = hits

    def retrieve(self, query: RagQuery, *, top_k: int) -> list[RagHit]:
        filtered = [
            hit for hit in self._hits
            if _metadata_matches(hit.metadata, query.role_key, query.phase)
        ]
        return filtered[:top_k]


class OpenAIEmbeddingFunction:
    def __init__(self, *, base_url: str, api_key: str, model: str) -> None:
        self.client = OpenAI(base_url=base_url, api_key=api_key)
        self.model = model

    def __call__(self, input: list[str]) -> list[list[float]]:
        response = self.client.embeddings.create(model=self.model, input=input)
        return [item.embedding for item in response.data]


class ChromaStrategyRetriever:
    def __init__(self, *, config: StrategyMemoryConfig, package_root: Path) -> None:
        import chromadb

        api_key = os.getenv(config.embedding_api_key_env)
        if not api_key:
            raise RuntimeError(f"{config.embedding_api_key_env} is required for strategy memory embeddings")
        persist_dir = _resolve_path(package_root, config.persist_dir)
        self._embedding = OpenAIEmbeddingFunction(
            base_url=config.embedding_base_url,
            api_key=api_key,
            model=config.embedding_model,
        )
        self._client = chromadb.PersistentClient(path=str(persist_dir))
        self._collection = self._client.get_or_create_collection(
            name=config.collection_name,
            embedding_function=self._embedding,
        )

    def retrieve(self, query: RagQuery, *, top_k: int) -> list[RagHit]:
        result = self._collection.query(
            query_texts=[query.to_search_text()],
            n_results=max(top_k * 4, top_k),
        )
        documents = (result.get("documents") or [[]])[0]
        metadatas = (result.get("metadatas") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]
        hits: list[RagHit] = []
        for content, metadata_payload, distance in zip(documents, metadatas, distances, strict=False):
            metadata = StrategyDocumentMetadata.model_validate(metadata_payload)
            if not _metadata_matches(metadata, query.role_key, query.phase):
                continue
            hits.append(RagHit(content=str(content), metadata=metadata, score=float(distance)))
            if len(hits) >= top_k:
                break
        return hits

    def ingest_directory(self, knowledge_dir: Path, *, max_chars: int = 1200) -> int:
        chunks = list(iter_markdown_chunks(knowledge_dir, max_chars=max_chars))
        if not chunks:
            return 0
        self._collection.upsert(
            ids=[stable_chunk_id(chunk) for chunk in chunks],
            documents=[chunk.content for chunk in chunks],
            metadatas=[chunk.metadata.model_dump(mode="json") for chunk in chunks],
        )
        return len(chunks)


def _metadata_matches(metadata: StrategyDocumentMetadata, role_key: str, phase: str) -> bool:
    return metadata.role_key in {role_key, "any"} and metadata.phase in {phase, "any"}


def _resolve_path(package_root: Path, path: str) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return package_root / candidate
