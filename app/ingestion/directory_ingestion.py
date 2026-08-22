from pathlib import Path

from app.ingestion.ingestion_pipeline import IngestionPipeline


class DirectoryIngestion:
    """Ingest multiple supported documents from a directory."""

    SUPPORTED_EXTENSIONS = {
        ".md",
        ".txt",
    }

    def __init__(
        self,
        pipeline: IngestionPipeline | None = None,
    ):
        self.pipeline = pipeline or IngestionPipeline()

    def ingest_directory(
        self,
        directory: str,
        domain: str,
    ) -> dict:

        path = Path(directory)

        if not path.exists():
            raise FileNotFoundError(
                f"Directory not found: {directory}"
            )

        if not path.is_dir():
            raise ValueError(
                f"Path is not a directory: {directory}"
            )

        files = [
            file
            for file in path.rglob("*")
            if file.is_file()
            and file.suffix.lower()
            in self.SUPPORTED_EXTENSIONS
        ]

        results = []

        total_chunks = 0

        for file in sorted(files):

            chunks = self.pipeline.ingest_file(
                str(file),
                domain,
            )

            results.append(
                {
                    "file": str(file),
                    "chunks": chunks,
                }
            )

            total_chunks += chunks

        return {
            "directory": str(path),
            "domain": domain,
            "files_processed": len(files),
            "total_chunks": total_chunks,
            "files": results,
        }