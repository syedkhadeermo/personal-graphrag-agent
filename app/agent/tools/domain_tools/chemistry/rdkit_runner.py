import json
import os
import subprocess
import sys

from typing import Any


class RDKitRunner:
    """
    Execute deterministic cheminformatics calculations with RDKit.

    Execution modes:
        - Windows controller: dedicated WSL Conda environment
        - Linux/Docker: current Python environment

    Initial capabilities:
        - SMILES validation
        - canonical SMILES generation
        - molecular formula
        - molecular descriptors
        - Lipinski rule assessment
        - Veber rule assessment

    The Windows path preserves dependency isolation for the
    existing Vina, Smina, GROMACS, ADMET, and toxicity
    environments.

    The Linux path allows the same tool to run inside Docker
    without relying on the Windows-only wsl executable.
    """

    _ANALYSIS_SCRIPT = r"""
import json
import sys

import rdkit

from rdkit import Chem
from rdkit.Chem import Crippen
from rdkit.Chem import Descriptors
from rdkit.Chem import Lipinski
from rdkit.Chem import QED
from rdkit.Chem import rdMolDescriptors


def emit(payload):
    print(
        json.dumps(
            payload,
            separators=(",", ":"),
            sort_keys=True,
        )
    )


input_smiles = sys.argv[1]

molecule = Chem.MolFromSmiles(
    input_smiles
)

if molecule is None:
    emit(
        {
            "status": "failed",
            "valid": False,
            "input_smiles": input_smiles,
            "error": "RDKit could not parse the supplied SMILES.",
            "rdkit_version": rdkit.__version__,
        }
    )

    raise SystemExit(2)


canonical_smiles = Chem.MolToSmiles(
    molecule,
    canonical=True,
    isomericSmiles=True,
)

molecular_weight = Descriptors.MolWt(
    molecule
)

exact_molecular_weight = (
    Descriptors.ExactMolWt(
        molecule
    )
)

log_p = Crippen.MolLogP(
    molecule
)

tpsa = rdMolDescriptors.CalcTPSA(
    molecule
)

h_bond_donors = (
    Lipinski.NumHDonors(
        molecule
    )
)

h_bond_acceptors = (
    Lipinski.NumHAcceptors(
        molecule
    )
)

rotatable_bonds = (
    Lipinski.NumRotatableBonds(
        molecule
    )
)

ring_count = (
    Lipinski.RingCount(
        molecule
    )
)

heavy_atom_count = (
    Lipinski.HeavyAtomCount(
        molecule
    )
)

fraction_csp3 = (
    rdMolDescriptors.CalcFractionCSP3(
        molecule
    )
)

molecular_formula = (
    rdMolDescriptors.CalcMolFormula(
        molecule
    )
)

qed_value = QED.qed(
    molecule
)

lipinski_violations = []

if molecular_weight > 500:
    lipinski_violations.append(
        "molecular_weight_gt_500"
    )

if log_p > 5:
    lipinski_violations.append(
        "logp_gt_5"
    )

if h_bond_donors > 5:
    lipinski_violations.append(
        "h_bond_donors_gt_5"
    )

if h_bond_acceptors > 10:
    lipinski_violations.append(
        "h_bond_acceptors_gt_10"
    )

veber_violations = []

if rotatable_bonds > 10:
    veber_violations.append(
        "rotatable_bonds_gt_10"
    )

if tpsa > 140:
    veber_violations.append(
        "tpsa_gt_140"
    )

emit(
    {
        "status": "completed",
        "valid": True,
        "input_smiles": input_smiles,
        "canonical_smiles": canonical_smiles,
        "molecular_formula": molecular_formula,
        "rdkit_version": rdkit.__version__,
        "descriptors": {
            "molecular_weight": round(
                molecular_weight,
                6,
            ),
            "exact_molecular_weight": round(
                exact_molecular_weight,
                6,
            ),
            "log_p": round(
                log_p,
                6,
            ),
            "tpsa": round(
                tpsa,
                6,
            ),
            "h_bond_donors": (
                h_bond_donors
            ),
            "h_bond_acceptors": (
                h_bond_acceptors
            ),
            "rotatable_bonds": (
                rotatable_bonds
            ),
            "ring_count": ring_count,
            "heavy_atom_count": (
                heavy_atom_count
            ),
            "fraction_csp3": round(
                fraction_csp3,
                6,
            ),
            "qed": round(
                qed_value,
                6,
            ),
        },
        "rules": {
            "lipinski": {
                "passed": (
                    len(
                        lipinski_violations
                    )
                    == 0
                ),
                "violation_count": len(
                    lipinski_violations
                ),
                "violations": (
                    lipinski_violations
                ),
            },
            "veber": {
                "passed": (
                    len(
                        veber_violations
                    )
                    == 0
                ),
                "violation_count": len(
                    veber_violations
                ),
                "violations": (
                    veber_violations
                ),
            },
        },
        "error": None,
    }
)
"""

    def __init__(
        self,
        wsl_executable: str = "wsl",
        python_executable: str = (
            "/home/sdkad/miniconda3/"
            "envs/cheminformatics/bin/python"
        ),
        local_python_executable: str | None = None,
    ):
        if (
            not wsl_executable
            or not wsl_executable.strip()
        ):
            raise ValueError(
                "wsl_executable cannot be empty."
            )

        if (
            not python_executable
            or not python_executable.strip()
        ):
            raise ValueError(
                "python_executable cannot be empty."
            )

        selected_local_python = (
            local_python_executable
            or sys.executable
        )

        if (
            not selected_local_python
            or not selected_local_python.strip()
        ):
            raise ValueError(
                "local_python_executable cannot be empty."
            )

        self.wsl_executable = (
            wsl_executable.strip()
        )

        self.python_executable = (
            python_executable.strip()
        )

        self.local_python_executable = (
            selected_local_python.strip()
        )

        self.execution_mode = (
            "wsl"
            if os.name == "nt"
            else "local"
        )

    def run(
        self,
        smiles: str,
        timeout: int = 60,
    ) -> dict[str, Any]:
        """
        Analyze one SMILES string with RDKit.

        Returns a structured result suitable for ToolRegistry,
        JobManager, API, Docker, and artifact/report generation.
        """

        if not smiles or not smiles.strip():
            raise ValueError(
                "SMILES cannot be empty."
            )

        if timeout <= 0:
            raise ValueError(
                "timeout must be greater than zero."
            )

        normalized_smiles = smiles.strip()

        command = self._build_command(
            normalized_smiles
        )

        environment = (
            self.python_executable
            if self.execution_mode == "wsl"
            else self.local_python_executable
        )

        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
                timeout=timeout,
            )

        except FileNotFoundError as exc:

            if self.execution_mode == "wsl":
                raise RuntimeError(
                    "WSL executable was not found: "
                    f"{self.wsl_executable}"
                ) from exc

            raise RuntimeError(
                "Local Python executable was not found: "
                f"{self.local_python_executable}"
            ) from exc

        except subprocess.TimeoutExpired as exc:
            raise TimeoutError(
                "RDKit analysis timed out after "
                f"{timeout} seconds."
            ) from exc

        payload = self._extract_payload(
            completed.stdout
        )

        if payload is None:
            error_text = (
                completed.stderr.strip()
                or completed.stdout.strip()
                or "RDKit returned no structured output."
            )

            return {
                "tool": "RDKit",
                "domain": "drug_discovery",
                "status": "failed",
                "return_code": (
                    completed.returncode
                ),
                "valid": False,
                "input_smiles": (
                    normalized_smiles
                ),
                "execution_mode": (
                    self.execution_mode
                ),
                "environment": environment,
                "stdout": completed.stdout,
                "stderr": completed.stderr,
                "error": error_text[-3000:],
            }

        return {
            "tool": "RDKit",
            "domain": "drug_discovery",
            "return_code": completed.returncode,
            "execution_mode": self.execution_mode,
            "environment": environment,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            **payload,
        }

    def _build_command(
        self,
        smiles: str,
    ) -> list[str]:
        """
        Build the platform-specific subprocess command.
        """

        if self.execution_mode == "wsl":
            return [
                self.wsl_executable,
                "-e",
                self.python_executable,
                "-c",
                self._ANALYSIS_SCRIPT,
                smiles,
            ]

        return [
            self.local_python_executable,
            "-c",
            self._ANALYSIS_SCRIPT,
            smiles,
        ]

    @staticmethod
    def _extract_payload(
        stdout: str,
    ) -> dict[str, Any] | None:
        """
        Extract the final JSON object from subprocess output.

        Reading the final valid JSON line keeps the adapter safe
        if a scientific dependency prints informational messages.
        """

        if not stdout:
            return None

        lines = [
            line.strip()
            for line in stdout.splitlines()
            if line.strip()
        ]

        for line in reversed(lines):
            try:
                payload = json.loads(
                    line
                )

            except json.JSONDecodeError:
                continue

            if isinstance(payload, dict):
                return payload

        return None