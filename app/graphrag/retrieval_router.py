import re
from dataclasses import asdict, dataclass
from typing import Literal

RetrievalMode = Literal["auto", "vector", "graph"]


@dataclass(frozen=True)
class RoutingDecision:
    requested_mode: RetrievalMode
    selected_mode: Literal["vector", "graph"]
    confidence: float
    signals: tuple[str, ...]
    entity_nodes: tuple[str, ...]

    def to_dict(self) -> dict:
        return asdict(self)


class RetrievalRouter:
    """Conservatively select vector or graph-augmented retrieval."""

    _WORKFLOW_PATTERNS = (
        r"\bworkflow\b",
        r"\bpipeline\b",
        r"\bsteps?\b",
        r"\bbefore\b",
        r"\bafter\b",
        r"\bprogress(?:es|ion)?\b",
        r"\bnext\b",
        r"\bend[- ]to[- ]end\b",
        r"\bfrom\b.+\bto\b",
    )
    _RELATIONSHIP_PATTERNS = (
        r"\brelat(?:e|ed|es|ionship)\b",
        r"\bconnect(?:s|ed|ion)?\b",
        r"\bdepend(?:s|ed|ency)?\b",
        r"\bleads? to\b",
        r"\baffect(?:s|ed)?\b",
        r"\brequired after\b",
        r"\bturned into\b",
        r"\bbecome(?:s)?\b",
    )
    _BOUNDARY_PATTERNS = (
        r"\bguarantee(?:s|d)?\b",
        r"\bestablish(?:es|ed)? that\b",
        r"\bprove(?:s|d)? that\b",
        r"\bsufficient to conclude\b",
    )
    _DIRECT_PATTERNS = (
        r"\baccording to\b",
        r"\bdocumentation\b",
        r"\bwhat (?:is|does|are)\b",
        r"\bwhich (?:function|command|parameter)\b",
        r"\bdefault\b",
        r"\bcalculate(?:s|d)?\b",
        r"\bparses?\b",
    )

    def __init__(self, entity_aliases: dict[str, tuple[str, ...]]):
        self.entity_aliases = entity_aliases

    @staticmethod
    def _matches(text: str, patterns: tuple[str, ...]) -> bool:
        return any(re.search(pattern, text) for pattern in patterns)

    def _entity_nodes(self, question: str) -> tuple[str, ...]:
        question_lower = question.lower()
        return tuple(
            sorted(
                node_id
                for node_id, aliases in self.entity_aliases.items()
                if any(alias in question_lower for alias in aliases)
            )
        )

    def route(
        self,
        question: str,
        requested_mode: RetrievalMode = "auto",
    ) -> RoutingDecision:
        if requested_mode not in {"auto", "vector", "graph"}:
            raise ValueError("retrieval_mode must be 'auto', 'vector', or 'graph'.")
        if not question or not question.strip():
            raise ValueError("Question cannot be empty.")

        entity_nodes = self._entity_nodes(question)
        if requested_mode != "auto":
            return RoutingDecision(
                requested_mode=requested_mode,
                selected_mode=requested_mode,
                confidence=1.0,
                signals=("explicit_override",),
                entity_nodes=entity_nodes,
            )

        question_lower = question.lower()
        workflow = self._matches(question_lower, self._WORKFLOW_PATTERNS)
        relationship = self._matches(question_lower, self._RELATIONSHIP_PATTERNS)
        boundary = self._matches(question_lower, self._BOUNDARY_PATTERNS)
        direct = self._matches(question_lower, self._DIRECT_PATTERNS)
        signals = []
        if workflow:
            signals.append("workflow_language")
        if relationship:
            signals.append("relationship_language")
        if boundary:
            signals.append("boundary_question")
        if direct:
            signals.append("direct_evidence_question")
        if len(entity_nodes) >= 2:
            signals.append("multiple_question_entities")

        use_graph = (
            boundary
            or (workflow and bool(entity_nodes))
            or (relationship and len(entity_nodes) >= 2 and not direct)
            or (len(entity_nodes) >= 3 and not direct)
        )
        if use_graph:
            confidence = 0.9 if boundary else 0.85 if workflow else 0.75
            return RoutingDecision(
                requested_mode="auto",
                selected_mode="graph",
                confidence=confidence,
                signals=tuple(signals),
                entity_nodes=entity_nodes,
            )

        if not signals:
            signals.append("conservative_vector_default")
        return RoutingDecision(
            requested_mode="auto",
            selected_mode="vector",
            confidence=0.85 if direct else 0.65,
            signals=tuple(signals),
            entity_nodes=entity_nodes,
        )
