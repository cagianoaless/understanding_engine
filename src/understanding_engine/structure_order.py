"""Compact, exact representation of the 02a geometric order rules."""

from .contracts import ExtractionError

ORDERING = {"accepted": "transitive_closure",
            "otherwise": "unresolved_for_every_distinct_region_pair",
            "unresolved_reason": "overlap_or_column_transition_unproven"}


def closure(regions, relations):
    """Return deterministic topological order and bitset reachability; reject cycles."""
    ids = [r["id"] for r in regions]
    index = {rid: i for i, rid in enumerate(ids)}
    if len(index) != len(ids):
        raise ExtractionError("invalid_structure", "Duplicate region IDs")
    outgoing = [set() for _ in ids]
    for edge in relations:
        a, b = edge["before"], edge["after"]
        if a not in index or b not in index or a == b:
            raise ExtractionError("invalid_structure", "Invalid order endpoints")
        if index[b] in outgoing[index[a]]:
            raise ExtractionError("invalid_structure", "Duplicate order edge")
        outgoing[index[a]].add(index[b])
    incoming = [0] * len(ids)
    for targets in outgoing:
        for b in targets:
            incoming[b] += 1
    import heapq
    ready = [i for i, n in enumerate(incoming) if n == 0]
    heapq.heapify(ready)
    order = []
    while ready:
        a = heapq.heappop(ready)
        order.append(a)
        for b in sorted(outgoing[a]):
            incoming[b] -= 1
            if incoming[b] == 0:
                heapq.heappush(ready, b)
    if len(order) != len(ids):
        raise ExtractionError("invalid_structure", "Reading-order cycle")
    reach = [0] * len(ids)
    for a in reversed(order):
        for b in outgoing[a]:
            reach[a] |= (1 << b) | reach[b]
    return order, reach


def compact_order(regions, columns):
    """Apply 02a's pair rules, store their transitive reduction, quantify the rest.

    Pair comparisons and temporary reachability can still be quadratic. Output
    is linear for chains/two-column prose; general DAG reductions can be dense.
    """
    n = len(regions)
    ranked = sorted(range(n), key=lambda i: (regions[i]["bbox"][1], i))
    targets = [0] * n
    for pos, a in enumerate(ranked):
        left = regions[a]
        if left["type"] == "unknown":
            continue
        for b in ranked[pos + 1:]:
            right = regions[b]
            same = left["column_id"] is not None and left["column_id"] == right["column_id"]
            spanning = len(columns) == 2 and left["type"] == "heading" and left["column_id"] is None
            if (same or spanning) and right["type"] != "unknown" and left["bbox"][3] <= right["bbox"][1]:
                targets[a] |= 1 << b
    reach = targets.copy()
    for a in reversed(ranked):
        for b in ranked:
            if targets[a] & (1 << b):
                reach[a] |= reach[b]
    reduced = []
    for a in range(n):
        covered = 0
        for b in ranked:
            if targets[a] & (1 << b) and not covered & (1 << b):
                reduced.append({"before": regions[a]["id"], "after": regions[b]["id"],
                                "rule": "same_column_vertical_separation" if regions[a]["column_id"] is not None
                                else "spanning_heading_above"})
                covered |= (1 << b) | reach[b]
    return {"relations": reduced, "ambiguities": [], "ordering": dict(ORDERING)}


def order_status(page, a, b):
    """Query validated 0.2 pages; omitted paths have explicitly unresolved order."""
    ids = [r["id"] for r in page["regions"]]
    index = {rid: i for i, rid in enumerate(ids)}
    if a not in index or b not in index:
        raise ExtractionError("invalid_structure", "Unknown order query endpoint")
    if a == b:
        return "same_region"
    _, reach = closure(page["regions"], page["relations"])
    if reach[index[a]] & (1 << index[b]):
        return "before"
    if reach[index[b]] & (1 << index[a]):
        return "after"
    return "unresolved"
