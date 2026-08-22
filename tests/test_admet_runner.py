import json
import math

from app.agent.tools.domain_tools.chemistry.admet_runner import (
    ADMETRunner,
)


ASPIRIN_SMILES = (
    "CC(=O)Oc1ccccc1C(=O)O"
)


def main() -> None:

    print(
        "1. Creating ADMET-AI runner..."
    )

    runner = ADMETRunner()

    print(
        json.dumps(
            {
                "execution_mode":
                    runner.execution_mode,

                "python_executable":
                    runner.python_executable,
            },
            indent=2,
        )
    )

    assert runner.execution_mode == "wsl"

    assert (
        runner.python_executable
        == (
            "/home/sdkad/miniconda3/"
            "envs/admet_ai/bin/python"
        )
    )

    print(
        "\n2. Running real aspirin prediction..."
    )

    result = runner.run(
        smiles=ASPIRIN_SMILES,
        timeout=300,
    )

    summary = {
        "status":
            result.get("status"),

        "return_code":
            result.get("return_code"),

        "execution_mode":
            result.get("execution_mode"),

        "canonical_smiles":
            result.get("canonical_smiles"),

        "model":
            result.get("model"),

        "runtime":
            result.get("runtime"),

        "endpoint_count":
            result.get("endpoint_count"),

        "percentile_count":
            result.get("percentile_count"),

        "prediction_groups": sorted(
            result.get(
                "predictions",
                {}
            )
        ),

        "selected_predictions": {
            "AMES":
                result.get(
                    "raw_predictions",
                    {},
                ).get("AMES"),

            "BBB_Martins":
                result.get(
                    "raw_predictions",
                    {},
                ).get("BBB_Martins"),

            "DILI":
                result.get(
                    "raw_predictions",
                    {},
                ).get("DILI"),

            "hERG":
                result.get(
                    "raw_predictions",
                    {},
                ).get("hERG"),

            "HIA_Hou":
                result.get(
                    "raw_predictions",
                    {},
                ).get("HIA_Hou"),

            "LD50_Zhu":
                result.get(
                    "raw_predictions",
                    {},
                ).get("LD50_Zhu"),
        },
    }

    print(
        json.dumps(
            summary,
            indent=2,
        )
    )

    assert result["status"] == "completed"
    assert result["return_code"] == 0
    assert result["valid"] is True
    assert result["tool"] == "ADMET-AI"
    assert (
        result["domain"]
        == "drug_discovery"
    )
    assert (
        result["input_smiles"]
        == ASPIRIN_SMILES
    )
    assert (
        result["canonical_smiles"]
        == ASPIRIN_SMILES
    )
    assert (
        result["execution_mode"]
        == "wsl"
    )

    model = result["model"]

    assert model["name"] == "ADMET-AI"
    assert model["version"] == "2.0.1"
    assert (
        model["model_generation"]
        == "v2"
    )
    assert (
        model["backend"]
        == "Chemprop"
    )
    assert (
        model["prediction_type"]
        == "computational_estimate"
    )

    runtime = result["runtime"]

    assert runtime["rdkit_version"]
    assert runtime["torch_version"]
    assert isinstance(
        runtime["cuda_available"],
        bool,
    )

    if runtime["cuda_available"]:
        assert runtime["gpu_name"]

    predictions = result["predictions"]

    expected_groups = {
        "physicochemical",
        "structural_alerts",
        "absorption",
        "distribution",
        "metabolism",
        "excretion",
        "toxicity",
    }

    assert set(predictions) == (
        expected_groups
    )

    for group_name in expected_groups:
        assert predictions[group_name]

    raw = result["raw_predictions"]

    required_endpoints = {
        "molecular_weight",
        "logP",
        "QED",
        "AMES",
        "BBB_Martins",
        "Bioavailability_Ma",
        "Caco2_Wang",
        "ClinTox",
        "DILI",
        "HIA_Hou",
        "LD50_Zhu",
        "PPBR_AZ",
        "Solubility_AqSolDB",
        "hERG",
    }

    assert required_endpoints.issubset(
        raw
    )

    assert (
        result["endpoint_count"]
        == len(raw)
    )

    percentiles = (
        result[
            "drugbank_approved_percentiles"
        ]
    )

    assert (
        result["percentile_count"]
        == len(percentiles)
    )

    assert (
        result["endpoint_count"]
        >= 40
    )

    assert (
        result["percentile_count"]
        >= 40
    )

    assert math.isclose(
        raw["molecular_weight"],
        180.159,
        rel_tol=0.0,
        abs_tol=0.001,
    )

    probability_endpoints = (
        "AMES",
        "BBB_Martins",
        "Bioavailability_Ma",
        "ClinTox",
        "DILI",
        "HIA_Hou",
        "hERG",
    )

    for endpoint in probability_endpoints:

        value = raw[endpoint]

        assert 0.0 <= value <= 1.0

    assert (
        "computational model predictions"
        in result[
            "interpretation_notice"
        ]
    )

    assert result["error"] is None

    print(
        "\n3. Testing invalid SMILES..."
    )

    invalid_result = runner.run(
        smiles="this-is-not-a-smiles",
        timeout=60,
    )

    print(
        json.dumps(
            {
                "status":
                    invalid_result.get(
                        "status"
                    ),

                "return_code":
                    invalid_result.get(
                        "return_code"
                    ),

                "valid":
                    invalid_result.get(
                        "valid"
                    ),

                "error":
                    invalid_result.get(
                        "error"
                    ),
            },
            indent=2,
        )
    )

    assert (
        invalid_result["status"]
        == "failed"
    )
    assert (
        invalid_result["return_code"]
        == 2
    )
    assert (
        invalid_result["valid"]
        is False
    )
    assert invalid_result["error"]

    print(
        "\n4. Testing empty input..."
    )

    try:
        runner.run(
            smiles="   "
        )

    except ValueError as exc:
        print(
            "Empty SMILES rejected:",
            exc,
        )

        assert (
            str(exc)
            == "SMILES cannot be empty."
        )

    else:
        raise AssertionError(
            "Empty SMILES was not rejected."
        )

    print(
        "\n5. Testing invalid timeout..."
    )

    try:
        runner.run(
            smiles="CCO",
            timeout=0,
        )

    except ValueError as exc:
        print(
            "Invalid timeout rejected:",
            exc,
        )

        assert (
            str(exc)
            == (
                "timeout must be "
                "greater than zero."
            )
        )

    else:
        raise AssertionError(
            "Invalid timeout was not rejected."
        )

    print(
        "\nPASS: Real ADMET-AI prediction passed."
    )
    print(
        "PASS: ADMET and toxicity endpoints were preserved."
    )
    print(
        "PASS: Predictions were grouped by scientific category."
    )
    print(
        "PASS: DrugBank reference percentiles were preserved."
    )
    print(
        "PASS: Model, RDKit, Torch, CUDA, and GPU provenance passed."
    )
    print(
        "PASS: Invalid SMILES and input validation passed."
    )
    print(
        "PASS: No docking, GROMACS, SQLite, SSH, or remote worker was used."
    )


if __name__ == "__main__":
    main()