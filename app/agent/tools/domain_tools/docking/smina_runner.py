from pathlib import Path
import subprocess
import re


class SminaRunner:
    """
    Production adapter for Smina molecular docking.

    Smina is a fork of AutoDock Vina with additional scoring
    and optimization capabilities.

    Responsible for:
    - validating docking inputs
    - executing Smina
    - capturing stdout/stderr
    - parsing docking affinities
    - returning structured results
    """

    def __init__(self, smina_executable: str = "smina"):
        self.smina_executable = smina_executable

    def run(
        self,
        receptor: str,
        ligand: str,
        center_x: float,
        center_y: float,
        center_z: float,
        size_x: float,
        size_y: float,
        size_z: float,
        output_dir: str = "data/results/docking",
        exhaustiveness: int = 8,
        num_modes: int = 9,
    ) -> dict:

        self._validate_file(receptor, "Receptor")
        self._validate_file(ligand, "Ligand")

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        ligand_name = Path(ligand).stem

        output_file = (
            output_path / f"{ligand_name}_smina_out.pdbqt"
        )

        log_file = (
            output_path / f"{ligand_name}_smina.log"
        )

        command = [
            self.smina_executable,

            "--receptor", receptor,
            "--ligand", ligand,

            "--center_x", str(center_x),
            "--center_y", str(center_y),
            "--center_z", str(center_z),

            "--size_x", str(size_x),
            "--size_y", str(size_y),
            "--size_z", str(size_z),

            "--exhaustiveness", str(exhaustiveness),
            "--num_modes", str(num_modes),

            "--out", str(output_file),
        ]

        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=False,
            )

        except FileNotFoundError as exc:
            raise RuntimeError(
                f"Smina executable not found: "
                f"{self.smina_executable}"
            ) from exc

        combined_output = (
            result.stdout
            + "\n"
            + result.stderr
        )

        log_file.write_text(
            combined_output,
            encoding="utf-8",
        )

        affinities = self._parse_affinities(
            combined_output
        )

        if result.returncode != 0:
            return {
                "tool": "Smina",
                "status": "failed",
                "return_code": result.returncode,
                "receptor": receptor,
                "ligand": ligand,
                "output_file": str(output_file),
                "log_file": str(log_file),
                "affinities": affinities,
                "error": combined_output[-3000:],
            }

        return {
            "tool": "Smina",
            "status": "completed",
            "return_code": result.returncode,
            "receptor": receptor,
            "ligand": ligand,
            "output_file": str(output_file),
            "log_file": str(log_file),
            "exhaustiveness": exhaustiveness,
            "num_modes": num_modes,
            "affinities": affinities,
            "best_affinity": (
                min(affinities)
                if affinities
                else None
            ),
        }

    @staticmethod
    def _validate_file(path: str, label: str):

        if not path or not path.strip():
            raise ValueError(
                f"{label} path cannot be empty."
            )

        file_path = Path(path)

        if not file_path.exists():
            raise FileNotFoundError(
                f"{label} file not found: {path}"
            )

        if not file_path.is_file():
            raise ValueError(
                f"{label} path is not a file: {path}"
            )

    @staticmethod
    def _parse_affinities(text: str) -> list[float]:

        affinities = []

        pattern = re.compile(
            r"^\s*\d+\s+(-?\d+(?:\.\d+)?)",
            re.MULTILINE,
        )

        for match in pattern.finditer(text):
            affinities.append(
                float(match.group(1))
            )

        return affinities