from pathlib import Path
from typing import Any

from pypdf import PdfReader


class DocumentLoader:
    """
    Load knowledge documents into a normalized structure.

    Initial support:
        - PDF
        - TXT
        - Markdown

    Output structure:
        {
            "source": "...",
            "filename": "...",
            "extension": ".pdf",
            "pages": [...]
        }
    """

    SUPPORTED_EXTENSIONS = {
        ".pdf",
        ".txt",
        ".md",
    }

    def load(
        self,
        path: str,
        domain: str | None = None,
    ) -> dict[str, Any]:

        if not path or not path.strip():
            raise ValueError(
                "Document path cannot be empty."
            )

        file_path = Path(path)

        if not file_path.exists():
            raise FileNotFoundError(
                f"Document not found: {path}"
            )

        if not file_path.is_file():
            raise ValueError(
                f"Document path is not a file: {path}"
            )

        extension = file_path.suffix.lower()

        if extension not in self.SUPPORTED_EXTENSIONS:
            raise ValueError(
                f"Unsupported document type: {extension}"
            )

        if extension == ".pdf":
            pages = self._load_pdf(
                file_path
            )

        else:
            pages = self._load_text(
                file_path
            )

        return {
            "source": str(file_path),
            "filename": file_path.name,
            "extension": extension,
            "domain": domain,
            "page_count": len(pages),
            "pages": pages,
        }

    # =========================================================
    # PDF
    # =========================================================

    @staticmethod
    def _load_pdf(
        file_path: Path,
    ) -> list[dict[str, Any]]:

        reader = PdfReader(
            str(file_path)
        )

        pages = []

        for index, page in enumerate(
            reader.pages,
            start=1,
        ):

            try:
                text = (
                    page.extract_text()
                    or ""
                )

            except Exception:
                text = ""

            text = text.strip()

            pages.append(
                {
                    "page": index,
                    "text": text,
                    "character_count": len(
                        text
                    ),
                }
            )

        return pages

    # =========================================================
    # Plain text / Markdown
    # =========================================================

    @staticmethod
    def _load_text(
        file_path: Path,
    ) -> list[dict[str, Any]]:

        text = file_path.read_text(
            encoding="utf-8",
            errors="replace",
        )

        return [
            {
                "page": 1,
                "text": text.strip(),
                "character_count": len(
                    text.strip()
                ),
            }
        ]