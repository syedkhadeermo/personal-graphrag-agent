from pathlib import Path
import subprocess


class GromacsRunner:
    """
    Production adapter for GROMACS.

    Responsible for:
    - validating GROMACS input files
    - running gmx grompp
    - optionally running gmx mdrun
    - capturing stdout/stderr
    - returning structured results
    """

    def __init__(self, gmx_executable: str = "gmx"):
        self.gmx_executable = gmx_executable

    def run(
        self,
        mdp: str,
        structure: str,
        topology: str,
        output_tpr: str,
        nsteps: int | None = None,
        use_gpu: bool = False,
        output_dir: str = "data/results/gromacs",
    ) -> dict:

        self._validate_file(mdp, "MDP")
        self._validate_file(structure, "Structure")
        self._validate_file(topology, "Topology")

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        tpr_path = Path(output_tpr)

        if not tpr_path.is_absolute():
            tpr_path = output_path / tpr_path.name

        log_file = output_path / f"{tpr_path.stem}.log"

        grompp_command = [
            self.gmx_executable,
            "grompp",
            "-f",
            mdp,
            "-c",
            structure,
            "-p",
            topology,
            "-o",
            str(tpr_path),
        ]

        grompp = self._run_command(grompp_command)

        if grompp["return_code"] != 0:
            log_file.write_text(
                grompp["output"],
                encoding="utf-8",
            )

            return {
                "tool": "GROMACS",
                "stage": "grompp",
                "status": "failed",
                "return_code": grompp["return_code"],
                "tpr_file": str(tpr_path),
                "log_file": str(log_file),
                "error": grompp["output"][-3000:],
            }

        mdrun_command = [
            self.gmx_executable,
            "mdrun",
            "-s",
            str(tpr_path),
        ]

        if use_gpu:
            mdrun_command.extend(
                [
                    "-nb",
                    "gpu",
                ]
            )
        else:
            mdrun_command.extend(
                [
                    "-nb",
                    "cpu",
                ]
            )

        if nsteps is not None:
            mdrun_command.extend(
                [
                    "-nsteps",
                    str(nsteps),
                ]
            )

        mdrun = self._run_command(mdrun_command)

        combined_output = (
            grompp["output"]
            + "\n"
            + mdrun["output"]
        )

        log_file.write_text(
            combined_output,
            encoding="utf-8",
        )

        return {
            "tool": "GROMACS",
            "stage": "mdrun",
            "status": (
                "completed"
                if mdrun["return_code"] == 0
                else "failed"
            ),
            "return_code": mdrun["return_code"],
            "tpr_file": str(tpr_path),
            "log_file": str(log_file),
            "nsteps": nsteps,
            "gpu_requested": use_gpu,
            "error": (
                None
                if mdrun["return_code"] == 0
                else mdrun["output"][-3000:]
            ),
        }

    def _run_command(self, command: list[str]) -> dict:

        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=False,
            )

        except FileNotFoundError as exc:
            raise RuntimeError(
                f"GROMACS executable not found: "
                f"{self.gmx_executable}"
            ) from exc

        output = (
            result.stdout
            + "\n"
            + result.stderr
        )

        return {
            "return_code": result.returncode,
            "output": output,
        }

    @staticmethod
    def _validate_file(
        path: str,
        label: str,
    ) -> None:

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