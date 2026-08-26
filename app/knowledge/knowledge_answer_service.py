import re
from typing import Any

from app.generation.provider import GenerationProvider
from app.generation.provider_factory import create_generation_provider
from app.retrieval.retrieval_service import RetrievalService
from app.vectorstore.chroma_store import ChromaVectorStore


class KnowledgeAnswerService:
    """
    Retrieve, rerank, and answer from local technical knowledge.

    Pipeline:
        question
            ↓
        vector retrieval
            ↓
        lexical/evidence reranking
            ↓
        strongest evidence
            ↓
        grounded local LLM answer
    """

    STOP_WORDS = {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "for",
        "from",
        "how",
        "in",
        "is",
        "it",
        "of",
        "on",
        "or",
        "that",
        "the",
        "this",
        "to",
        "was",
        "what",
        "when",
        "where",
        "which",
        "with",
    }

    def __init__(
        self,
        retrieval_service: RetrievalService | None = None,
        model: str | None = None,
        host: str | None = None,
        generator: GenerationProvider | None = None,
        n_results: int = 8,
        evidence_limit: int = 4,
    ):
        if n_results <= 0:
            raise ValueError(
                "n_results must be greater than zero."
            )

        if evidence_limit <= 0:
            raise ValueError(
                "evidence_limit must be greater than zero."
            )

        if retrieval_service is None:

            technical_store = ChromaVectorStore(
                persist_directory="data/chroma",
                collection_name="technical_knowledge",
            )

            retrieval_service = RetrievalService(
                vector_store=technical_store,
                relevance_threshold=0.85,
            )

        self.retrieval_service = retrieval_service
        self.generator = generator or create_generation_provider(
            model=model,
            host=host,
        )

        self.n_results = n_results
        self.evidence_limit = evidence_limit

    # =========================================================
    # Tokenization
    # =========================================================

    @classmethod
    def _important_tokens(
        cls,
        text: str,
    ) -> set[str]:

        tokens = set(
            re.findall(
                r"[a-zA-Z0-9_-]+",
                text.lower(),
            )
        )

        return {
            token
            for token in tokens
            if (
                token not in cls.STOP_WORDS
                and len(token) > 1
            )
        }

    # =========================================================
    # Evidence reranking
    # =========================================================

    def _rerank(
        self,
        question: str,
        results: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:

        query_tokens = self._important_tokens(
            question
        )

        reranked = []

        for item in results:

            text = (
                item.get("text", "")
                or ""
            )

            text_tokens = self._important_tokens(
                text
            )

            matched_tokens = (
                query_tokens
                & text_tokens
            )

            coverage = (
                len(matched_tokens)
                / max(
                    len(query_tokens),
                    1,
                )
            )

            distance = item.get(
                "distance"
            )

            if distance is None:
                vector_score = 0.0
            else:
                # Lower Chroma distance is better.
                vector_score = max(
                    0.0,
                    1.0 - float(distance),
                )

            # Question-specific lexical evidence is
            # weighted more heavily than vector rank.
            rerank_score = (
                0.70 * coverage
                + 0.30 * vector_score
            )

            enriched = dict(item)

            enriched[
                "rerank_score"
            ] = round(
                rerank_score,
                6,
            )

            enriched[
                "matched_query_tokens"
            ] = sorted(
                matched_tokens
            )

            reranked.append(
                enriched
            )

        reranked.sort(
            key=lambda item: item[
                "rerank_score"
            ],
            reverse=True,
        )

        return reranked

    # =========================================================
    # Context formatting
    # =========================================================

    @staticmethod
    def _format_context(
        results: list[dict[str, Any]],
    ) -> str:

        blocks = []

        for index, item in enumerate(
            results,
            start=1,
        ):

            metadata = item.get(
                "metadata",
                {},
            )

            source = metadata.get(
                "source",
                "unknown",
            )

            page = metadata.get(
                "page",
                "unknown",
            )

            text = (
                item.get(
                    "text",
                    "",
                )
                .strip()
            )

            blocks.append(
                f"[EVIDENCE {index}]\n"
                f"Source: {source}\n"
                f"Page: {page}\n"
                f"Rerank score: "
                f"{item.get('rerank_score')}\n"
                f"Matched query terms: "
                f"{item.get('matched_query_tokens')}\n"
                f"Text:\n{text}"
            )

        return "\n\n".join(
            blocks
        )

    # =========================================================
    # Source list
    # =========================================================

    @staticmethod
    def _build_sources(
        results: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:

        sources = []
        seen = set()

        for item in results:

            metadata = item.get(
                "metadata",
                {},
            )

            source = metadata.get(
                "source"
            )

            page = metadata.get(
                "page"
            )

            key = (
                source,
                page,
            )

            if key in seen:
                continue

            seen.add(key)

            sources.append(
                {
                    "source": source,
                    "page": page,
                    "distance": item.get(
                        "distance"
                    ),
                    "rerank_score": item.get(
                        "rerank_score"
                    ),
                }
            )

        return sources

    # =========================================================
    # Answer
    # =========================================================

    def answer(
        self,
        question: str,
        domain: str,
    ) -> dict[str, Any]:

        if not question or not question.strip():
            raise ValueError(
                "Question cannot be empty."
            )

        if not domain or not domain.strip():
            raise ValueError(
                "Domain cannot be empty."
            )

        # -----------------------------------------------------
        # Vector retrieval
        # -----------------------------------------------------

        retrieved = (
            self.retrieval_service
            .search_by_domain(
                query=question,
                domain=domain,
                n_results=self.n_results,
            )
        )

        if not retrieved:

            return {
                "status":
                    "insufficient_knowledge",
                "question": question,
                "domain": domain,
                "answer": (
                    "The available knowledge base "
                    "does not contain sufficient "
                    "evidence to answer this question."
                ),
                "sources": [],
                "retrieved_chunks": 0,
            }

        # -----------------------------------------------------
        # Rerank retrieved evidence
        # -----------------------------------------------------

        reranked = self._rerank(
            question,
            retrieved,
        )

        evidence = reranked[
            :self.evidence_limit
        ]

        context = self._format_context(
            evidence
        )

        # -----------------------------------------------------
        # Grounded generation
        # -----------------------------------------------------

        system_prompt = """
You are a technical evidence-based question answering system.

You must use ONLY the supplied retrieved evidence.

Rules:

1. Answer the exact question immediately.
2. Prioritize explicit statements that directly answer the question.
3. Preserve exact numbers, units, parameter names, commands, and terminology.
4. If both a default value and recommended value are stated, report both.
5. State the reason when the evidence explicitly gives one.
6. Do not replace a direct numerical answer with a general explanation.
7. Do not repeat yourself.
8. Do not introduce outside knowledge.
9. Normally answer in no more than 3 short paragraphs.
10. Finish with the strongest supporting source in this exact form:

Source: <document>, page <page>

If the evidence does not actually answer the question, say:

The retrieved evidence is insufficient to answer this question.
"""

        user_prompt = f"""
QUESTION:
{question}

DOMAIN:
{domain}

RETRIEVED AND RERANKED EVIDENCE:
{context}

Answer the exact question.
"""

        answer_text = self.generator.chat(
            messages=[
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": user_prompt,
                },
            ],
            temperature=0.0,
            max_tokens=220,
        )

        return {
            "status": "completed",
            "question": question,
            "domain": domain,
            "answer": answer_text,
            "sources": self._build_sources(
                evidence
            ),
            "retrieved_chunks": len(
                retrieved
            ),
            "evidence_chunks": len(
                evidence
            ),
        }
