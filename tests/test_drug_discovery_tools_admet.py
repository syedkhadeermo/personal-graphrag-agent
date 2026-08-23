import json
from typing import Any

from app.agent.tools.domain_tools.drug_discovery_tools import (
    DrugDiscoveryTools,
)


class FakeADMETRunner:
    """
    Isolated ADMET runner replacement.

    Records calls without loading ADMET-AI, Torch, CUDA, or WSL.
    """

    def __init__(self):
        self.calls: list[dict[str, Any]] = []

    def run(
        self,
        smiles: str,
        timeout: int = 300,
    ) -> dict[str, Any]:

        self.calls.append(
            {
                "smiles": smiles,
                "timeout": timeout,
            }
        )

        return {
            "tool": "ADMET-AI",
            "domain": "drug_discovery",
            "status": "completed",
            "return_code": 0,
            "valid": True,
            "input_smiles": smiles,
            "canonical_smiles": "CCO",
            "model": {
                "name": "ADMET-AI",
                "version": "2.0.1",
                "model_generation": "v2",
                "backend": "Chemprop",
                "prediction_type": (
                    "computational_estimate"
                ),
            },
            "predictions": {
                "absorption": {
                    "HIA_Hou": 0.95,
                },
                "toxicity": {
                    "AMES": 0.08,
                    "hERG": 0.02,
                },
            },
            "endpoint_count": 52,
            "percentile_count": 52,
            "error": None,
        }


def main() -> None:

    print(
        "1. Creating DrugDiscoveryTools adapter..."
    )

    tools = DrugDiscoveryTools()
    fake_runner = FakeADMETRunner()

    tools.admet = fake_runner

    print(
        "\n2. Calling run_admet() through the adapter..."
    )

    result = tools.run_admet(
        smiles="CCO",
        timeout=180,
    )

    print(
        json.dumps(
            result,
            indent=2,
        )
    )

    assert result["status"] == "completed"
    assert result["tool"] == "ADMET-AI"
    assert (
        result["domain"]
        == "drug_discovery"
    )
    assert result["return_code"] == 0
    assert result["valid"] is True
    assert result["input_smiles"] == "CCO"
    assert (
        result["canonical_smiles"]
        == "CCO"
    )
    assert (
        result["model"]["name"]
        == "ADMET-AI"
    )
    assert (
        result["model"]["version"]
        == "2.0.1"
    )
    assert (
        result["model"][
            "prediction_type"
        ]
        == "computational_estimate"
    )
    assert (
        result["predictions"][
            "absorption"
        ][
            "HIA_Hou"
        ]
        == 0.95
    )
    assert (
        result["predictions"][
            "toxicity"
        ][
            "AMES"
        ]
        == 0.08
    )
    assert result["endpoint_count"] == 52
    assert result["percentile_count"] == 52
    assert result["error"] is None

    print(
        "\n3. Verifying delegated arguments..."
    )

    print(
        json.dumps(
            fake_runner.calls,
            indent=2,
        )
    )

    assert len(fake_runner.calls) == 1

    assert fake_runner.calls[0] == {
        "smiles": "CCO",
        "timeout": 180,
    }

    print(
        "\n4. Verifying other adapters remain available..."
    )

    expected_methods = {
        "run_admet",
        "run_rdkit",
        "run_docking",
        "run_smina",
        "run_gromacs",
    }

    available_methods = {
        name
        for name in dir(tools)
        if name.startswith("run_")
    }

    print(
        json.dumps(
            sorted(available_methods),
            indent=2,
        )
    )

    assert expected_methods.issubset(
        available_methods
    )

    print(
        "\nPASS: DrugDiscoveryTools ADMET adapter passed."
    )
    print(
        "PASS: SMILES and timeout were delegated correctly."
    )
    print(
        "PASS: Structured ADMET results were returned unchanged."
    )
    print(
        "PASS: RDKit, Vina, Smina, and GROMACS adapters remain available."
    )
    print(
        "PASS: No WSL, ADMET model, CUDA, docking, MD, SQLite, SSH, or worker was executed."
    )


if __name__ == "__main__":
    main()


def test_main() -> None:
    main()
