# stage3_wall_graph.py
#
# Stage 3 - Wall Graph Construction
#
# Build a wall connectivity graph from axis-aligned segments (Stage 2).
#
# Core Principles:
#   - Stage 2 segments are authoritative and unchanged.
#   - Intersections require strict containment inside segment bounds.
#   - Tolerances applied independently, never stacked, never expand ranges.
#   - No artificial nodes or connections.
#
# Tolerances (independent):
#   INTERSECTION: 0 (strict containment, no range expansion)
#   NODE_CLUSTER: 2px Euclidean for merging coincident points
#   SPLIT_AXIS:   2px for perpendicular axis proximity after clustering
#   MIN_EDGE:     3px minimum edge length
#
# Pipeline:
#   1. load_segments
#   2. detect_intersections  (strict H x V containment)
#   3. collect candidate nodes (endpoints + intersections)
#   4. cluster_nodes (merge within 2px Euclidean)
#   5. split_segments (axis tolerance 2px, no range expansion)
#   6. build_graph (deduplicated edges, no zero-length)
#   7. clean_graph (keep largest connected component)

import sys
import os
import json
import math
import numpy as np
import cv2
from collections import defaultdict

# -- Tolerances (each used independently) ------------------------------------
NODE_CLUSTER_TOL = 2   # Euclidean distance for merging coincident points
SPLIT_AXIS_TOL = 2     # Perpendicular axis proximity in split_segments
MIN_EDGE_LEN = 3       # Discard sub-segments shorter than this


# =============================================================================
# 1. Load segments
# =============================================================================

def load_segments(json_path=None):
    """Load Stage 2 segments.  Endpoints remain unchanged."""
    if json_path is None:
        json_path = os.path.join("data", "intermediate", "wall_line_segments.json")
    with open(json_path) as f:
        raw = json.load(f)

    segments = []
    for s in raw:
        sx, sy = int(s["start"][0]), int(s["start"][1])
        ex, ey = int(s["end"][0]),   int(s["end"][1])
        ori = s["orientation"]

        # Canonical order without changing values
        if ori == "horizontal":
            if sx > ex:
                sx, ex = ex, sx
            ey = sy
        else:
            if sy > ey:
                sy, ey = ey, sy
            ex = sx

        segments.append({
            "start": (sx, sy), "end": (ex, ey), "orientation": ori,
        })

    nh = sum(1 for s in segments if s["orientation"] == "horizontal")
    print(f"Loaded {len(segments)} segments  (H={nh}, V={len(segments) - nh})")
    return segments


# =============================================================================
# 2. Detect intersections (strict containment, no range expansion)
# =============================================================================

def detect_intersections(segments):
    """
    Strict H x V intersection.

    Intersection exists ONLY if:
        hx1 <= vx <= hx2   (V's x within H's x-range inclusive)
        vy1 <= hy <= vy2   (H's y within V's y-range inclusive)

    NO tolerance applied.  NO range expansion (hx1-tol, hx2+tol forbidden).
    Intersection point is exactly (vx, hy).  NO snapping to endpoints.
    """
    horiz = [s for s in segments if s["orientation"] == "horizontal"]
    vert  = [s for s in segments if s["orientation"] == "vertical"]

    points = []
    for h in horiz:
        hy  = h["start"][1]
        hx1 = h["start"][0]
        hx2 = h["end"][0]
        for v in vert:
            vx  = v["start"][0]
            vy1 = v["start"][1]
            vy2 = v["end"][1]
            if hx1 <= vx <= hx2 and vy1 <= hy <= vy2:
                points.append((vx, hy))

    unique = sorted(set(points))
    print(f"Strict intersections: {len(unique)}")
    return unique


# =============================================================================
# 3. Collect candidate nodes
# =============================================================================

def collect_candidates(segments, intersections):
    """Gather all segment endpoints and intersection points."""
    pts = set()
    for s in segments:
        pts.add(s["start"])
        pts.add(s["end"])
    for ix in intersections:
        pts.add(ix)
    return sorted(pts)


# =============================================================================
# 4. Cluster nodes (union-find, Euclidean <= NODE_CLUSTER_TOL)
# =============================================================================

def cluster_nodes(points, tol=NODE_CLUSTER_TOL):
    """
    Merge points within Euclidean distance <= tol.
    Replace each cluster with integer-rounded centroid.
    Only clusters geometrically coincident points.
    """
    pts = list(points)
    n = len(pts)
    if n == 0:
        return {}, []

    parent = list(range(n))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for i in range(n):
        for j in range(i + 1, n):
            dx = pts[i][0] - pts[j][0]
            dy = pts[i][1] - pts[j][1]
            if dx * dx + dy * dy <= tol * tol:
                union(i, j)

    groups = defaultdict(list)
    for i in range(n):
        groups[find(i)].append(i)

    mapping = {}       # old point -> centroid
    centroids = set()
    for members in groups.values():
        cx = round(sum(pts[m][0] for m in members) / len(members))
        cy = round(sum(pts[m][1] for m in members) / len(members))
        c = (cx, cy)
        centroids.add(c)
        for m in members:
            mapping[pts[m]] = c

    centroids = sorted(centroids)
    merged = len(pts) - len(centroids)
    if merged:
        print(f"Node clustering: {len(pts)} pts -> {len(centroids)} nodes"
              f"  ({merged} merged)")
    else:
        print(f"Node clustering: {len(centroids)} nodes (no merges)")
    return mapping, centroids


# =============================================================================
# 5. Split segments at on-segment nodes
# =============================================================================

def split_segments(segments, node_positions, mapping, axis_tol=SPLIT_AXIS_TOL):
    """
    For each original segment, find clustered nodes that lie on it:

        Horizontal (y=hy, x in [hx1,hx2]):
            |ny - hy| <= axis_tol   AND   hx1 <= nx <= hx2

        Vertical   (x=vx, y in [vy1,vy2]):
            |nx - vx| <= axis_tol   AND   vy1 <= ny <= vy2

    Axis tolerance accounts for centroid rounding from clustering.
    Range bounds are NOT expanded (no hx1-tol or hx2+tol).

    Sort on-segment nodes along the axis and create sub-edges between
    consecutive nodes.  Discard sub-segments shorter than MIN_EDGE_LEN.
    """
    edges = []

    for seg in segments:
        ori = seg["orientation"]
        sx, sy = seg["start"]
        ex, ey = seg["end"]

        # The segment's own endpoints, mapped through clustering
        sp = mapping.get((sx, sy), (sx, sy))
        ep = mapping.get((ex, ey), (ex, ey))

        on_seg = set()
        on_seg.add(sp)
        on_seg.add(ep)

        for nd in node_positions:
            nx, ny = nd
            if ori == "horizontal":
                if abs(ny - sy) <= axis_tol and sx <= nx <= ex:
                    on_seg.add(nd)
            else:
                if abs(nx - sx) <= axis_tol and sy <= ny <= ey:
                    on_seg.add(nd)

        # Sort along segment axis
        if ori == "horizontal":
            ordered = sorted(on_seg, key=lambda p: p[0])
        else:
            ordered = sorted(on_seg, key=lambda p: p[1])

        # Create sub-edges between consecutive nodes
        for i in range(len(ordered) - 1):
            p1 = ordered[i]
            p2 = ordered[i + 1]
            length = math.hypot(p2[0] - p1[0], p2[1] - p1[1])
            if length >= MIN_EDGE_LEN:
                edges.append((p1, p2))

    print(f"Sub-segments after splitting: {len(edges)}")
    return edges


# =============================================================================
# 6. Build graph
# =============================================================================

def build_graph(sub_edges, node_positions):
    """
    Assign unique IDs to clustered nodes.
    Create edges (no duplicates, no zero-length).
    """
    coord_to_id = {c: i for i, c in enumerate(node_positions)}
    nodes = [{"id": i, "x": c[0], "y": c[1]}
             for i, c in enumerate(node_positions)]

    seen = set()
    edges = []
    for p1, p2 in sub_edges:
        a = coord_to_id.get(p1)
        b = coord_to_id.get(p2)
        if a is None or b is None or a == b:
            continue
        key = (min(a, b), max(a, b))
        if key in seen:
            continue
        seen.add(key)
        length = math.hypot(p2[0] - p1[0], p2[1] - p1[1])
        if length < 0.5:
            continue  # zero-length guard
        edges.append({
            "start_node": key[0],
            "end_node":   key[1],
            "length_px":  round(length, 1),
        })

    print(f"Graph: {len(nodes)} nodes, {len(edges)} edges")
    return nodes, edges


# =============================================================================
# 7. Clean graph - keep largest connected component
# =============================================================================

def clean_graph(nodes, edges):
    """Remove floating fragments.  Keep only the largest component."""
    adj = defaultdict(set)
    for e in edges:
        adj[e["start_node"]].add(e["end_node"])
        adj[e["end_node"]].add(e["start_node"])

    visited = set()
    components = []
    for n in nodes:
        nid = n["id"]
        if nid in visited:
            continue
        queue = [nid]
        comp = set()
        while queue:
            cur = queue.pop(0)
            if cur in visited:
                continue
            visited.add(cur)
            comp.add(cur)
            for nb in adj[cur]:
                if nb not in visited:
                    queue.append(nb)
        if comp:
            components.append(comp)

    components.sort(key=len, reverse=True)
    sizes = [len(c) for c in components]

    if len(components) <= 1:
        tag = "single component"
        if edges and len(edges) >= len(nodes):
            tag += ", has cycle"
        print(f"Components: {len(components)}  ({tag})")
        return nodes, edges

    top = str(sizes[:8])
    if len(sizes) > 8:
        top = top[:-1] + ", ..."
    pct = round(100 * sizes[0] / len(nodes)) if nodes else 0
    print(f"Components: {len(components)}  sizes={top}"
          f"  largest={sizes[0]} ({pct}%)")

    # Keep largest
    keep = components[0]
    old_to_new = {}
    new_nodes = []
    for n in nodes:
        if n["id"] in keep:
            new_id = len(new_nodes)
            old_to_new[n["id"]] = new_id
            new_nodes.append({"id": new_id, "x": n["x"], "y": n["y"]})

    new_edges = []
    for e in edges:
        if e["start_node"] in keep and e["end_node"] in keep:
            new_edges.append({
                "start_node": old_to_new[e["start_node"]],
                "end_node":   old_to_new[e["end_node"]],
                "length_px":  e["length_px"],
            })

    dropped_n = len(nodes) - len(new_nodes)
    dropped_e = len(edges) - len(new_edges)
    if dropped_n:
        print(f"Pruned {dropped_n} nodes, {dropped_e} edges from fragments")

    return new_nodes, new_edges


# =============================================================================
# Reporting
# =============================================================================

def report(nodes, edges):
    deg = defaultdict(int)
    for e in edges:
        deg[e["start_node"]] += 1
        deg[e["end_node"]] += 1

    d1 = sum(1 for v in deg.values() if v == 1)
    d2 = sum(1 for v in deg.values() if v == 2)
    d3 = sum(1 for v in deg.values() if v >= 3)
    print(f"Degree dist:  deg-1={d1}, deg-2={d2}, deg-3+={d3}")

    pairs = [(e["start_node"], e["end_node"]) for e in edges]
    dupes = len(pairs) - len(set(pairs))
    zl = sum(1 for e in edges if e["length_px"] < 0.5)
    print(f"Dup edges: {dupes}  Zero-len: {zl}"
          f"  {'[PASS]' if dupes == 0 and zl == 0 else '[FAIL]'}")


# =============================================================================
# Save & Visualize
# =============================================================================

def get_image_dimensions():
    p = os.path.join("data", "intermediate", "binary_wall_mask.png")
    if os.path.exists(p):
        img = cv2.imread(p, cv2.IMREAD_GRAYSCALE)
        if img is not None:
            return img.shape
    return (720, 1024)


def save_graph(nodes, edges, path=None):
    if path is None:
        path = os.path.join("data", "intermediate", "wall_graph.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump({"nodes": nodes, "edges": edges}, f, indent=2)
    print(f"Saved -> {path}")


def visualize(nodes, edges, img_shape, save_dir=None, suffix=""):
    if save_dir is None:
        save_dir = os.path.join("data", "intermediate")
    h, w = img_shape[:2]
    nmap = {n["id"]: (n["x"], n["y"]) for n in nodes}

    def _draw(bg, tag, path):
        for e in edges:
            cv2.line(bg, nmap[e["start_node"]], nmap[e["end_node"]],
                     (0, 255, 0), 2)
        for n in nodes:
            cv2.circle(bg, (n["x"], n["y"]), 5, (0, 0, 255), -1)
            cv2.putText(bg, str(n["id"]), (n["x"] + 6, n["y"] - 4),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 0), 1)
        cv2.imwrite(path, bg)
        print(f"{tag} -> {path}")

    _draw(np.zeros((h, w, 3), np.uint8), "Overlay",
          os.path.join(save_dir, f"wall_graph_overlay{suffix}.png"))

    mp = os.path.join("data", "intermediate", "binary_wall_mask.png")
    if os.path.exists(mp):
        mask = cv2.imread(mp, cv2.IMREAD_GRAYSCALE)
        if mask is not None:
            bg = cv2.cvtColor((mask * 0.35).astype(np.uint8),
                              cv2.COLOR_GRAY2BGR)
            _draw(bg, "Mask overlay",
                  os.path.join(save_dir, f"wall_graph_on_mask{suffix}.png"))


# =============================================================================
# Main
# =============================================================================

def main():
    print("=" * 55)
    print("  Stage 3: Wall Graph Construction")
    print("=" * 55)
    print()

    img_shape = get_image_dimensions()
    print(f"Image: {img_shape[1]}x{img_shape[0]}")
    print(f"Tolerances:  cluster={NODE_CLUSTER_TOL}px"
          f"  axis={SPLIT_AXIS_TOL}px  min_edge={MIN_EDGE_LEN}px")
    print()

    path = sys.argv[1] if len(sys.argv) >= 2 else None

    # 1. Load
    segments = load_segments(path)

    # 2. Strict perpendicular intersections
    intersections = detect_intersections(segments)

    # 3. Collect all candidate nodes
    candidates = collect_candidates(segments, intersections)
    print(f"Candidate points: {len(candidates)}")

    # 4. Cluster nearby nodes
    mapping, node_positions = cluster_nodes(candidates, NODE_CLUSTER_TOL)

    # 5. Split segments at on-segment nodes
    sub_edges = split_segments(segments, node_positions, mapping,
                               SPLIT_AXIS_TOL)

    # 6. Build graph
    nodes, edges = build_graph(sub_edges, node_positions)

    # 6b. Pre-cleanup visualization
    visualize(nodes, edges, img_shape, suffix="_all")

    # 7. Keep largest component
    nodes, edges = clean_graph(nodes, edges)

    # 8. Report, save, visualize
    print()
    report(nodes, edges)
    save_graph(nodes, edges)
    visualize(nodes, edges, img_shape)

    print(f"\nFinal: {len(nodes)} nodes, {len(edges)} edges")
    print("Stage 3 complete!")


if __name__ == "__main__":
    main()