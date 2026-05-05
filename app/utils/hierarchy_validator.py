"""
Hierarchy Validator: Validates parent-child relationships in document nodes.
Ensures no orphans, cycles, or consistency issues before DB commit.
"""

import logging
from typing import Set
from dataclasses import dataclass

from app.adapters.base import IngestedNode

logger = logging.getLogger(__name__)


@dataclass
class ValidationReport:
    """Report from hierarchy validation."""

    is_valid: bool
    errors: list[str]
    warnings: list[str]
    node_count: int
    orphaned_nodes: int
    hierarchical_nodes: int  # Nodes with parent_id
    depth: int  # Max tree depth


class HierarchyValidator:
    """Validates document node hierarchies before persistence."""

    @staticmethod
    def validate(nodes: list[IngestedNode]) -> ValidationReport:
        """
        Validate node hierarchy for consistency.

        Args:
            nodes: List of IngestedNode objects to validate

        Returns:
            ValidationReport with detailed findings
        """
        errors = []
        warnings = []

        if not nodes:
            return ValidationReport(
                is_valid=False,
                errors=["No nodes provided"],
                warnings=[],
                node_count=0,
                orphaned_nodes=0,
                hierarchical_nodes=0,
                depth=0,
            )

        # Check 1: Duplicate node IDs in O(N)
        node_ids = [node.node_id for node in nodes]
        seen_ids = set()
        duplicates = []
        for nid in node_ids:
            if nid in seen_ids:
                duplicates.append(nid)
            else:
                seen_ids.add(nid)

        if duplicates:
            errors.append(f"Duplicate node IDs: {duplicates[:5]}")

        # Check 2: Parent references validity
        node_id_set = set(node_ids)
        orphaned = []
        for node in nodes:
            if node.parent_id:
                if node.parent_id not in node_id_set:
                    orphaned.append((node.node_id, node.parent_id))

        if orphaned:
            errors.append(f"Orphaned parent references: {orphaned[:5]}")

        # Check 3: Cycles detection
        cycles = HierarchyValidator._detect_cycles(nodes)
        if cycles:
            errors.append(f"Parent-child cycles detected: {cycles[:3]}")

        # Check 4: Text content
        empty_nodes = [n.node_id for n in nodes if not n.text or not n.text.strip()]
        if empty_nodes:
            warnings.append(f"Empty nodes (no text): {len(empty_nodes)}")

        # Check 5: Object validity
        for node in nodes:
            if not node.node_id or not node.document_id:
                errors.append(f"Node missing required ID fields: {node}")

        # Calculate statistics
        hierarchical_nodes = sum(1 for n in nodes if n.parent_id)
        depth = HierarchyValidator._calculate_depth(nodes)

        is_valid = len(errors) == 0

        report = ValidationReport(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            node_count=len(nodes),
            orphaned_nodes=len(orphaned),
            hierarchical_nodes=hierarchical_nodes,
            depth=depth,
        )

        if is_valid:
            logger.info(f"✓ Node hierarchy valid: {len(nodes)} nodes, depth {depth}, {hierarchical_nodes} hierarchical")
        else:
            logger.error(f"✗ Node hierarchy invalid: {len(errors)} errors, {len(warnings)} warnings")

        return report

    @staticmethod
    def _detect_cycles(nodes: list[IngestedNode]) -> list[tuple[str, str]]:
        """
        Detect cycles in parent-child relationships using DFS.

        Returns:
            List of tuples representing cyclic paths
        """
        parent_map = {node.node_id: node.parent_id for node in nodes}
        visited: Set[str] = set()
        rec_stack: Set[str] = set()
        cycles = []

        def dfs(node_id: str, path: list[str]) -> None:
            visited.add(node_id)
            rec_stack.add(node_id)
            path.append(node_id)

            parent = parent_map.get(node_id)
            if parent:
                if parent in rec_stack:
                    # Cycle detected
                    cycle_start = path.index(parent)
                    cycle = path[cycle_start:] + [parent]
                    cycles.append((cycle[0], cycle[1] if len(cycle) > 1 else cycle[0]))
                elif parent not in visited:
                    dfs(parent, path.copy())

            rec_stack.discard(node_id)

        for node_id in parent_map:
            if node_id not in visited:
                dfs(node_id, [])

        return cycles

    @staticmethod
    def _calculate_depth(nodes: list[IngestedNode]) -> int:
        """Calculate maximum hierarchy depth."""
        if not nodes:
            return 0

        parent_map = {node.node_id: node.parent_id for node in nodes}

        def get_depth(node_id: str, memo: dict | None = None) -> int:
            if memo is None:
                memo = {}
            if node_id in memo:
                return memo[node_id]

            parent = parent_map.get(node_id)
            if not parent:
                depth = 0
            else:
                depth = 1 + get_depth(parent, memo)

            memo[node_id] = depth
            return depth

        depths = [get_depth(nid) for nid in parent_map]
        return max(depths) if depths else 0
