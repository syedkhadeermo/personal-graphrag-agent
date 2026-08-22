from app.knowledge_graph.graph_store import KnowledgeGraphStore


class KnowledgeGraphBuilder:
    """
    Build deterministic knowledge graphs from document chunks
    and curated scientific workflow definitions.

    The curated workflow provides stable relationships for
    GraphRAG traversal. Document extraction continues to enrich
    the same graph with source-derived entities.
    """

    def __init__(
        self,
        graph_store: KnowledgeGraphStore | None = None,
    ):
        self.graph = (
            graph_store
            or KnowledgeGraphStore()
        )

    def build_from_chunk(
        self,
        text: str,
        domain: str,
        source: str = "unknown",
    ) -> dict:
        """
        Extract foundational entities and relationships from
        one document chunk.
        """

        if not text or not text.strip():
            raise ValueError(
                "Text cannot be empty."
            )

        if not domain or not domain.strip():
            raise ValueError(
                "Domain cannot be empty."
            )

        text_lower = text.lower()

        entities = []
        relations = []

        def add_entity(
            node_id: str,
            node_type: str,
        ):
            if node_id not in entities:

                self.graph.add_node(
                    node_id,
                    node_type,
                    {
                        "domain":
                            domain.strip(),

                        "source":
                            source,
                    },
                )

                entities.append(
                    node_id
                )

        def add_relation(
            source_id: str,
            relation: str,
            target_id: str,
        ):
            edge = {
                "source": source_id,
                "relation": relation,
                "target": target_id,
            }

            self.graph.add_edge(
                source_id,
                relation,
                target_id,
            )

            if edge not in relations:
                relations.append(edge)

        # =====================================================
        # Drug discovery
        # =====================================================

        if "rdkit" in text_lower:
            add_entity(
                "rdkit",
                "software",
            )

        if (
            "molecular descriptor"
            in text_lower
        ):
            add_entity(
                "molecular_descriptors",
                "scientific_concept",
            )

        if "admet-ai" in text_lower:
            add_entity(
                "admet_ai",
                "software",
            )

        if "chemprop" in text_lower:
            add_entity(
                "chemprop",
                "machine_learning_model",
            )

        if "dili" in text_lower:
            add_entity(
                "dili",
                "toxicity_endpoint",
            )

        if "herg" in text_lower:
            add_entity(
                "herg",
                "toxicity_endpoint",
            )

        if "toxicity" in text_lower:
            add_entity(
                "toxicity",
                "admet_category",
            )

        if "cardiotoxicity" in text_lower:
            add_entity(
                "cardiotoxicity_risk",
                "risk_concept",
            )

        if "autodock vina" in text_lower:
            add_entity(
                "autodock_vina",
                "software",
            )

        if "smina" in text_lower:
            add_entity(
                "smina",
                "software",
            )

        if "molecular docking" in text_lower:
            add_entity(
                "molecular_docking",
                "method",
            )

        if "docking pose" in text_lower:
            add_entity(
                "docking_pose",
                "artifact",
            )

        if "binding affinity" in text_lower:
            add_entity(
                "binding_affinity",
                "scientific_measure",
            )

        if "gromacs" in text_lower:
            add_entity(
                "gromacs",
                "software",
            )

        if "molecular dynamics" in text_lower:
            add_entity(
                "molecular_dynamics",
                "method",
            )

        if "rmsd" in text_lower:
            add_entity(
                "rmsd",
                "simulation_metric",
            )

        if "rmsf" in text_lower:
            add_entity(
                "rmsf",
                "simulation_metric",
            )

        if (
            "radius of gyration"
            in text_lower
        ):
            add_entity(
                "radius_of_gyration",
                "simulation_metric",
            )

        if (
            "hydrogen bond"
            in text_lower
        ):
            add_entity(
                "hydrogen_bond_persistence",
                "simulation_metric",
            )

        if (
            "rdkit" in entities
            and "molecular_descriptors"
            in entities
        ):
            add_relation(
                "rdkit",
                "calculates",
                "molecular_descriptors",
            )

        if (
            "admet_ai" in entities
            and "chemprop" in entities
        ):
            add_relation(
                "admet_ai",
                "uses",
                "chemprop",
            )

        if (
            "admet_ai" in entities
            and "dili" in entities
        ):
            add_relation(
                "admet_ai",
                "predicts",
                "dili",
            )

        if (
            "admet_ai" in entities
            and "herg" in entities
        ):
            add_relation(
                "admet_ai",
                "predicts",
                "herg",
            )

        if (
            "dili" in entities
            and "toxicity" in entities
        ):
            add_relation(
                "dili",
                "belongs_to",
                "toxicity",
            )

        if (
            "herg" in entities
            and "cardiotoxicity_risk"
            in entities
        ):
            add_relation(
                "herg",
                "indicates",
                "cardiotoxicity_risk",
            )

        if (
            "autodock_vina" in entities
            and "molecular_docking"
            in entities
        ):
            add_relation(
                "autodock_vina",
                "performs",
                "molecular_docking",
            )

        if (
            "smina" in entities
            and "molecular_docking"
            in entities
        ):
            add_relation(
                "smina",
                "performs",
                "molecular_docking",
            )

        if (
            "molecular_docking" in entities
            and "docking_pose" in entities
        ):
            add_relation(
                "molecular_docking",
                "produces",
                "docking_pose",
            )

        if (
            "molecular_docking" in entities
            and "binding_affinity"
            in entities
        ):
            add_relation(
                "molecular_docking",
                "estimates",
                "binding_affinity",
            )

        if (
            "gromacs" in entities
            and "molecular_dynamics"
            in entities
        ):
            add_relation(
                "gromacs",
                "performs",
                "molecular_dynamics",
            )

        simulation_metrics = (
            "rmsd",
            "rmsf",
            "radius_of_gyration",
            "hydrogen_bond_persistence",
        )

        if "molecular_dynamics" in entities:

            for metric in simulation_metrics:

                if metric in entities:
                    add_relation(
                        "molecular_dynamics",
                        "measures",
                        metric,
                    )

        # =====================================================
        # CAD / engineering simulation
        # =====================================================

        if "openfoam" in text_lower:
            add_entity(
                "openfoam",
                "software",
            )

        if (
            "computational fluid dynamics"
            in text_lower
        ):
            add_entity(
                "computational_fluid_dynamics",
                "method",
            )

        if "cfd" in text_lower:
            add_entity(
                "cfd",
                "method",
            )

        if (
            "openfoam" in entities
            and "computational_fluid_dynamics"
            in entities
        ):
            add_relation(
                "openfoam",
                "performs",
                "computational_fluid_dynamics",
            )

        if (
            "openfoam" in entities
            and "cfd" in entities
        ):
            add_relation(
                "openfoam",
                "used_for",
                "cfd",
            )

        # =====================================================
        # Cybersecurity
        # =====================================================

        if "network security" in text_lower:
            add_entity(
                "network_security",
                "concept",
            )

        if "security automation" in text_lower:
            add_entity(
                "security_automation",
                "concept",
            )

        if "monitoring" in text_lower:
            add_entity(
                "security_monitoring",
                "process",
            )

        if (
            "security_automation" in entities
            and "security_monitoring"
            in entities
        ):
            add_relation(
                "security_automation",
                "supports",
                "security_monitoring",
            )

        return {
            "domain": domain.strip(),
            "source": source,
            "entities": entities,
            "relations": relations,
        }

    def build_drug_discovery_workflow(
        self,
        source: str = (
            "curated_drug_discovery_workflow"
        ),
    ) -> dict:
        """
        Build the canonical RDKit → ADMET → docking →
        molecular-dynamics workflow graph.

        This curated workflow supplies stable traversal paths.
        Retrieved documentation supplies supporting evidence and
        source-specific context.
        """

        domain = "drug_discovery"

        nodes = {
            "candidate_molecule":
                "molecule",

            "rdkit":
                "software",

            "molecular_descriptors":
                "scientific_concept",

            "admet_ai":
                "software",

            "admet_ai_v2":
                "model_version",

            "admet_ai_v1":
                "model_version",

            "chemprop":
                "machine_learning_model",

            "dili":
                "toxicity_endpoint",

            "herg":
                "toxicity_endpoint",

            "toxicity":
                "admet_category",

            "cardiotoxicity_risk":
                "risk_concept",

            "autodock_vina":
                "software",

            "smina":
                "software",

            "molecular_docking":
                "method",

            "binding_affinity":
                "scientific_measure",

            "docking_pose":
                "artifact",

            "protein_ligand_complex":
                "scientific_system",

            "molecular_dynamics":
                "method",

            "gromacs":
                "software",

            "dynamic_stability":
                "scientific_concept",

            "rmsd":
                "simulation_metric",

            "rmsf":
                "simulation_metric",

            "radius_of_gyration":
                "simulation_metric",

            "hydrogen_bond_persistence":
                "simulation_metric",
        }

        relationships = [
            (
                "candidate_molecule",
                "analyzed_by",
                "rdkit",
            ),
            (
                "rdkit",
                "calculates",
                "molecular_descriptors",
            ),
            (
                "candidate_molecule",
                "screened_by",
                "admet_ai",
            ),
            (
                "admet_ai",
                "implemented_as",
                "admet_ai_v2",
            ),
            (
                "admet_ai_v2",
                "differs_from",
                "admet_ai_v1",
            ),
            (
                "admet_ai",
                "uses",
                "chemprop",
            ),
            (
                "admet_ai",
                "predicts",
                "dili",
            ),
            (
                "admet_ai",
                "predicts",
                "herg",
            ),
            (
                "dili",
                "belongs_to",
                "toxicity",
            ),
            (
                "herg",
                "indicates",
                "cardiotoxicity_risk",
            ),
            (
                "candidate_molecule",
                "docked_with",
                "autodock_vina",
            ),
            (
                "candidate_molecule",
                "docked_with",
                "smina",
            ),
            (
                "autodock_vina",
                "performs",
                "molecular_docking",
            ),
            (
                "smina",
                "performs",
                "molecular_docking",
            ),
            (
                "molecular_docking",
                "estimates",
                "binding_affinity",
            ),
            (
                "molecular_docking",
                "produces",
                "docking_pose",
            ),
            (
                "docking_pose",
                "forms",
                "protein_ligand_complex",
            ),
            (
                "protein_ligand_complex",
                "evaluated_by",
                "molecular_dynamics",
            ),
            (
                "molecular_dynamics",
                "performed_by",
                "gromacs",
            ),
            (
                "molecular_dynamics",
                "evaluates",
                "dynamic_stability",
            ),
            (
                "molecular_dynamics",
                "measures",
                "rmsd",
            ),
            (
                "molecular_dynamics",
                "measures",
                "rmsf",
            ),
            (
                "molecular_dynamics",
                "measures",
                "radius_of_gyration",
            ),
            (
                "molecular_dynamics",
                "measures",
                "hydrogen_bond_persistence",
            ),
        ]

        nodes_before = (
            self.graph.node_count()
        )

        edges_before = (
            self.graph.edge_count()
        )

        for node_id, node_type in (
            nodes.items()
        ):
            self.graph.add_node(
                node_id=node_id,
                node_type=node_type,
                properties={
                    "domain": domain,
                    "source": source,
                    "curated": True,
                },
            )

        for (
            source_id,
            relation,
            target_id,
        ) in relationships:

            self.graph.add_edge(
                source=source_id,
                relation=relation,
                target=target_id,
                properties={
                    "domain": domain,
                    "source": source,
                    "curated": True,
                },
            )

        return {
            "domain": domain,
            "source": source,
            "nodes_total": len(nodes),
            "relationships_total": len(
                relationships
            ),
            "nodes_created": (
                self.graph.node_count()
                - nodes_before
            ),
            "relationships_created": (
                self.graph.edge_count()
                - edges_before
            ),
            "node_count": (
                self.graph.node_count()
            ),
            "edge_count": (
                self.graph.edge_count()
            ),
        }

    def build_cad_workflow(
        self,
        source: str = "curated_cad_simulation_workflow",
    ) -> dict:
        """
        Build the canonical FreeCAD -> OpenFOAM -> Blender
        engineering workflow graph.
        """

        domain = "cad_simulation"

        nodes = {
            "engineering_workflow": "workflow",
            "freecad": "software",
            "parametric_cad_model": "engineering_model",
            "geometry_export": "artifact",
            "computational_domain": "simulation_domain",
            "openfoam_case": "simulation_case",
            "computational_mesh": "simulation_mesh",
            "boundary_conditions": "simulation_configuration",
            "openfoam": "software",
            "computational_fluid_dynamics": "method",
            "fluid_flow_simulation": "simulation",
            "simulation_results": "simulation_artifact",
            "blender": "software",
            "visualization_scene": "visualization_artifact",
            "camera": "scene_component",
            "lighting": "scene_component",
            "keyframe_animation": "animation_method",
            "rendered_animation": "rendered_artifact",
        }

        relationships = [
            (
                "engineering_workflow",
                "modeled_with",
                "freecad",
            ),
            (
                "freecad",
                "creates",
                "parametric_cad_model",
            ),
            (
                "parametric_cad_model",
                "exported_as",
                "geometry_export",
            ),
            (
                "geometry_export",
                "defines",
                "computational_domain",
            ),
            (
                "computational_domain",
                "prepared_as",
                "openfoam_case",
            ),
            (
                "openfoam_case",
                "contains",
                "computational_mesh",
            ),
            (
                "openfoam_case",
                "configured_with",
                "boundary_conditions",
            ),
            (
                "openfoam_case",
                "simulated_by",
                "openfoam",
            ),
            (
                "openfoam",
                "performs",
                "computational_fluid_dynamics",
            ),
            (
                "computational_fluid_dynamics",
                "executes",
                "fluid_flow_simulation",
            ),
            (
                "fluid_flow_simulation",
                "produces",
                "simulation_results",
            ),
            (
                "simulation_results",
                "visualized_in",
                "visualization_scene",
            ),
            (
                "visualization_scene",
                "assembled_by",
                "blender",
            ),
            (
                "visualization_scene",
                "configured_with",
                "camera",
            ),
            (
                "visualization_scene",
                "configured_with",
                "lighting",
            ),
            (
                "visualization_scene",
                "animated_with",
                "keyframe_animation",
            ),
            (
                "keyframe_animation",
                "rendered_as",
                "rendered_animation",
            ),
            (
                "blender",
                "produces",
                "rendered_animation",
            ),
        ]

        nodes_before = self.graph.node_count()
        edges_before = self.graph.edge_count()

        for node_id, node_type in nodes.items():
            self.graph.add_node(
                node_id=node_id,
                node_type=node_type,
                properties={
                    "domain": domain,
                    "source": source,
                    "curated": True,
                },
            )

        for source_id, relation, target_id in relationships:
            self.graph.add_edge(
                source=source_id,
                relation=relation,
                target=target_id,
                properties={
                    "domain": domain,
                    "source": source,
                    "curated": True,
                },
            )

        return {
            "domain": domain,
            "source": source,
            "nodes_total": len(nodes),
            "relationships_total": len(relationships),
            "nodes_created": (
                self.graph.node_count()
                - nodes_before
            ),
            "relationships_created": (
                self.graph.edge_count()
                - edges_before
            ),
            "node_count": self.graph.node_count(),
            "edge_count": self.graph.edge_count(),
        }

    def build_cybersecurity_workflow(
        self,
        source: str = "curated_cybersecurity_workflow",
    ) -> dict:
        """
        Build an authorization-bounded defensive security
        assessment workflow based on NIST SP 800-115.
        """

        domain = "cybersecurity"

        nodes = {
            "authorized_security_assessment": "workflow",
            "written_authorization": "authorization",
            "assessment_plan": "planning_artifact",
            "rules_of_engagement": "governance_artifact",
            "assessment_scope": "governance_concept",
            "target_systems": "assessment_target",
            "operational_safeguards": "risk_control",
            "incident_response_contact": "operational_role",
            "vulnerability_scan": "assessment_method",
            "potential_finding": "security_finding",
            "finding_validation": "assessment_process",
            "confirmed_vulnerability": "security_finding",
            "risk_analysis": "risk_process",
            "remediation_recommendation": "remediation_artifact",
            "assessment_report": "report_artifact",
        }

        relationships = [
            (
                "authorized_security_assessment",
                "requires",
                "written_authorization",
            ),
            (
                "authorized_security_assessment",
                "governed_by",
                "assessment_plan",
            ),
            (
                "assessment_plan",
                "includes",
                "rules_of_engagement",
            ),
            (
                "assessment_plan",
                "defines",
                "assessment_scope",
            ),
            (
                "assessment_scope",
                "identifies",
                "target_systems",
            ),
            (
                "assessment_plan",
                "requires",
                "operational_safeguards",
            ),
            (
                "assessment_plan",
                "identifies",
                "incident_response_contact",
            ),
            (
                "target_systems",
                "assessed_by",
                "vulnerability_scan",
            ),
            (
                "vulnerability_scan",
                "identifies",
                "potential_finding",
            ),
            (
                "potential_finding",
                "verified_by",
                "finding_validation",
            ),
            (
                "finding_validation",
                "confirms",
                "confirmed_vulnerability",
            ),
            (
                "confirmed_vulnerability",
                "evaluated_by",
                "risk_analysis",
            ),
            (
                "risk_analysis",
                "informs",
                "remediation_recommendation",
            ),
            (
                "remediation_recommendation",
                "documented_in",
                "assessment_report",
            ),
            (
                "confirmed_vulnerability",
                "reported_in",
                "assessment_report",
            ),
        ]

        nodes_before = self.graph.node_count()
        edges_before = self.graph.edge_count()

        for node_id, node_type in nodes.items():
            self.graph.add_node(
                node_id=node_id,
                node_type=node_type,
                properties={
                    "domain": domain,
                    "source": source,
                    "curated": True,
                    "authorized_only": True,
                },
            )

        for source_id, relation, target_id in relationships:
            self.graph.add_edge(
                source=source_id,
                relation=relation,
                target=target_id,
                properties={
                    "domain": domain,
                    "source": source,
                    "curated": True,
                    "authorized_only": True,
                },
            )

        return {
            "domain": domain,
            "source": source,
            "nodes_total": len(nodes),
            "relationships_total": len(relationships),
            "nodes_created": (
                self.graph.node_count()
                - nodes_before
            ),
            "relationships_created": (
                self.graph.edge_count()
                - edges_before
            ),
            "node_count": self.graph.node_count(),
            "edge_count": self.graph.edge_count(),
        }

    def build_all_domain_workflows(
        self,
    ) -> dict:
        """
        Build all curated domain workflows idempotently.
        """

        nodes_before = self.graph.node_count()
        edges_before = self.graph.edge_count()

        workflows = {
            "drug_discovery": (
                self.build_drug_discovery_workflow()
            ),
            "cad_simulation": (
                self.build_cad_workflow()
            ),
            "cybersecurity": (
                self.build_cybersecurity_workflow()
            ),
        }

        return {
            "domains": list(workflows),
            "workflows": workflows,
            "nodes_created": (
                self.graph.node_count()
                - nodes_before
            ),
            "relationships_created": (
                self.graph.edge_count()
                - edges_before
            ),
            "node_count": self.graph.node_count(),
            "edge_count": self.graph.edge_count(),
        }
