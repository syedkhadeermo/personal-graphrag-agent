from pathlib import Path

from app.ingestion.ingestion_pipeline import IngestionPipeline


class PublicKnowledgeIngestion:
    """
    Batch ingestion service for public knowledge organized by domain.

    Expected structure:

        data/public/
            drug_discovery/
            cad_simulation/
            cybersecurity/
    """

    SUPPORTED_DOMAINS = {
        "drug_discovery",
        "cad_simulation",
        "cybersecurity",
    }

    SUPPORTED_EXTENSIONS = {
        ".md",
        ".txt",
    }

    def __init__(
        self,
        public_root: str = "data/public",
        pipeline: IngestionPipeline | None = None,
    ):
        self.public_root = Path(public_root)
        self.pipeline = pipeline or IngestionPipeline()

    def ingest_domain(self, domain: str) -> dict:
        """Ingest all supported files belonging to one domain."""

        if domain not in self.SUPPORTED_DOMAINS:
            raise ValueError(
                f"Unsupported domain: {domain}. "
                f"Expected one of: {sorted(self.SUPPORTED_DOMAINS)}"
            )

        domain_path = self.public_root / domain

        if not domain_path.exists():
            raise FileNotFoundError(
                f"Domain directory does not exist: {domain_path}"
            )

        files = sorted(
            path
            for path in domain_path.rglob("*")
            if path.is_file()
            and path.suffix.lower() in self.SUPPORTED_EXTENSIONS
        )

        total_chunks = 0
        processed_files = []

        for file_path in files:
            chunks = self.pipeline.ingest_file(
                str(file_path),
                domain,
            )

            total_chunks += chunks
            processed_files.append(
                {
                    "file": str(file_path),
                    "chunks": chunks,
                }
            )

        return {
            "domain": domain,
            "files_processed": len(processed_files),
            "chunks_ingested": total_chunks,
            "files": processed_files,
        }

    def ingest_all(self) -> dict:
        """Ingest all public knowledge domains."""

        results = {}

        for domain in sorted(self.SUPPORTED_DOMAINS):
            results[domain] = self.ingest_domain(domain)

        return results