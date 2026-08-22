from app.agent.workers.remote_compute_worker import RemoteComputeWorker


class FreeCADRunner:
    """Remote FreeCAD execution adapter."""

    def __init__(
        self,
        host: str = "192.168.137.2",
        username: str = "syed",
    ):
        self.worker = RemoteComputeWorker(
            host=host,
            username=username,
        )

    def run(self, script_path: str) -> dict:
        if not script_path or not script_path.strip():
            raise ValueError("FreeCAD script path cannot be empty.")

        result = self.worker.run_freecad(script_path)

        return {
            "tool": "FreeCAD",
            "domain": "cad_simulation",
            "worker": self.worker.host,
            **result,
        }