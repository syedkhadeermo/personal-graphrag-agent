from app.agent.tools.domain_tools.cad.freecad_runner import FreeCADRunner
from app.agent.tools.domain_tools.cad.blender_runner import BlenderRunner
from app.agent.tools.domain_tools.cad.openfoam_runner import OpenFOAMRunner


class CADSimulationTools:
    """CAD and engineering simulation tools."""

    def __init__(self):
        self.freecad = FreeCADRunner()
        self.blender = BlenderRunner()
        self.openfoam = OpenFOAMRunner()

    def run_freecad(
        self,
        script_path: str,
    ) -> dict:

        return self.freecad.run(
            script_path=script_path,
        )

    def run_blender(
        self,
        script_path: str | None = None,
    ) -> dict:

        return self.blender.run(
            script_path=script_path,
        )

    def run_openfoam(
        self,
        case_directory: str,
        solver: str = "foamRun",
        run_blockmesh: bool = True,
        run_checkmesh: bool = True,
    ) -> dict:

        return self.openfoam.run(
            case_directory=case_directory,
            solver=solver,
            run_blockmesh=run_blockmesh,
            run_checkmesh=run_checkmesh,
        )