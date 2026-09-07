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

        result = self.worker.run_openfoam(
            case_directory=case_directory,
            solver=solver,
            run_blockmesh=run_blockmesh,
            run_checkmesh=run_checkmesh,
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