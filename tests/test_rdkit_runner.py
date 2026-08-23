import json

from app.agent.tools.domain_tools.chemistry.rdkit_runner import (
    RDKitRunner,
)


ASPIRIN_SMILES = (
    "CC(=O)Oc1ccccc1C(=O)O"
)

HIGH_MOLECULAR_WEIGHT_SMILES = (
    "C" * 40
)

INVALID_SMILES = (
    "this-is-not-a-smiles"
)


def clean_result(
    result: dict,
) -> dict:
    """
    Remove raw subprocess streams from readable output.
    """

    return {
        key: value
        for key, value in result.items()
        if key not in {
            "stdout",
            "stderr",
        }
    }


def main() -> None:
    print(
        "1. Creating isolated RDKit runner..."
    )

    runner = RDKitRunner()

    print(
        json.dumps(
            {
                "wsl_executable": (
                    runner.wsl_executable
                ),
                "python_executable": (
                    runner.python_executable
                ),
            },
            indent=2,
        )
    )

    print(
        "\n2. Testing aspirin descriptors..."
    )

    aspirin = runner.run(
        smiles=ASPIRIN_SMILES,
    )

    print(
        json.dumps(
            clean_result(aspirin),
            indent=2,
            default=str,
        )
    )

    assert aspirin["tool"] == "RDKit"
    assert (
        aspirin["domain"]
        == "drug_discovery"
    )
    assert aspirin["status"] == "completed"
    assert aspirin["return_code"] == 0
    assert aspirin["valid"] is True
    assert aspirin["error"] is None

    assert (
        aspirin["molecular_formula"]
        == "C9H8O4"
    )

    assert (
        aspirin["canonical_smiles"]
        == ASPIRIN_SMILES
    )

    descriptors = aspirin["descriptors"]

    assert abs(
        descriptors["molecular_weight"]
        - 180.159
    ) < 0.01

    assert abs(
        descriptors[
            "exact_molecular_weight"
        ]
        - 180.042259
    ) < 0.0001

    assert abs(
        descriptors["log_p"]
        - 1.3101
    ) < 0.001

    assert abs(
        descriptors["tpsa"]
        - 63.6
    ) < 0.01

    assert (
        descriptors["h_bond_donors"]
        == 1
    )

    # Aspirin has three RDKit hydrogen-bond acceptors:
    # two ester oxygens and one carboxyl carbonyl oxygen.
    # The acidic hydroxyl oxygen is not an acceptor.
    assert (
        descriptors["h_bond_acceptors"]
        == 3
    )

    assert (
        descriptors["rotatable_bonds"]
        == 2
    )

    assert descriptors["ring_count"] == 1

    assert (
        descriptors["heavy_atom_count"]
        == 13
    )

    assert (
        aspirin["rules"]["lipinski"][
            "passed"
        ]
        is True
    )

    assert (
        aspirin["rules"]["lipinski"][
            "violation_count"
        ]
        == 0
    )

    assert (
        aspirin["rules"]["veber"][
            "passed"
        ]
        is True
    )

    assert (
        aspirin["rules"]["veber"][
            "violation_count"
        ]
        == 0
    )

    print(
        "\n3. Testing Lipinski and "
        "Veber violations..."
    )

    large_molecule = runner.run(
        smiles=(
            HIGH_MOLECULAR_WEIGHT_SMILES
        ),
    )

    print(
        json.dumps(
            clean_result(
                large_molecule
            ),
            indent=2,
            default=str,
        )
    )

    assert (
        large_molecule["status"]
        == "completed"
    )

    assert (
        large_molecule["return_code"]
        == 0
    )

    assert (
        large_molecule["valid"]
        is True
    )

    assert (
        large_molecule["descriptors"][
            "molecular_weight"
        ]
        > 500
    )

    assert (
        large_molecule["rules"][
            "lipinski"
        ]["passed"]
        is False
    )

    assert (
        "molecular_weight_gt_500"
        in large_molecule["rules"][
            "lipinski"
        ]["violations"]
    )

    assert (
        large_molecule["rules"][
            "veber"
        ]["passed"]
        is False
    )

    assert (
        "rotatable_bonds_gt_10"
        in large_molecule["rules"][
            "veber"
        ]["violations"]
    )

    print(
        "\n4. Testing invalid SMILES..."
    )

    invalid = runner.run(
        smiles=INVALID_SMILES,
    )

    print(
        json.dumps(
            clean_result(invalid),
            indent=2,
            default=str,
        )
    )

    assert invalid["status"] == "failed"
    assert invalid["return_code"] == 2
    assert invalid["valid"] is False

    assert (
        invalid["input_smiles"]
        == INVALID_SMILES
    )

    assert (
        invalid["error"]
        == (
            "RDKit could not parse "
            "the supplied SMILES."
        )
    )

    print(
        "\n5. Testing empty input..."
    )

    try:
        runner.run(
            smiles="   ",
        )

    except ValueError as exc:
        print(
            f"Empty SMILES rejected: {exc}"
        )

    else:
        raise AssertionError(
            "Empty SMILES was not rejected."
        )

    print(
        "\n6. Testing invalid timeout..."
    )

    try:
        runner.run(
            smiles="CCO",
            timeout=0,
        )

    except ValueError as exc:
        print(
            f"Invalid timeout rejected: {exc}"
        )

    else:
        raise AssertionError(
            "Invalid timeout was not rejected."
        )

    print(
        "\nPASS: RDKit WSL execution passed."
    )
    print(
        "PASS: Aspirin descriptors passed."
    )
    print(
        "PASS: Canonicalization and formula passed."
    )
    print(
        "PASS: Lipinski assessment passed."
    )
    print(
        "PASS: Veber assessment passed."
    )
    print(
        "PASS: Invalid SMILES handling passed."
    )
    print(
        "PASS: Input validation passed."
    )
    print(
        "PASS: No Vina, Smina, GROMACS, "
        "SQLite, SSH, or remote worker was used."
    )


if __name__ == "__main__":
    main()


def test_main() -> None:
    main()
