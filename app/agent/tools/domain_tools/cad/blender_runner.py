from app.agent.workers.remote_compute_worker import RemoteComputeWorker


class BlenderRunner:
    """Remote Blender execution adapter."""

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
        script_path: str | None = None,
    ) -> dict:

        result = self.worker.run_blender(
            script_path=script_path,
        )

        return {
            "tool": "Blender",
            "domain": "cad_simulation",
            "worker": self.worker.host,
            **result,
        }