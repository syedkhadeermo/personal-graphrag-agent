from app.agent.tools.domain_tools.chemistry.admet_runner import (
    ADMETRunner,
)
from app.agent.tools.domain_tools.chemistry.rdkit_runner import (
    RDKitRunner,
)
from app.agent.tools.domain_tools.docking.smina_runner import (
    SminaRunner,
)
from app.agent.tools.domain_tools.docking.vina_runner import (
    VinaRunner,
)
from app.agent.tools.domain_tools.md.gromacs_runner import (
    GromacsRunner,
)


class DrugDiscoveryTools:
    """
    Computational drug-discovery tool adapter.

    Available tools:
        - RDKit molecular descriptors
        - ADMET-AI ADMET and toxicity prediction
        - AutoDock Vina docking
        - Smina docking
        - GROMACS molecular dynamics
    """

    def __init__(self):
        self.rdkit = RDKitRunner()
        self.admet = ADMETRunner()
        self.vina = VinaRunner()
        self.smina = SminaRunner()
        self.gromacs = GromacsRunner()

    # =========================================================
    # RDKit
    # =========================================================

    def run_rdkit(
        self,
        smiles: str,
        timeout: int = 60,
    ) -> dict:
        """
        Calculate molecular descriptors and drug-likeness rules.
        """

        return self.rdkit.run(
            smiles=smiles,
            timeout=timeout,
        )

    # =========================================================
    # ADMET-AI
    # =========================================================

    def run_admet(
        self,
        smiles: str,
        timeout: int = 300,
    ) -> dict:
        """
        Predict ADMET and toxicity properties using ADMET-AI.

        Returned values are computational predictions and must
        not be represented as experimental or clinical results.
        """

        return self.admet.run(
            smiles=smiles,
            timeout=timeout,
        )

    # =========================================================
    # AutoDock Vina
    # =========================================================

    def run_docking(
        self,
        receptor: str,
        ligand: str,
        center_x: float,
        center_y: float,
        center_z: float,
        size_x: float,
        size_y: float,
        size_z: float,
        exhaustiveness: int = 8,
        num_modes: int = 9,
    ) -> dict:

        return self.vina.run(
            receptor=receptor,
            ligand=ligand,
            center_x=center_x,
            center_y=center_y,
            center_z=center_z,
            size_x=size_x,
            size_y=size_y,
            size_z=size_z,
            exhaustiveness=exhaustiveness,
            num_modes=num_modes,
        )

    # =========================================================
    # Smina
    # =========================================================

    def run_smina(
        self,
        receptor: str,
        ligand: str,
        center_x: float,
        center_y: float,
        center_z: float,
        size_x: float,
        size_y: float,
        size_z: float,
        exhaustiveness: int = 8,
        num_modes: int = 9,
    ) -> dict:

        return self.smina.run(
            receptor=receptor,
            ligand=ligand,
            center_x=center_x,
            center_y=center_y,
            center_z=center_z,
            size_x=size_x,
            size_y=size_y,
            size_z=size_z,
            exhaustiveness=exhaustiveness,
            num_modes=num_modes,
        )

    # =========================================================
    # GROMACS
    # =========================================================

    def run_gromacs(
        self,
        mdp: str,
        structure: str,
        topology: str,
        output_tpr: str,
        nsteps: int | None = None,
        use_gpu: bool = False,
        output_dir: str = "data/results/gromacs",
    ) -> dict:

        return self.gromacs.run(
            mdp=mdp,
            structure=structure,
            topology=topology,
            output_tpr=output_tpr,
            nsteps=nsteps,
            use_gpu=use_gpu,
            output_dir=output_dir,
        )