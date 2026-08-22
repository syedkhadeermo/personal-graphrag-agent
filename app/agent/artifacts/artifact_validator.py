from pathlib import Path
from typing import Any


class ArtifactValidator:
    """
    Validate artifacts produced by computational jobs.

    Initial validation:
        - path supplied
        - file exists
        - path is a file
        - file is not empty
        - optional extension validation
    """

    @staticmethod
    def validate_local_file(
        path: str,
        expected_extensions: tuple[str, ...] | None = None,
    ) -> dict[str, Any]:

        result = {
            "path": path,
            "exists": False,
            "is_file": False,
            "size_bytes": 0,
            "extension_valid": True,
            "valid": False,
            "error": None,
        }

        try:
            file_path = Path(path)

            result["exists"] = file_path.exists()

            if not file_path.exists():
                result["error"] = "Artifact does not exist."
                return result

            result["is_file"] = file_path.is_file()

            if not file_path.is_file():
                result["error"] = "Artifact path is not a file."
                return result

            size_bytes = file_path.stat().st_size

            result["size_bytes"] = size_bytes

            if size_bytes <= 0:
                result["error"] = "Artifact file is empty."
                return result

            if expected_extensions:
                suffix = file_path.suffix.lower()

                normalized = tuple(
                    ext.lower()
                    if ext.startswith(".")
                    else f".{ext.lower()}"
                    for ext in expected_extensions
                )

                result["extension_valid"] = (
                    suffix in normalized
                )

                if not result["extension_valid"]:
                    result["error"] = (
                        f"Unexpected artifact extension: "
                        f"{file_path.suffix}"
                    )

                    return result

            result["valid"] = True

            return result

        except Exception as exc:

            result["error"] = str(exc)

            return result