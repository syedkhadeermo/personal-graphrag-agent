import argparse
import json

from typing import Any

import chromadb


MIGRATIONS = (
    {
        "source":
            "autodock_vina_documentation.pdf",

        "expected_count":
            114,

        "metadata": {
            "domain":
                "drug_discovery",

            "subdomain":
                "docking",

            "tool":
                "autodock_vina",

            "version":
                "1.2.0",

            "visibility":
                "public",

            "document_type":
                "official_documentation",
        },
    },
    {
        "source":
            "gromacs_manual.pdf",

        "expected_count":
            2560,

        "metadata": {
            "domain":
                "drug_discovery",

            "subdomain":
                "molecular_dynamics",

            "tool":
                "gromacs",

            "version":
                "2025.0",

            "visibility":
                "public",

            "document_type":
                "official_documentation",
        },
    },
)


def enrich_source(
    collection: Any,
    source: str,
    expected_count: int,
    metadata_updates: dict[str, Any],
    apply: bool,
    batch_size: int = 500,
) -> dict[str, Any]:
    """
    Enrich metadata for all records from one exact source.

    Documents, embeddings, IDs, and collection membership are
    not changed.
    """

    result = collection.get(
        where={
            "source": {
                "$eq": source,
            }
        },
        include=[
            "metadatas",
        ],
    )

    ids = result.get(
        "ids",
        [],
    )

    metadatas = result.get(
        "metadatas",
        [],
    )

    records_found = len(
        ids
    )

    if records_found != expected_count:
        raise RuntimeError(
            "Source record-count preflight failed: "
            f"source={source}; "
            f"expected={expected_count}; "
            f"found={records_found}"
        )

    changed_ids = []
    changed_metadatas = []

    for record_id, metadata in zip(
        ids,
        metadatas,
        strict=True,
    ):
        existing_metadata = dict(
            metadata or {}
        )

        updated_metadata = dict(
            existing_metadata
        )

        updated_metadata.update(
            metadata_updates
        )

        if (
            updated_metadata
            != existing_metadata
        ):
            changed_ids.append(
                record_id
            )

            changed_metadatas.append(
                updated_metadata
            )

    records_requiring_update = len(
        changed_ids
    )

    batches = 0

    if apply:

        for start in range(
            0,
            records_requiring_update,
            batch_size,
        ):
            end = (
                start
                + batch_size
            )

            collection.update(
                ids=changed_ids[
                    start:end
                ],
                metadatas=(
                    changed_metadatas[
                        start:end
                    ]
                ),
            )

            batches += 1

    return {
        "source":
            source,

        "expected_count":
            expected_count,

        "records_found":
            records_found,

        "records_requiring_update":
            records_requiring_update,

        "already_current":
            (
                records_requiring_update
                == 0
            ),

        "applied":
            apply,

        "records_updated":
            (
                records_requiring_update
                if apply
                else 0
            ),

        "batches":
            batches,

        "metadata":
            metadata_updates,
    }


def main() -> None:

    parser = argparse.ArgumentParser(
        description=(
            "Enrich legacy technical knowledge "
            "metadata without re-embedding."
        )
    )

    parser.add_argument(
        "--apply",
        action="store_true",
        help=(
            "Apply metadata updates. "
            "Without this flag, run read-only."
        ),
    )

    parser.add_argument(
        "--persist-directory",
        default="data/chroma",
    )

    parser.add_argument(
        "--collection",
        default="technical_knowledge",
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=500,
    )

    arguments = parser.parse_args()

    if arguments.batch_size <= 0:
        raise ValueError(
            "batch-size must be greater than zero."
        )

    client = chromadb.PersistentClient(
        path=arguments.persist_directory
    )

    collection = client.get_collection(
        name=arguments.collection
    )

    collection_count_before = (
        collection.count()
    )

    migration_results = []

    for migration in MIGRATIONS:

        migration_results.append(
            enrich_source(
                collection=collection,
                source=migration[
                    "source"
                ],
                expected_count=migration[
                    "expected_count"
                ],
                metadata_updates=migration[
                    "metadata"
                ],
                apply=arguments.apply,
                batch_size=(
                    arguments.batch_size
                ),
            )
        )

    collection_count_after = (
        collection.count()
    )

    if (
        collection_count_after
        != collection_count_before
    ):
        raise RuntimeError(
            "Collection count changed during "
            "metadata enrichment."
        )

    output = {
        "mode": (
            "apply"
            if arguments.apply
            else "dry_run"
        ),
        "persist_directory":
            arguments.persist_directory,
        "collection":
            arguments.collection,
        "collection_count_before":
            collection_count_before,
        "collection_count_after":
            collection_count_after,
        "migrations":
            migration_results,
    }

    print(
        json.dumps(
            output,
            indent=2,
            default=str,
        )
    )


if __name__ == "__main__":
    main()