from __future__ import annotations

import pandas as pd
import pytest

from Engine.module_6b_ordering.graph import (
    build_dependency_graph,
    detect_cycles,
    topological_sort,
)


def test_build_and_sort_dependency_components():
    schedule = pd.DataFrame([
        {"activity_id": "A", "predecessor_activity_id": ""},
        {"activity_id": "B", "predecessor_activity_id": "A"},
        {"activity_id": "C", "predecessor_activity_id": ""},
    ])
    graph = build_dependency_graph([("r1", "B"), ("r2", "A"), ("r3", "C")], schedule)

    assert topological_sort(graph) == [["A", "B"], ["C"]]
    assert detect_cycles(graph) is None


def test_detect_cycles_and_reject_sort():
    graph = {"A": {"B"}, "B": {"A"}}

    assert detect_cycles(graph) == ["A", "B", "A"]
    with pytest.raises(ValueError, match="cycle"):
        topological_sort(graph)