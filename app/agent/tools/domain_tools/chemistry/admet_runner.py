import json
import os
import subprocess
import sys

from typing import Any


class ADMETRunner:
    """
    Execute ADMET-AI predictions for one molecule.

    Execution modes:
        - Windows controller: dedicated WSL Conda environment
        - Linux: current Python environment, if ADMET-AI is installed

    The runner:
        - validates and canonicalizes SMILES with RDKit
        - executes the pretrained ADMET-AI v2 model
        - preserves all raw prediction values
        - groups predictions by scientific category
        - preserves DrugBank reference percentiles
        - records model and compute-environment metadata

    Prediction values are computational estimates. They must not
    be represented as experimental or clinical conclusions.
    """

    _PREDICTION_SCRIPT = r"""
import importlib.metadata
import json
import sys

import rdkit
import torch

from admet_ai import ADMETModel
from rdkit import Chem


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
            "model": {
                "name": "ADMET-AI",
                "version": importlib.metadata.version(
                    "admet-ai"
                ),
            },
            "rdkit_version": rdkit.__version__,
        }
    )

    raise SystemExit(2)


canonical_smiles = Chem.MolToSmiles(
    molecule,
    canonical=True,
    isomericSmiles=True,
)

cuda_available = torch.cuda.is_available()

if cuda_available:
    torch.set_float32_matmul_precision(
        "high"
    )

model = ADMETModel()

raw_result = model.predict(
    smiles=canonical_smiles
)

raw_predictions = {
    str(name): float(value)
    for name, value in raw_result.items()
}

percentile_suffix = (
    "_drugbank_approved_percentile"
)

drugbank_percentiles = {
    name.removesuffix(
        percentile_suffix
    ): value
    for name, value in raw_predictions.items()
    if name.endswith(
        percentile_suffix
    )
}

base_predictions = {
    name: value
    for name, value in raw_predictions.items()
    if not name.endswith(
        percentile_suffix
    )
}

group_definitions = {
    "physicochemical": (
        "molecular_weight",
        "logP",
        "hydrogen_bond_acceptors",
        "hydrogen_bond_donors",
        "Lipinski",
        "QED",
        "stereo_centers",
        "tpsa",
        "Lipophilicity_AstraZeneca",
    ),
    "structural_alerts": (
        "PAINS_alert",
        "BRENK_alert",
        "NIH_alert",
    ),
    "absorption": (
        "Bioavailability_Ma",
        "Caco2_Wang",
        "HIA_Hou",
        "PAMPA_NCATS",
        "Pgp_Broccatelli",
        "Solubility_AqSolDB",
    ),
    "distribution": (
        "BBB_Martins",
        "HydrationFreeEnergy_FreeSolv",
        "PPBR_AZ",
        "VDss_Lombardo",
    ),
    "metabolism": (
        "CYP1A2_Veith",
        "CYP2C19_Veith",
        "CYP2C9_Substrate_CarbonMangels",
        "CYP2C9_Veith",
        "CYP2D6_Substrate_CarbonMangels",
        "CYP2D6_Veith",
        "CYP3A4_Substrate_CarbonMangels",
        "CYP3A4_Veith",
    ),
    "excretion": (
        "Clearance_Hepatocyte_AZ",
        "Clearance_Microsome_AZ",
        "Half_Life_Obach",
    ),
    "toxicity": (
        "AMES",
        "Carcinogens_Lagunin",
        "ClinTox",
        "DILI",
        "LD50_Zhu",
        "Skin_Reaction",
        "hERG",
        "NR-AR-LBD",
        "NR-AR",
        "NR-AhR",
        "NR-Aromatase",
        "NR-ER-LBD",
        "NR-ER",
        "NR-PPAR-gamma",
        "SR-ARE",
        "SR-ATAD5",
        "SR-HSE",
        "SR-MMP",
        "SR-p53",
    ),
}

prediction_groups = {
    group_name: {
        endpoint: base_predictions[
            endpoint
        ]
        for endpoint in endpoints
        if endpoint in base_predictions
    }
    for group_name, endpoints
    in group_definitions.items()
}

grouped_names = {
    endpoint
    for endpoints in group_definitions.values()
    for endpoint in endpoints
}

unclassified_predictions = {
    name: value
    for name, value in base_predictions.items()
    if name not in grouped_names
}

gpu_name = None

if cuda_available:
    gpu_name = torch.cuda.get_device_name(
        0
    )

emit(
    {
        "status": "completed",
        "valid": True,
        "input_smiles": input_smiles,
        "canonical_smiles": canonical_smiles,
        "model": {
            "name": "ADMET-AI",
            "version": importlib.metadata.version(
                "admet-ai"
            ),
            "model_generation": "v2",
            "backend": "Chemprop",
            "prediction_type": (
                "computational_estimate"
            ),
        },
        "runtime": {
            "rdkit_version": rdkit.__version__,
            "torch_version": torch.__version__,
            "cuda_available": cuda_available,
            "cuda_version": torch.version.cuda,
            "gpu_name": gpu_name,
        },
        "predictions": prediction_groups,
        "unclassified_predictions": (
            unclassified_predictions
        ),
        "drugbank_approved_percentiles": (
            drugbank_percentiles
        ),
        "raw_predictions": base_predictions,
        "endpoint_count": len(
            base_predictions
        ),
        "percentile_count": len(
            drugbank_percentiles
        ),
        "interpretation_notice": (
            "ADMET-AI values are computational model "
            "predictions and are not experimental or "
            "clinical conclusions."
        ),
        "error": None,
    }
)
"""

    def __init__(
        self,
        wsl_executable: str = "wsl",
        python_executable: str = (
            "/home/sdkad/miniconda3/"
            "envs/admet_ai/bin/python"
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
        timeout: int = 300,
    ) -> dict[str, Any]:
        """
        Predict ADMET and toxicity properties for one SMILES.

        The first prediction may be slower because the pretrained
        model ensemble must be loaded.
        """

        if not smiles or not smiles.strip():
            raise ValueError(
                "SMILES cannot be empty."
            )

        if timeout <= 0:
            raise ValueError(
                "timeout must be greater than zero."
            )

        normalized_smiles = (
            smiles.strip()
        )

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
                "ADMET-AI prediction timed out after "
                f"{timeout} seconds."
            ) from exc

        payload = self._extract_payload(
            completed.stdout
        )

        if payload is None:
            error_text = (
                completed.stderr.strip()
                or completed.stdout.strip()
                or (
                    "ADMET-AI returned no "
                    "structured output."
                )
            )

            return {
                "tool": "ADMET-AI",
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
                "stdout_tail": self._tail(
                    completed.stdout
                ),
                "stderr_tail": self._tail(
                    completed.stderr
                ),
                "error": error_text[-3000:],
            }

        return {
            "tool": "ADMET-AI",
            "domain": "drug_discovery",
            "return_code": completed.returncode,
            "execution_mode": self.execution_mode,
            "environment": environment,
            "stdout_tail": self._tail(
                completed.stdout
            ),
            "stderr_tail": self._tail(
                completed.stderr
            ),
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
                self._PREDICTION_SCRIPT,
                smiles,
            ]

        return [
            self.local_python_executable,
            "-c",
            self._PREDICTION_SCRIPT,
            smiles,
        ]

    @staticmethod
    def _extract_payload(
        stdout: str,
    ) -> dict[str, Any] | None:
        """
        Extract the final valid JSON object from subprocess output.
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

    @staticmethod
    def _tail(
        text: str,
        limit: int = 5000,
    ) -> str:
        """
        Limit captured scientific-process logs stored in SQLite.
        """

        if not text:
            return ""

        return text[-limit:]