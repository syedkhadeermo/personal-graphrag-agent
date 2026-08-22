from ollama import Client


class OllamaGenerator:
    """Generate strictly context-grounded answers using Ollama."""

    def __init__(
        self,
        model: str = "deepseek-coder:6.7b",
        host: str = "http://localhost:11434",
    ):
        self.model = model
        self.client = Client(host=host)

    def generate(self, question: str, context: str) -> str:
        """Generate an answer using only the supplied context."""

        if not question or not question.strip():
            raise ValueError("Question cannot be empty.")

        if not context or not context.strip():
            raise ValueError("Context cannot be empty.")

        prompt = f"""
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

        response = self.client.chat(
            model=self.model,
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
        )

        return response["message"]["content"].strip()