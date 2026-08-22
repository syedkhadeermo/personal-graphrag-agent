import json

from collections import deque
from pathlib import Path
from typing import Any


class KnowledgeGraphStore:
    """
    Simple persistent knowledge graph for GraphRAG.

    Relationship identity is defined by:
        source + relation + target

    Relationship properties do not create duplicate edges.
    """

    def __init__(
        self,
        persist_path: str = (
            "data/knowledge_graph.json"
        ),
    ):
        self.persist_path = Path(
            persist_path
        )

        self.persist_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.nodes: dict[
            str,
            dict[str, Any],
        ] = {}

        self.edges: list[
            dict[str, Any]
        ] = []

        self._load()

    def add_node(
        self,
        node_id: str,
        node_type: str,
        properties: dict | None = None,
    ) -> None:
        """
        Add or update a graph node.
        """

        if not node_id or not node_id.strip():
            raise ValueError(
                "node_id cannot be empty."
            )

        if (
            not node_type
            or not node_type.strip()
        ):
            raise ValueError(
                "node_type cannot be empty."
            )

        normalized_id = (
            node_id.strip()
        )

        self.nodes[normalized_id] = {
            "id": normalized_id,
            "type": node_type.strip(),
            "properties": properties or {},
        }

        self._save()

    def add_edge(
        self,
        source: str,
        relation: str,
        target: str,
        properties: dict | None = None,
    ) -> None:
        """
        Create or enrich one unique directed relationship.

        Edge identity:
            source + relation + target

        Re-registering the same relationship does not create a
        duplicate, even when metadata properties differ.
        Existing properties are preserved. New property keys are
        added without overwriting existing provenance.
        """

        if not source or not source.strip():
            raise ValueError(
                "source cannot be empty."
            )

        if (
            not relation
            or not relation.strip()
        ):
            raise ValueError(
                "relation cannot be empty."
            )

        if not target or not target.strip():
            raise ValueError(
                "target cannot be empty."
            )

        normalized_source = (
            source.strip()
        )

        normalized_relation = (
            relation.strip()
        )

        normalized_target = (
            target.strip()
        )

        supplied_properties = (
            properties or {}
        )

        for edge in self.edges:

            same_identity = (
                edge["source"]
                == normalized_source
                and edge["relation"]
                == normalized_relation
                and edge["target"]
                == normalized_target
            )

            if not same_identity:
                continue

            changed = False

            existing_properties = (
                edge.setdefault(
                    "properties",
                    {},
                )
            )

            for key, value in (
                supplied_properties.items()
            ):

                if (
                    key
                    not in existing_properties
                ):
                    existing_properties[
                        key
                    ] = value

                    changed = True

            if changed:
                self._save()

            return

        edge = {
            "source":
                normalized_source,

            "relation":
                normalized_relation,

            "target":
                normalized_target,

            "properties":
                supplied_properties,
        }

        self.edges.append(
            edge
        )

        self._save()

    def get_node(
        self,
        node_id: str,
    ) -> dict | None:
        """
        Return one node by ID.
        """

        return self.nodes.get(
            node_id
        )

    def get_related(
        self,
        node_id: str,
        relation: str | None = None,
    ) -> list[dict]:
        """
        Return incoming and outgoing relationships connected
        directly to a node.

        This preserves the existing public behavior.
        """

        results = []

        for edge in self.edges:

            connected = (
                edge["source"] == node_id
                or edge["target"] == node_id
            )

            relation_matches = (
                relation is None
                or edge["relation"]
                == relation
            )

            if (
                connected
                and relation_matches
            ):
                results.append(edge)

        return results

    def get_outgoing(
        self,
        node_id: str,
        relation: str | None = None,
    ) -> list[dict]:
        """
        Return direct outgoing relationships.
        """

        return [
            edge
            for edge in self.edges
            if (
                edge["source"] == node_id
                and (
                    relation is None
                    or edge["relation"]
                    == relation
                )
            )
        ]

    def get_incoming(
        self,
        node_id: str,
        relation: str | None = None,
    ) -> list[dict]:
        """
        Return direct incoming relationships.
        """

        return [
            edge
            for edge in self.edges
            if (
                edge["target"] == node_id
                and (
                    relation is None
                    or edge["relation"]
                    == relation
                )
            )
        ]

    def traverse(
        self,
        start_node: str,
        max_depth: int = 2,
        direction: str = "outgoing",
        relation: str | None = None,
    ) -> list[dict]:
        """
        Traverse relationships breadth-first from one node.
        """

        if (
            not start_node
            or not start_node.strip()
        ):
            raise ValueError(
                "start_node cannot be empty."
            )

        if max_depth <= 0:
            raise ValueError(
                "max_depth must be greater than zero."
            )

        normalized_direction = (
            direction.strip().lower()
        )

        allowed_directions = {
            "outgoing",
            "incoming",
            "both",
        }

        if (
            normalized_direction
            not in allowed_directions
        ):
            raise ValueError(
                "direction must be outgoing, "
                "incoming, or both."
            )

        normalized_start = (
            start_node.strip()
        )

        if normalized_start not in self.nodes:
            return []

        queue = deque(
            [
                (
                    normalized_start,
                    0,
                )
            ]
        )

        visited_nodes = {
            normalized_start
        }

        seen_edges = set()
        results = []

        while queue:

            current_node, depth = (
                queue.popleft()
            )

            if depth >= max_depth:
                continue

            connected_edges = []

            if normalized_direction in {
                "outgoing",
                "both",
            }:
                connected_edges.extend(
                    self.get_outgoing(
                        current_node,
                        relation=relation,
                    )
                )

            if normalized_direction in {
                "incoming",
                "both",
            }:
                connected_edges.extend(
                    self.get_incoming(
                        current_node,
                        relation=relation,
                    )
                )

            for edge in connected_edges:

                edge_key = (
                    edge["source"],
                    edge["relation"],
                    edge["target"],
                )

                if edge_key not in seen_edges:

                    seen_edges.add(
                        edge_key
                    )

                    result_edge = dict(
                        edge
                    )

                    result_edge[
                        "depth"
                    ] = depth + 1

                    results.append(
                        result_edge
                    )

                if (
                    edge["source"]
                    == current_node
                ):
                    next_node = (
                        edge["target"]
                    )

                else:
                    next_node = (
                        edge["source"]
                    )

                if (
                    next_node
                    not in visited_nodes
                ):
                    visited_nodes.add(
                        next_node
                    )

                    queue.append(
                        (
                            next_node,
                            depth + 1,
                        )
                    )

        return results

    def node_count(
        self,
    ) -> int:
        return len(
            self.nodes
        )

    def edge_count(
        self,
    ) -> int:
        return len(
            self.edges
        )

    def reset(
        self,
    ) -> None:
        """
        Delete all nodes and relationships.
        """

        self.nodes = {}
        self.edges = []

        self._save()

    def _save(
        self,
    ) -> None:
        """
        Persist graph to disk.
        """

        data = {
            "nodes": self.nodes,
            "edges": self.edges,
        }

        with self.persist_path.open(
            "w",
            encoding="utf-8",
        ) as handle:

            json.dump(
                data,
                handle,
                indent=2,
                ensure_ascii=False,
            )

    def _load(
        self,
    ) -> None:
        """
        Load an existing graph from disk.
        """

        if not self.persist_path.exists():
            return

        with self.persist_path.open(
            "r",
            encoding="utf-8",
        ) as handle:

            data = json.load(
                handle
            )

        self.nodes = data.get(
            "nodes",
            {},
        )

        self.edges = data.get(
            "edges",
            [],
        )