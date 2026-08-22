import subprocess
from typing import Any


class RemoteComputeWorker:
    """
    Execute commands on a remote Windows compute node through SSH.

    Current use cases:
        - FreeCAD
        - Blender
        - OpenFOAM through WSL2
        - remote artifact validation
        - remote SHA-256 hashing
        - future scientific/GPU workloads
    """

    def __init__(
        self,
        host: str,
        username: str,
        ssh_executable: str = "ssh",
    ):
        if not host or not host.strip():
            raise ValueError(
                "Remote host cannot be empty."
            )

        if not username or not username.strip():
            raise ValueError(
                "Remote username cannot be empty."
            )

        self.host = host.strip()
        self.username = username.strip()
        self.ssh_executable = ssh_executable

    # =========================================================
    # Target
    # =========================================================

    @property
    def target(self) -> str:
        return f"{self.username}@{self.host}"

    # =========================================================
    # Generic remote execution
    # =========================================================

    def run(
        self,
        command: str,
        timeout: int | None = None,
    ) -> dict[str, Any]:

        if not command or not command.strip():
            raise ValueError(
                "Remote command cannot be empty."
            )

        ssh_command = [
            self.ssh_executable,
            self.target,
            command,
        ]

        try:
            result = subprocess.run(
                ssh_command,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )

        except FileNotFoundError as exc:
            raise RuntimeError(
                f"SSH executable not found: "
                f"{self.ssh_executable}"
            ) from exc

        except subprocess.TimeoutExpired as exc:

            return {
                "host": self.host,
                "username": self.username,
                "status": "timeout",
                "return_code": None,
                "command": command,
                "stdout": exc.stdout or "",
                "stderr": exc.stderr or "",
            }

        return {
            "host": self.host,
            "username": self.username,
            "status": (
                "completed"
                if result.returncode == 0
                else "failed"
            ),
            "return_code": result.returncode,
            "command": command,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }

    # =========================================================
    # Connectivity
    # =========================================================

    def ping(self) -> dict[str, Any]:
        """
        Verify SSH connectivity to the remote worker.
        """

        return self.run(
            command="hostname",
            timeout=10,
        )

    # =========================================================
    # FreeCAD
    # =========================================================

    def run_freecad(
        self,
        script_path: str,
        freecad_executable: str = (
            r"C:\Program Files\FreeCAD 1.0\bin\FreeCADCmd.exe"
        ),
        timeout: int | None = 300,
    ) -> dict[str, Any]:
        """
        Execute a FreeCAD Python script remotely.
        """

        if not script_path or not script_path.strip():
            raise ValueError(
                "FreeCAD script path cannot be empty."
            )

        command = (
            f'"{freecad_executable}" '
            f'"{script_path}"'
        )

        result = self.run(
            command=command,
            timeout=timeout,
        )

        result["tool"] = "FreeCAD"

        return result

    # =========================================================
    # Blender
    # =========================================================

    def run_blender(
        self,
        script_path: str | None = None,
        blender_executable: str = (
            r"C:\Program Files\Blender Foundation\Blender 5.0\blender.exe"
        ),
        timeout: int | None = 300,
    ) -> dict[str, Any]:
        """
        Execute Blender remotely.

        If script_path is supplied:
            run Blender in background/headless mode.

        If script_path is None:
            return Blender version information.
        """

        if script_path:
            command = (
                f'"{blender_executable}" '
                f'--background '
                f'--python "{script_path}"'
            )

        else:
            command = (
                f'"{blender_executable}" --version'
            )

        result = self.run(
            command=command,
            timeout=timeout,
        )

        result["tool"] = "Blender"

        return result

    # =========================================================
    # OpenFOAM
    # =========================================================

    def run_openfoam(
        self,
        case_directory: str,
        solver: str = "foamRun",
        run_blockmesh: bool = True,
        run_checkmesh: bool = True,
        timeout: int | None = 1200,
    ) -> dict[str, Any]:
        """
        Execute OpenFOAM inside WSL2 on the remote Windows worker.
        """

        if not case_directory or not case_directory.strip():
            raise ValueError(
                "OpenFOAM case directory cannot be empty."
            )

        if not solver or not solver.strip():
            raise ValueError(
                "OpenFOAM solver cannot be empty."
            )

        commands = [
            "source /opt/openfoam12/etc/bashrc",
            f'cd "{case_directory}"',
        ]

        if run_blockmesh:
            commands.append(
                "blockMesh"
            )

        if run_checkmesh:
            commands.append(
                "checkMesh"
            )

        commands.append(
            solver
        )

        bash_command = " && ".join(
            commands
        )

        remote_command = (
            'wsl.exe -e bash -lc '
            f'"{bash_command}"'
        )

        result = self.run(
            command=remote_command,
            timeout=timeout,
        )

        result["tool"] = "OpenFOAM"
        result["case_directory"] = (
            case_directory
        )
        result["solver"] = solver

        return result

    # =========================================================
    # Remote SHA-256
    # =========================================================

    def calculate_remote_sha256(
        self,
        path: str,
        timeout: int = 120,
    ) -> dict[str, Any]:
        """
        Calculate SHA-256 directly on the remote Windows worker.

        The artifact itself is NOT transferred to the controller.

        Returns:
            path
            host
            username
            exists
            size_bytes
            sha256
            valid
            return_code
            stdout
            stderr
            error

        PowerShell Get-FileHash is used because the remote
        compute node is Windows.

        This is appropriate for:
            - FreeCAD .FCStd / .STEP
            - Blender .blend / .png / rendered outputs
            - OpenFOAM exported/post-processing files
            - future remote scientific artifacts
        """

        if not path or not path.strip():
            raise ValueError(
                "Remote artifact path cannot be empty."
            )

        path = path.strip()

        # Escape a single quote for a PowerShell
        # single-quoted literal string.
        powershell_path = path.replace(
            "'",
            "''",
        )

        command = (
            'powershell.exe -NoProfile -NonInteractive '
            '-Command '
            '"'
            f"$p='{powershell_path}'; "
            "if (Test-Path -LiteralPath $p -PathType Leaf) { "
            "$item = Get-Item -LiteralPath $p; "
            "$hash = "
            "(Get-FileHash "
            "-Algorithm SHA256 "
            "-LiteralPath $p).Hash.ToLower(); "
            "Write-Output "
            "('ARTIFACT_HASH|' "
            "+ $hash "
            "+ '|' "
            "+ $item.Length); "
            "} else { "
            "Write-Output 'ARTIFACT_MISSING'; "
            "exit 2; "
            "}"
            '"'
        )

        result = self.run(
            command=command,
            timeout=timeout,
        )

        stdout = (
            result.get(
                "stdout",
                "",
            ).strip()
        )

        exists = (
            "ARTIFACT_HASH|" in stdout
        )

        sha256 = None
        size_bytes = 0

        if exists:

            try:
                line = next(
                    line
                    for line in stdout.splitlines()
                    if line.startswith(
                        "ARTIFACT_HASH|"
                    )
                )

                parts = line.split(
                    "|"
                )

                if len(parts) >= 3:

                    sha256 = (
                        parts[1]
                        .strip()
                        .lower()
                    )

                    size_bytes = int(
                        parts[2].strip()
                    )

            except (
                StopIteration,
                ValueError,
                IndexError,
            ):
                sha256 = None
                size_bytes = 0

        hash_valid = (
            isinstance(
                sha256,
                str,
            )
            and len(sha256) == 64
            and all(
                character
                in "0123456789abcdef"
                for character
                in sha256
            )
        )

        valid = (
            result.get(
                "return_code"
            ) == 0
            and exists
            and size_bytes > 0
            and hash_valid
        )

        error = None

        if (
            result.get(
                "status"
            )
            == "timeout"
        ):
            error = (
                "Remote SHA-256 calculation timed out."
            )

        elif not exists:
            error = (
                "Remote artifact does not exist "
                "or could not be hashed."
            )

        elif size_bytes <= 0:
            error = (
                "Remote artifact is empty."
            )

        elif not hash_valid:
            error = (
                "Remote SHA-256 result is invalid."
            )

        elif result.get(
            "return_code"
        ) != 0:
            error = (
                result.get(
                    "stderr"
                )
                or "Remote SHA-256 command failed."
            )

        return {
            "path": path,
            "host": self.host,
            "username": self.username,

            "exists": exists,

            "size_bytes": size_bytes,

            "sha256": sha256,

            "valid": valid,

            "return_code": (
                result.get(
                    "return_code"
                )
            ),

            "stdout": (
                result.get(
                    "stdout",
                    "",
                )
            ),

            "stderr": (
                result.get(
                    "stderr",
                    "",
                )
            ),

            "error": error,
        }

    # =========================================================
    # Remote artifact validation
    # =========================================================

    def validate_remote_file(
        self,
        path: str,
        expected_extensions: tuple[str, ...] | None = None,
        timeout: int = 30,
    ) -> dict[str, Any]:
        """
        Validate a file that exists on the remote Windows worker.

        Validation checks:
            - path supplied
            - file exists
            - file size > 0
            - optional extension validation

        Intended for remote artifacts such as:
            .FCStd
            .step
            .stp
            .blend
            .png
            .obj
            etc.
        """

        if not path or not path.strip():
            raise ValueError(
                "Remote artifact path cannot be empty."
            )

        path = path.strip()

        command = (
            f'if exist "{path}" '
            f'(for %I in ("{path}") do '
            f'@echo ARTIFACT_EXISTS^|%~zI) '
            f'else (echo ARTIFACT_MISSING)'
        )

        result = self.run(
            command=command,
            timeout=timeout,
        )

        stdout = (
            result.get(
                "stdout",
                "",
            )
            .strip()
        )

        exists = (
            "ARTIFACT_EXISTS" in stdout
        )

        size_bytes = 0

        if exists:

            try:
                size_text = (
                    stdout
                    .split("|")[-1]
                    .strip()
                )

                size_bytes = int(
                    size_text
                )

            except (
                ValueError,
                IndexError,
            ):
                size_bytes = 0

        # -----------------------------------------------------
        # Extension validation
        # -----------------------------------------------------

        extension_valid = True

        if expected_extensions:

            lower_path = (
                path.lower()
            )

            normalized_extensions = tuple(
                ext.lower()
                if ext.startswith(".")
                else f".{ext.lower()}"
                for ext
                in expected_extensions
            )

            extension_valid = (
                lower_path.endswith(
                    normalized_extensions
                )
            )

        # -----------------------------------------------------
        # Final validity
        # -----------------------------------------------------

        valid = (
            result.get(
                "return_code"
            ) == 0
            and exists
            and size_bytes > 0
            and extension_valid
        )

        error = None

        if result.get(
            "return_code"
        ) not in (
            None,
            0,
        ):

            error = (
                result.get(
                    "stderr"
                )
                or "Remote validation command failed."
            )

        elif not exists:

            error = (
                "Remote artifact does not exist."
            )

        elif size_bytes <= 0:

            error = (
                "Remote artifact is empty."
            )

        elif not extension_valid:

            error = (
                "Remote artifact extension "
                "is not allowed."
            )

        return {
            "path": path,
            "host": self.host,
            "username": self.username,

            "exists": exists,

            "size_bytes": size_bytes,

            "extension_valid": (
                extension_valid
            ),

            "valid": valid,

            "return_code": (
                result.get(
                    "return_code"
                )
            ),

            "stdout": (
                result.get(
                    "stdout",
                    "",
                )
            ),

            "stderr": (
                result.get(
                    "stderr",
                    "",
                )
            ),

            "error": error,
        }