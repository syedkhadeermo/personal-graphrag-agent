from app.agent.tools.tool_registry import ToolRegistry

from app.agent.tools.domain_tools.drug_discovery_tools import (
    DrugDiscoveryTools,
)

from app.agent.tools.domain_tools.cad_tools import (
    CADSimulationTools,
)

from app.agent.tools.domain_tools.cybersecurity_tools import (
    CybersecurityTools,
)

from app.agent.tools.domain_tools.structural_fea_tools import (
    StructuralFEATools,
)


def create_default_registry() -> ToolRegistry:
    """
    Create the default tool registry for the GraphRAG agent.

    Domains:
        - drug_discovery
        - cad_simulation
        - structural_fea
        - cybersecurity
    """

    registry = ToolRegistry()

    # =========================================================
    # Drug Discovery
    # =========================================================

    drug_tools = DrugDiscoveryTools()

    registry.register(
        domain="drug_discovery",
        name="rdkit_descriptors",
        function=drug_tools.run_rdkit,
        description=(
            "RDKit molecular descriptor, canonicalization, "
            "Lipinski, and Veber assessment workflow."
        ),
    )

    registry.register(
        domain="drug_discovery",
        name="admet_prediction",
        function=drug_tools.run_admet,
        description=(
            "ADMET-AI absorption, distribution, metabolism, "
            "excretion, toxicity, structural-alert, and "
            "DrugBank-reference prediction workflow."
        ),
    )

    registry.register(
        domain="drug_discovery",
        name="vina_docking",
        function=drug_tools.run_docking,
        description=(
            "AutoDock Vina molecular docking workflow."
        ),
    )

    registry.register(
        domain="drug_discovery",
        name="smina_docking",
        function=drug_tools.run_smina,
        description=(
            "Smina molecular docking and scoring workflow."
        ),
    )

    registry.register(
        domain="drug_discovery",
        name="gromacs_md",
        function=drug_tools.run_gromacs,
        description=(
            "GROMACS molecular dynamics simulation workflow."
        ),
    )

    # =========================================================
    # CAD / Engineering Simulation
    # =========================================================

    cad_tools = CADSimulationTools()

    registry.register(
        domain="cad_simulation",
        name="freecad",
        function=cad_tools.run_freecad,
        description=(
            "Remote FreeCAD geometry generation and "
            "CAD automation workflow."
        ),
    )

    registry.register(
        domain="cad_simulation",
        name="blender",
        function=cad_tools.run_blender,
        description=(
            "Remote Blender visualization and rendering workflow."
        ),
    )

    registry.register(
        domain="cad_simulation",
        name="openfoam",
        function=cad_tools.run_openfoam,
        description=(
            "Remote OpenFOAM computational fluid dynamics "
            "simulation workflow."
        ),
    )

    # =========================================================
    # Structural FEA
    # =========================================================

    structural_fea_tools = StructuralFEATools()

    registry.register(
        domain="structural_fea",
        name="calculix",
        function=structural_fea_tools.run_calculix,
        description=(
            "Remote CalculiX structural finite element "
            "analysis workflow."
        ),
    )

    # =========================================================
    # Cybersecurity
    # =========================================================

    registry.register(
        domain="cybersecurity",
        name="vulnerability_scan",
        function=CybersecurityTools.vulnerability_scan,
        description=(
            "Authorized defensive vulnerability-assessment workflow."
        ),
    )

    return registry