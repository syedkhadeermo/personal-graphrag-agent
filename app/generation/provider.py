from collections.abc import Mapping, Sequence
from typing import Protocol, TypedDict


class ChatMessage(TypedDict):
    role: str
    content: str


class GenerationProvider(Protocol):
    """Provider-neutral interface for grounded text generation."""

    def generate(self, question: str, context: str) -> str:
        """Answer a question using only the supplied context."""
        ...

    def chat(
        self,
        messages: Sequence[Mapping[str, str]],
        *,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> str:
        """Generate text from provider-neutral chat messages."""
        ...


def grounded_prompt(question: str, context: str) -> str:
    """Build the shared evidence-only prompt used by every provider."""

    if not question or not question.strip():
        raise ValueError("Question cannot be empty.")
    if not context or not context.strip():
        raise ValueError("Context cannot be empty.")

    return f"""
You are a strict evidence-based question answering system.

Your ONLY source of factual information is the CONTEXT below.

RULES:
- Every factual statement in your answer must be directly supported
  by the CONTEXT.
- Do NOT use your pretrained knowledge.
- Do NOT expand, interpret, explain, or infer beyond the CONTEXT.
- Do NOT introduce terminology that is absent from the CONTEXT unless
  it is necessary to repeat the user's question.
- Do NOT provide examples that are not in the CONTEXT.
- Do NOT add mechanisms, methods, results, numbers, or technical details
  that are not explicitly stated in the CONTEXT.
- If the CONTEXT does not explicitly answer the question, respond exactly:

"The available knowledge base does not contain enough information
to answer this question."

CONTEXT:
{context}

QUESTION:
{question}

Return only the answer.
"""
