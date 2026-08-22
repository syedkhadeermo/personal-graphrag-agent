from pathlib import Path


class MarkdownDocumentLoader:
    """Load Markdown documents from disk."""

    def load(self, file_path: str) -> dict:
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        if path.suffix.lower() != ".md":
            raise ValueError("Only Markdown (.md) files are supported.")

        text = path.read_text(encoding="utf-8")

        if not text.strip():
            raise ValueError("Document is empty.")

        return {
            "text": text,
            "metadata": {
                "source": str(path),
                "file_name": path.name,
                "file_type": "markdown",
            },
        }