import json
from typing import Any

from app.agent.tools.domain_tools.drug_discovery_tools import (
    DrugDiscoveryTools,
)


class FakeRDKitRunner:
    """
    Isolated RDKit runner replacement.

    Records calls without starting WSL or importing RDKit.
    """

    def __init__(self):
        self.calls: list[dict[str, Any]] = []

    def run(
        self,
        smiles: str,
        timeout: int = 60,
    ) -> dict[str, Any]:

        self.calls.append(
            {
                "smiles": smiles,
                "timeout": timeout,
            }
        )

        return {
            "status": "completed",
            "tool": "RDKit",
            "domain": "drug_discovery",
            "return_code": 0,
            "valid": True,
            "input_smiles": smiles,
            "canonical_smiles": "CCO",
            "molecular_formula": "C2H6O",
            "descriptors": {
                "molecular_weight": 46.069,
                "h_bond_acceptors": 1,
                "h_bond_donors": 1,
            },
            "rules": {
                "lipinski": {
                    "passed": True,
                    "violation_count": 0,
                    "violations": [],
                },
                "veber": {
                    "passed": True,
                    "violation_count": 0,
                    "violations": [],
                },
            },
            "error": None,
        }


def main() -> None:

    print(
        "1. Creating DrugDiscoveryTools adapter..."
    )

    tools = DrugDiscoveryTools()
    fake_runner = FakeRDKitRunner()

    tools.rdkit = fake_runner

    print(
        "\n2. Calling run_rdkit() through the adapter..."
    )

    result = tools.run_rdkit(
        smiles="CCO",
        timeout=45,
    )

    print(
        json.dumps(
            result,
            indent=2,
        )
    )

    assert result["status"] == "completed"
    assert result["tool"] == "RDKit"
    assert result["domain"] == "drug_discovery"
    assert result["return_code"] == 0
    assert result["valid"] is True
    assert result["input_smiles"] == "CCO"
    assert result["canonical_smiles"] == "CCO"
    assert (
        result["molecular_formula"]
        == "C2H6O"
    )
    assert (
        result["descriptors"]["molecular_weight"]
        == 46.069
    )
    assert (
        result["rules"]["lipinski"]["passed"]
        is True
    )
    assert (
        result["rules"]["veber"]["passed"]
        is True
    )
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
        "timeout": 45,
    }

    print(
        "\n4. Verifying the other tool adapters remain available..."
    )

    expected_methods = {
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
        "\nPASS: DrugDiscoveryTools RDKit adapter passed."
    )
    print(
        "PASS: SMILES and timeout were delegated correctly."
    )
    print(
        "PASS: Structured RDKit results were returned unchanged."
    )
    print(
        "PASS: Vina, Smina, and GROMACS adapters remain available."
    )
    print(
        "PASS: No WSL, RDKit, docking, MD, SQLite, SSH, or worker was executed."
    )


if __name__ == "__main__":
    main()