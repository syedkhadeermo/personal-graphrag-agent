import json

from app.agent.tools.default_tools import (
    create_default_registry,
)


def main() -> None:

    print(
        "1. Creating the default ToolRegistry..."
    )

    registry = create_default_registry()

    drug_tools = registry.list_tools(
        "drug_discovery"
    )

    print(
        json.dumps(
            drug_tools,
            indent=2,
        )
    )

    assert "rdkit_descriptors" in drug_tools
    assert "vina_docking" in drug_tools
    assert "smina_docking" in drug_tools
    assert "gromacs_md" in drug_tools

    print(
        "\n2. Executing ethanol through ToolRegistry..."
    )

    result = registry.execute(
        domain="drug_discovery",
        name="rdkit_descriptors",
        request={
            "smiles": "CCO",
            "timeout": 60,
        },
    )

    print(
        json.dumps(
            result,
            indent=2,
        )
    )

    assert isinstance(result, dict)
    assert result["status"] == "completed"
    assert result["tool"] == "RDKit"
    assert result["domain"] == "drug_discovery"
    assert result["return_code"] == 0
    assert result["valid"] is True
    assert result["input_smiles"] == "CCO"
    assert result["canonical_smiles"] == "CCO"
    assert result["molecular_formula"] == "C2H6O"
    assert result["rdkit_version"]

    descriptors = result["descriptors"]

    assert round(
        descriptors["molecular_weight"],
        3,
    ) == 46.069

    assert descriptors["h_bond_acceptors"] == 1
    assert descriptors["h_bond_donors"] == 1

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
        "\n3. Testing invalid SMILES through ToolRegistry..."
    )

    invalid_result = registry.execute(
        domain="drug_discovery",
        name="rdkit_descriptors",
        request={
            "smiles": "this-is-not-a-smiles",
            "timeout": 60,
        },
    )

    print(
        json.dumps(
            invalid_result,
            indent=2,
        )
    )

    assert isinstance(
        invalid_result,
        dict,
    )

    assert invalid_result["status"] == "failed"
    assert invalid_result["return_code"] == 2
    assert invalid_result["valid"] is False
    assert (
        invalid_result["input_smiles"]
        == "this-is-not-a-smiles"
    )
    assert invalid_result["error"]

    print(
        "\n4. Verifying unrelated domain registrations..."
    )

    summary = registry.summary()

    print(
        json.dumps(
            summary,
            indent=2,
        )
    )

    assert summary["cad_simulation"] == [
        "blender",
        "freecad",
        "openfoam",
    ]

    assert summary["cybersecurity"] == [
        "vulnerability_scan",
    ]

    print(
        "\nPASS: RDKit ToolRegistry registration passed."
    )
    print(
        "PASS: Valid SMILES execution passed through the registry."
    )
    print(
        "PASS: Invalid SMILES remained a structured tool result."
    )
    print(
        "PASS: Existing domain registrations remain intact."
    )
    print(
        "PASS: No docking, GROMACS, SQLite, SSH, or remote worker was used."
    )


if __name__ == "__main__":
    main()


def test_main() -> None:
    main()
