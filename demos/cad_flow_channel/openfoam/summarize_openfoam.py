import json
import math
import re
from pathlib import Path


CASE_DIRECTORY = Path(
    "/mnt/c/AI_Worker/openfoam_cases/portfolio_flow_channel"
)
OUTPUT_PATH = Path(
    "/mnt/c/AI_Worker/results/cad_flow_channel/openfoam_summary.json"
)


def numeric_time_directories() -> list[tuple[float, Path]]:
    directories = []

    for path in CASE_DIRECTORY.iterdir():
        if not path.is_dir():
            continue

        try:
            time_value = float(path.name)
        except ValueError:
            continue

        directories.append(
            (time_value, path)
        )

    return sorted(directories)


def internal_field_body(
    text: str,
    field_type: str,
) -> str:
    pattern = re.compile(
        rf"internalField\s+nonuniform\s+"
        rf"List<{field_type}>\s+\d+\s*"
        rf"\((.*?)\)\s*;",
        re.DOTALL,
    )
    match = pattern.search(text)

    if not match:
        raise RuntimeError(
            f"Could not parse nonuniform {field_type} field."
        )

    return match.group(1)


def parse_vectors(path: Path) -> list[tuple[float, float, float]]:
    text = path.read_text(
        encoding="utf-8",
        errors="replace",
    )
    body = internal_field_body(
        text=text,
        field_type="vector",
    )

    vectors = [
        (
            float(match.group(1)),
            float(match.group(2)),
            float(match.group(3)),
        )
        for match in re.finditer(
            r"\(\s*"
            r"([-+0-9.eE]+)\s+"
            r"([-+0-9.eE]+)\s+"
            r"([-+0-9.eE]+)\s*"
            r"\)",
            body,
        )
    ]

    if not vectors:
        raise RuntimeError(
            "No velocity vectors were parsed."
        )

    return vectors


def parse_scalars(path: Path) -> list[float]:
    text = path.read_text(
        encoding="utf-8",
        errors="replace",
    )
    body = internal_field_body(
        text=text,
        field_type="scalar",
    )

    values = [
        float(value)
        for value in re.findall(
            r"[-+0-9.eE]+",
            body,
        )
    ]

    if not values:
        raise RuntimeError(
            "No pressure values were parsed."
        )

    return values


def statistics(values: list[float]) -> dict[str, float]:
    return {
        "minimum": min(values),
        "maximum": max(values),
        "mean": sum(values) / len(values),
    }


def main() -> None:
    time_directories = numeric_time_directories()

    if not time_directories:
        raise RuntimeError(
            "No OpenFOAM time directories were found."
        )

    final_time, final_directory = time_directories[-1]
    velocity_vectors = parse_vectors(
        final_directory / "U"
    )
    pressure_values = parse_scalars(
        final_directory / "p"
    )

    velocity_magnitudes = [
        math.sqrt(
            x * x
            + y * y
            + z * z
        )
        for x, y, z in velocity_vectors
    ]

    summary = {
        "workflow": "freecad_openfoam_blender",
        "stage": "openfoam_simulation",
        "status": "completed",
        "tool": "OpenFOAM",
        "version": "12",
        "case_directory": str(CASE_DIRECTORY),
        "final_time_seconds": final_time,
        "available_times": [
            time_value
            for time_value, _
            in time_directories
        ],
        "geometry_m": {
            "length": 0.2,
            "width": 0.05,
            "height": 0.02,
        },
        "mesh": {
            "cells": 1600,
            "divisions": [40, 10, 4],
            "cell_size_m": 0.005,
            "check_mesh": "passed",
        },
        "boundary_conditions": {
            "inlet_velocity_m_per_s": [1.0, 0.0, 0.0],
            "outlet_pressure_m2_per_s2": 0.0,
            "walls": "noSlip",
        },
        "final_fields": {
            "cell_count": len(velocity_vectors),
            "velocity_magnitude_m_per_s": statistics(
                velocity_magnitudes
            ),
            "kinematic_pressure_m2_per_s2": statistics(
                pressure_values
            ),
        },
        "artifacts": {
            "velocity_field": str(final_directory / "U"),
            "pressure_field": str(final_directory / "p"),
            "summary": str(OUTPUT_PATH),
        },
        "downstream": {
            "tool": "Blender",
            "version": "5.0.1",
            "visualization": "flow_channel_animation",
        },
    }

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    OUTPUT_PATH.write_text(
        json.dumps(
            summary,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(
        json.dumps(
            summary,
            indent=2,
        )
    )
    print("OPENFOAM_SUMMARY_OK")


if __name__ == "__main__":
    main()
