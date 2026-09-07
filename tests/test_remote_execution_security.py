"""Security regression tests for remote command construction."""

import pytest

from app.agent.workers.remote_compute_worker import RemoteComputeWorker


class RecordingWorker(RemoteComputeWorker):
    def __init__(self):
        super().__init__(host="192.168.137.2", username="worker")
        self.commands: list[str] = []

    def run(self, command: str, timeout: int | None = None) -> dict:
        self.commands.append(command)
        return {
            "host": self.host,
            "username": self.username,
            "status": "completed",
            "return_code": 0,
            "command": command,
            "stdout": "",
            "stderr": "",
        }


@pytest.mark.parametrize(
    "solver",
    ["foamRun && whoami", "foamRun; whoami", "$(whoami)", "../foamRun"],
)
def test_openfoam_rejects_solver_injection(solver: str) -> None:
    worker = RecordingWorker()

    with pytest.raises(ValueError):
        worker.run_openfoam(
            "/mnt/c/AI_Worker/openfoam_cases/cavity",
            solver=solver,
        )

    assert worker.commands == []


@pytest.mark.parametrize(
    "case_directory",
    [
        "/mnt/c/AI_Worker/openfoam_cases/cavity;whoami",
        "/mnt/c/AI_Worker/openfoam_cases/$(whoami)",
        "/mnt/c/AI_Worker/openfoam_cases/../outside",
        "/tmp/cavity",
    ],
)
def test_openfoam_rejects_untrusted_case_paths(case_directory: str) -> None:
    worker = RecordingWorker()

    with pytest.raises(ValueError):
        worker.run_openfoam(case_directory)

    assert worker.commands == []


@pytest.mark.parametrize(
    "script_path",
    [
        r"C:\AI_Worker\jobs\demo.py & whoami",
        r"C:\AI_Worker\jobs\..\outside.py",
        r"C:\Windows\Temp\demo.py",
        r"C:\AI_Worker\jobs\demo.blend",
    ],
)
def test_cad_runners_reject_untrusted_script_paths(script_path: str) -> None:
    worker = RecordingWorker()

    with pytest.raises(ValueError):
        worker.run_freecad(script_path)

    with pytest.raises(ValueError):
        worker.run_blender(script_path)

    assert worker.commands == []


def test_artifact_operations_reject_command_injection() -> None:
    worker = RecordingWorker()
    malicious_path = r"C:\AI_Worker\results\file.png & whoami"

    with pytest.raises(ValueError):
        worker.validate_remote_file(malicious_path)

    with pytest.raises(ValueError):
        worker.calculate_remote_sha256(malicious_path)

    assert worker.commands == []


def test_valid_remote_commands_reach_execution_boundary() -> None:
    worker = RecordingWorker()

    worker.run_freecad(r"C:\AI_Worker\jobs\model.py")
    worker.run_blender(r"C:\AI_Worker\jobs\render.py")
    worker.run_openfoam(
        "/mnt/c/AI_Worker/openfoam_cases/cavity",
        solver="foamRun",
    )

    assert len(worker.commands) == 3
    assert "model.py" in worker.commands[0]
    assert "render.py" in worker.commands[1]
    assert "foamRun" in worker.commands[2]
