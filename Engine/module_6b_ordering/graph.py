"""Pure dependency graph operations for batch schedule updates."""

from __future__ import annotations

from collections import defaultdict, deque
from typing import Dict, List, Optional, Set, Tuple

import pandas as pd

Graph = Dict[str, Set[str]]


def build_dependency_graph(matched_pairs: List[Tuple[str, str]], schedule_df: pd.DataFrame) -> Graph:
    """Build an activity -> predecessor graph for the matched batch items."""
    matched_ids = {activity_id for _, activity_id in matched_pairs}
    graph: Graph = {activity_id: set() for activity_id in matched_ids}
    for _, activity_id in matched_pairs:
        rows = schedule_df[schedule_df["activity_id"] == activity_id]
        if rows.empty:
            continue
        predecessor = str(rows.iloc[0].get("predecessor_activity_id", "") or "").strip()
        if predecessor and predecessor in matched_ids:
            graph[activity_id].add(predecessor)
    return graph


def detect_cycles(graph: Graph) -> Optional[List[str]]:
    """Return one cycle path, or None when the graph is acyclic."""
    visiting: Set[str] = set()
    visited: Set[str] = set()
    path: List[str] = []

    def visit(node: str) -> Optional[List[str]]:
        if node in visiting:
            return path[path.index(node):] + [node]
        if node in visited:
            return None
        visiting.add(node)
        path.append(node)
        for predecessor in graph.get(node, set()):
            cycle = visit(predecessor)
            if cycle:
                return cycle
        path.pop()
        visiting.remove(node)
        visited.add(node)
        return None

    for node in graph:
        cycle = visit(node)
        if cycle:
            return cycle
    return None


def topological_sort(graph: Graph) -> List[List[str]]:
    """Return topological activity order grouped into connected components."""
    if (cycle := detect_cycles(graph)) is not None:
        raise ValueError(f"Dependency graph contains a cycle: {' -> '.join(cycle)}")

    undirected: Dict[str, Set[str]] = defaultdict(set)
    for node, predecessors in graph.items():
        undirected[node].update(predecessors)
        for predecessor in predecessors:
            undirected[predecessor].add(node)

    components: List[Set[str]] = []
    remaining = set(graph)
    while remaining:
        root = min(remaining)
        remaining.remove(root)
        component = {root}
        queue = deque([root])
        while queue:
            node = queue.popleft()
            for neighbor in undirected[node]:
                if neighbor in remaining:
                    remaining.remove(neighbor)
                    component.add(neighbor)
                    queue.append(neighbor)
        components.append(component)

    ordered_components: List[List[str]] = []
    for component in components:
        indegree = {node: 0 for node in component}
        successors: Dict[str, Set[str]] = defaultdict(set)
        for node in component:
            for predecessor in graph[node]:
                indegree[node] += 1
                successors[predecessor].add(node)
        ready = deque(sorted(node for node, degree in indegree.items() if degree == 0))
        ordered: List[str] = []
        while ready:
            node = ready.popleft()
            ordered.append(node)
            for successor in sorted(successors[node]):
                indegree[successor] -= 1
                if indegree[successor] == 0:
                    ready.append(successor)
        ordered_components.append(ordered)
    ordered_components.sort(key=lambda component: component[0] if component else "")
    return ordered_components