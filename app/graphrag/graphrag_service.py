from typing import Any

from app.generation.ollama_generator import OllamaGenerator
from app.knowledge_graph.graph_store import KnowledgeGraphStore
from app.retrieval.retrieval_service import RetrievalService


class GraphRAGService:
    """
    Combine semantic retrieval, relevant graph traversal,
    grounded generation, and source tracking.

    Graph traversal is seeded from:
        - retrieved tool metadata
        - entities explicitly mentioned in the question
        - workflow language such as candidate or workflow

    It does not add every graph edge from the selected domain.
    """

    _TOOL_NODE_MAP = {
        "rdkit":
            "rdkit",

        "admet_ai":
            "admet_ai",

        "autodock_vina":
            "autodock_vina",

        "vina":
            "autodock_vina",

        "smina":
            "smina",

        "gromacs":
            "gromacs",

        "freecad":
            "freecad",

        "openfoam":
            "openfoam",

        "blender":
            "blender",
    }

    _QUESTION_ENTITY_ALIASES = {
        "candidate_molecule": (
            "candidate molecule",
            "drug discovery workflow",
            "complete workflow",
            "end-to-end workflow",
            "end to end workflow",
        ),
        "rdkit": (
            "rdkit",
            "molecular descriptor",
            "molecular descriptors",
        ),
        "admet_ai": (
            "admet-ai",
            "admet ai",
            "admet_ai",
        ),
        "admet_ai_v2": (
            "admet-ai v2",
            "admet ai v2",
            "version 2",
        ),
        "admet_ai_v1": (
            "admet-ai v1",
            "admet ai v1",
            "version 1",
        ),
        "chemprop": (
            "chemprop",
        ),
        "dili": (
            "dili",
            "drug-induced liver injury",
            "drug induced liver injury",
        ),
        "herg": (
            "herg",
        ),
        "toxicity": (
            "toxicity",
        ),
        "cardiotoxicity_risk": (
            "cardiotoxicity",
            "cardiac toxicity",
        ),
        "autodock_vina": (
            "autodock vina",
            "vina docking",
        ),
        "smina": (
            "smina",
        ),
        "molecular_docking": (
            "molecular docking",
            "docking workflow",
        ),
        "binding_affinity": (
            "binding affinity",
            "docking score",
        ),
        "docking_pose": (
            "docking pose",
            "binding pose",
        ),
        "protein_ligand_complex": (
            "protein-ligand complex",
            "protein ligand complex",
        ),
        "molecular_dynamics": (
            "molecular dynamics",
            "md simulation",
        ),
        "gromacs": (
            "gromacs",
        ),
        "dynamic_stability": (
            "dynamic stability",
            "complex stability",
        ),
        "rmsd": (
            "rmsd",
        ),
        "rmsf": (
            "rmsf",
        ),
        "radius_of_gyration": (
            "radius of gyration",
        ),
        "hydrogen_bond_persistence": (
            "hydrogen bond persistence",
            "hydrogen-bond persistence",
        ),
        "engineering_workflow": (
            "engineering workflow",
            "cad simulation workflow",
            "freecad to openfoam",
            "freecad openfoam blender",
        ),
        "freecad": (
            "freecad",
        ),
        "parametric_cad_model": (
            "parametric cad model",
            "cad model",
        ),
        "geometry_export": (
            "geometry export",
            "exported geometry",
            "step geometry",
        ),
        "computational_domain": (
            "computational domain",
            "fluid domain",
        ),
        "openfoam_case": (
            "openfoam case",
            "case directory",
            "controldict",
            "fvschemes",
            "fvsolution",
        ),
        "computational_mesh": (
            "computational mesh",
            "cfd mesh",
            "blockmesh",
            "snappyhexmesh",
        ),
        "boundary_conditions": (
            "boundary condition",
            "boundary conditions",
        ),
        "openfoam": (
            "openfoam",
        ),
        "computational_fluid_dynamics": (
            "computational fluid dynamics",
            "cfd simulation",
            "cfd workflow",
        ),
        "fluid_flow_simulation": (
            "fluid flow simulation",
            "flow simulation",
        ),
        "simulation_results": (
            "simulation results",
            "cfd results",
        ),
        "blender": (
            "blender",
        ),
        "visualization_scene": (
            "visualization scene",
            "render scene",
            "blender scene",
        ),
        "camera": (
            "camera setup",
            "camera configuration",
        ),
        "lighting": (
            "lighting setup",
            "light objects",
        ),
        "keyframe_animation": (
            "keyframe animation",
            "keyframes",
        ),
        "rendered_animation": (
            "rendered animation",
            "animation output",
            "background rendering",
            "headless rendering",
        ),
        "authorized_security_assessment": (
            "authorized security assessment",
            "authorized assessment",
            "security assessment workflow",
        ),
        "written_authorization": (
            "written authorization",
            "written permission",
        ),
        "assessment_plan": (
            "assessment plan",
            "security assessment plan",
        ),
        "rules_of_engagement": (
            "rules of engagement",
            "roe",
        ),
        "assessment_scope": (
            "assessment scope",
            "testing scope",
        ),
        "target_systems": (
            "target systems",
            "systems in scope",
        ),
        "operational_safeguards": (
            "operational safeguards",
            "minimize operational risk",
            "safe execution",
        ),
        "incident_response_contact": (
            "incident response contact",
            "incident contact",
        ),
        "vulnerability_scan": (
            "vulnerability scan",
            "vulnerability scanning",
        ),
        "potential_finding": (
            "potential finding",
            "potential vulnerability",
        ),
        "finding_validation": (
            "finding validation",
            "validate findings",
            "finding verification",
        ),
        "confirmed_vulnerability": (
            "confirmed vulnerability",
            "validated vulnerability",
        ),
        "risk_analysis": (
            "risk analysis",
            "risk assessment",
        ),
        "remediation_recommendation": (
            "remediation recommendation",
            "remediation recommendations",
            "risk mitigation action",
        ),
        "assessment_report": (
            "assessment report",
            "security report",
            "report findings",
        ),
    }

    def __init__(
        self,
        retrieval_service: RetrievalService | None = None,
        graph_store: KnowledgeGraphStore | None = None,
        generator: OllamaGenerator | None = None,
    ):
        self.retrieval = (
            retrieval_service
            or RetrievalService()
        )

        self.graph = (
            graph_store
            or KnowledgeGraphStore()
        )

        self.generator = (
            generator
            or OllamaGenerator()
        )

    def answer(
        self,
        question: str,
        domain: str | None = None,
        n_results: int = 5,
        subdomain: str | None = None,
        tool: str | None = None,
        version: str | None = None,
        visibility: str | None = None,
        document_type: str | None = None,
        source: str | None = None,
        graph_max_depth: int = 3,
    ) -> dict:
        """
        Answer a question using retrieved text and graph context.
        """

        if not question or not question.strip():
            raise ValueError(
                "Question cannot be empty."
            )

        if graph_max_depth <= 0:
            raise ValueError(
                "graph_max_depth must be greater than zero."
            )

        retrieval_kwargs: dict[
            str,
            Any,
        ] = {
            "query":
                question.strip(),

            "n_results":
                n_results,

            "domain":
                domain,
        }

        optional_filters = {
            "subdomain": subdomain,
            "tool": tool,
            "version": version,
            "visibility": visibility,
            "document_type":
                document_type,
            "source": source,
        }

        for key, value in (
            optional_filters.items()
        ):
            if value is not None:
                retrieval_kwargs[
                    key
                ] = value

        retrieved_chunks = (
            self.retrieval.search(
                **retrieval_kwargs
            )
        )

        if not retrieved_chunks:
            return {
                "question": question,
                "answer": (
                    "No relevant information was "
                    "found in the knowledge base."
                ),
                "domain": domain,
                "retrieval_filters":
                    optional_filters,
                "retrieved_chunks": [],
                "graph_seed_nodes": [],
                "graph_context": [],
                "sources": [],
            }

        graph_seed_nodes = (
            self._identify_seed_nodes(
                question=question,
                retrieved_chunks=(
                    retrieved_chunks
                ),
                domain=domain,
            )
        )

        graph_context = (
            self._collect_graph_context(
                seed_nodes=graph_seed_nodes,
                domain=domain,
                max_depth=(
                    graph_max_depth
                ),
            )
        )

        text_context = "\n\n".join(
            chunk["text"]
            for chunk in retrieved_chunks
        )

        graph_text = ""

        if graph_context:

            graph_lines = [
                (
                    f"{relation['source']} "
                    f"{relation['relation']} "
                    f"{relation['target']} "
                    f"(depth "
                    f"{relation['depth']})"
                )
                for relation
                in graph_context
            ]

            graph_text = (
                "\n\nKnowledge graph "
                "relationships:\n"
                + "\n".join(
                    graph_lines
                )
            )

        combined_context = (
            text_context
            + graph_text
        )

        answer = self.generator.generate(
            question,
            combined_context,
        )

        sources = (
            self._build_sources(
                retrieved_chunks
            )
        )

        return {
            "question": question,
            "answer": answer,
            "domain": domain,
            "retrieval_filters": {
                key: value
                for key, value
                in optional_filters.items()
                if value is not None
            },
            "retrieved_chunks":
                retrieved_chunks,
            "graph_seed_nodes":
                graph_seed_nodes,
            "graph_context":
                graph_context,
            "sources":
                sources,
        }

    def _identify_seed_nodes(
        self,
        question: str,
        retrieved_chunks: list[dict],
        domain: str | None,
    ) -> list[str]:
        """
        Identify relevant graph starting points.
        """

        question_lower = (
            question.lower()
        )

        candidates = set()

        for (
            node_id,
            aliases,
        ) in (
            self
            ._QUESTION_ENTITY_ALIASES
            .items()
        ):

            if any(
                alias in question_lower
                for alias in aliases
            ):
                candidates.add(
                    node_id
                )

        for chunk in retrieved_chunks:

            metadata = chunk.get(
                "metadata",
                {},
            )

            metadata_tool = (
                metadata.get(
                    "tool"
                )
            )

            if metadata_tool:

                normalized_tool = (
                    str(
                        metadata_tool
                    )
                    .strip()
                    .lower()
                )

                mapped_node = (
                    self._TOOL_NODE_MAP.get(
                        normalized_tool
                    )
                )

                if mapped_node:
                    candidates.add(
                        mapped_node
                    )

            text_lower = str(
                chunk.get(
                    "text",
                    "",
                )
            ).lower()

            for (
                node_id,
                aliases,
            ) in (
                self
                ._QUESTION_ENTITY_ALIASES
                .items()
            ):

                if any(
                    alias in text_lower
                    for alias in aliases
                ):
                    candidates.add(
                        node_id
                    )

        valid_nodes = []

        for node_id in sorted(
            candidates
        ):

            node = self.graph.get_node(
                node_id
            )

            if not node:
                continue

            node_domain = (
                node.get(
                    "properties",
                    {},
                ).get(
                    "domain"
                )
            )

            if (
                domain
                and node_domain
                and node_domain != domain
            ):
                continue

            valid_nodes.append(
                node_id
            )

        return valid_nodes

    def _collect_graph_context(
        self,
        seed_nodes: list[str],
        domain: str | None,
        max_depth: int,
    ) -> list[dict]:
        """
        Traverse outward from relevant seed nodes and return
        unique, domain-safe relationships.
        """

        graph_context = []
        seen_edges = set()

        for seed_node in seed_nodes:

            relations = (
                self.graph.traverse(
                    start_node=seed_node,
                    max_depth=max_depth,
                    direction="outgoing",
                )
            )

            for relation in relations:

                if not self._edge_matches_domain(
                    relation=relation,
                    domain=domain,
                ):
                    continue

                edge_key = (
                    relation["source"],
                    relation["relation"],
                    relation["target"],
                )

                if edge_key in seen_edges:
                    continue

                seen_edges.add(
                    edge_key
                )

                graph_context.append(
                    relation
                )

        graph_context.sort(
            key=lambda edge: (
                edge.get(
                    "depth",
                    0,
                ),
                edge["source"],
                edge["relation"],
                edge["target"],
            )
        )

        return graph_context

    def _edge_matches_domain(
        self,
        relation: dict,
        domain: str | None,
    ) -> bool:
        """
        Enforce domain isolation for graph relationships.
        """

        if not domain:
            return True

        relation_domain = (
            relation.get(
                "properties",
                {},
            ).get(
                "domain"
            )
        )

        if relation_domain:
            return (
                relation_domain
                == domain
            )

        source_node = self.graph.get_node(
            relation["source"]
        )

        target_node = self.graph.get_node(
            relation["target"]
        )

        node_domains = {
            node.get(
                "properties",
                {},
            ).get(
                "domain"
            )
            for node in (
                source_node,
                target_node,
            )
            if node
        }

        node_domains.discard(
            None
        )

        return (
            not node_domains
            or node_domains
            == {
                domain
            }
        )

    @staticmethod
    def _build_sources(
        retrieved_chunks: list[dict],
    ) -> list[dict]:
        """
        Create a unique, metadata-rich source list.
        """

        sources = []
        seen_sources = set()

        for chunk in retrieved_chunks:

            metadata = chunk.get(
                "metadata",
                {},
            )

            source_key = (
                metadata.get(
                    "source"
                ),
                metadata.get(
                    "page"
                ),
                metadata.get(
                    "chunk_index"
                ),
            )

            if source_key in seen_sources:
                continue

            seen_sources.add(
                source_key
            )

            sources.append(
                {
                    "source":
                        metadata.get(
                            "source"
                        ),

                    "domain":
                        metadata.get(
                            "domain"
                        ),

                    "subdomain":
                        metadata.get(
                            "subdomain"
                        ),

                    "tool":
                        metadata.get(
                            "tool"
                        ),

                    "version":
                        metadata.get(
                            "version"
                        ),

                    "document_type":
                        metadata.get(
                            "document_type"
                        ),

                    "visibility":
                        metadata.get(
                            "visibility"
                        ),

                    "page":
                        metadata.get(
                            "page"
                        ),

                    "chunk_index":
                        metadata.get(
                            "chunk_index"
                        ),

                    "distance":
                        chunk.get(
                            "distance"
                        ),
                }
            )

        return sources

