from app.agent.workers.remote_compute_worker import RemoteComputeWorker


class OpenFOAMRunner:
    """Remote OpenFOAM execution adapter through WSL2."""

    def __init__(
        self,
        host: str = "192.168.137.2",
        username: str = "syed",
    ):
        self.worker = RemoteComputeWorker(
            host=host,
            username=username,
        )

    def run(
        self,
        case_directory: str,
        solver: str = "foamRun",
        run_blockmesh: bool = True,
        run_checkmesh: bool = True,
        timeout: int = 1200,
    ) -> dict:

        if not case_directory or not case_directory.strip():
            raise ValueError(
                "OpenFOAM case directory cannot be empty."
            )

        commands = [
            "source /opt/openfoam12/etc/bashrc",
            f'cd "{case_directory}"',
        ]

        if run_blockmesh:
            commands.append("blockMesh")

        if run_checkmesh:
            commands.append("checkMesh")

        commands.append(solver)

        bash_command = " && ".join(commands)

        remote_command = (
            'wsl.exe -e bash -lc '
            f'"{bash_command}"'
        )

        result = self.worker.run(
            command=remote_command,
            timeout=timeout,
        )

        return {
            "tool": "OpenFOAM",
            "domain": "cad_simulation",
            "worker": self.worker.host,
            "case_directory": case_directory,
            "solver": solver,
            **result,
        }