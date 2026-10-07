"""Pure dependency-graph algorithms: cycle detection and topological sort.

No I/O, no ORM — operates on plain dicts of hashable node identifiers
(topic UUIDs in practice) so it can be tested and reasoned about in
isolation from persistence.
"""

from __future__ import annotations

import uuid

Edges = dict[uuid.UUID, set[uuid.UUID]]


def find_cycle(edges: Edges) -> list[uuid.UUID] | None:
    """
    DFS-based cycle detection with back-edge identification.

    edges: node -> set of nodes it depends on. Returns the exact cycle
    path (list of nodes) if one exists, else None.
    """
    white, gray, black = 0, 1, 2
    color: dict[uuid.UUID, int] = {node: white for node in edges}
    parent: dict[uuid.UUID, uuid.UUID] = {}

    def dfs(node: uuid.UUID) -> list[uuid.UUID] | None:
        color[node] = gray

        for neighbor in edges.get(node, ()):
            if neighbor not in color:
                color[neighbor] = white

            if color[neighbor] == white:
                parent[neighbor] = node
                result = dfs(neighbor)
                if result:
                    return result
            elif color[neighbor] == gray:
                cycle = [node]
                current = node
                while current != neighbor:
                    current = parent[current]
                    cycle.append(current)
                cycle.append(neighbor)
                return list(reversed(cycle))

        color[node] = black
        return None

    for node in list(edges.keys()):
        if color.get(node, white) == white:
            result = dfs(node)
            if result:
                return result

    return None


def break_all_cycles(edges: Edges) -> tuple[Edges, list[tuple[uuid.UUID, uuid.UUID]]]:
    """
    Repeatedly detect and break cycles by removing the exact edge that
    closes each one, until the graph is acyclic.

    Returns (acyclic_edges, removed_edges) — removed_edges must be
    reported to the caller, never silently dropped.
    """
    working_edges: Edges = {node: set(deps) for node, deps in edges.items()}
    removed: list[tuple[uuid.UUID, uuid.UUID]] = []

    while True:
        cycle = find_cycle(working_edges)
        if cycle is None:
            break

        closing_from, closing_to = cycle[-2], cycle[-1]
        working_edges[closing_from].discard(closing_to)
        removed.append((closing_from, closing_to))

    return working_edges, removed


def topological_sort(edges: Edges) -> list[uuid.UUID]:
    """
    Kahn's algorithm: returns nodes in an order where every node
    appears after all nodes it depends on.

    Raises RuntimeError if the graph still contains a cycle — callers
    should always run break_all_cycles first.
    """
    all_nodes: set[uuid.UUID] = set(edges.keys())
    for deps in edges.values():
        all_nodes.update(deps)

    in_degree: dict[uuid.UUID, int] = {node: 0 for node in all_nodes}
    dependents: dict[uuid.UUID, set[uuid.UUID]] = {node: set() for node in all_nodes}

    for node, deps in edges.items():
        for dep in deps:
            dependents[dep].add(node)
            in_degree[node] += 1

    queue = sorted((node for node in all_nodes if in_degree[node] == 0), key=str)
    order: list[uuid.UUID] = []

    while queue:
        node = queue.pop(0)
        order.append(node)

        for dependent in sorted(dependents[node], key=str):
            in_degree[dependent] -= 1
            if in_degree[dependent] == 0:
                queue.append(dependent)

        queue.sort(key=str)

    if len(order) != len(all_nodes):
        raise RuntimeError("Graph still contains a cycle; run break_all_cycles first.")

    return order
