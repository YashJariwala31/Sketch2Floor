# stage3_wall_graph.py
#
# Stage 3 – Wall Graph Construction (Axis-Normalized)
#
# Build a clean wall connectivity graph from axis-aligned segments (Stage 2).
#
# Core Principles:
#   - Stage 2 segments are authoritative geometry.
#   - Before any intersection work, near-identical axis coordinates are
#     snapped to canonical values (vertical X's, horizontal Y's).
#   - Intersections require strict containment inside segment bounds.
#   - Node membership is strictly tracked: a node may split a segment
#     ONLY if it is an endpoint or was born from an intersection on it.
#   - No geometric proximity checks for segment membership.
#   - No artificial nodes or connections.
#
# Tolerances:
#   AXIS_SNAP:       3px – snap near-identical axis coordinates (tight)
#   COLLINEAR_GAP:   5px – merge collinear segments with gap <= this
#   CORNER_EXTEND:  80px – extend endpoints to reach nearby perpendiculars
#   INTERSECTION:    0   – strict containment, no range expansion
#   NODE_CLUSTER:    2px – Euclidean merge for coincident points (tight)
#   MIN_EDGE:       20px – discard short sub-segments
#   NOISE_THRESH:   50px – remove components with total edge length below this
#
# Pipeline:
#   1.   load_segments
#   2.   normalize_axis_coordinates  (snap X of V segs, Y of H segs)
#   2.5  merge_collinear_segments    (fuse coaxial segments within gap tol)
#   2.75 extend_to_corners           (extend endpoints to nearby perpendiculars)
#   3.   detect_intersections        (strict H×V, track segment indices)
#   4.   collect candidate nodes     (endpoints + intersections only)
#   5.   cluster_nodes               (merge within 2px Euclidean)
#   6.   split_segments              (strict membership only)
#   7.   build_graph                 (deduplicated, no zero-length)
#   8.   clean_graph                 (remove noise components only)

import sys
import os
import json
import math
import numpy as np
import cv2
from collections import defaultdict

# -- Tolerances ---------------------------------------------------------------
AXIS_SNAP_TOL = 5           # Snap near-identical axis coordinates (tight)
COLLINEAR_GAP_TOL = 5      # Merge collinear segments whose gap <= this
CORNER_EXTEND_TOL = 80     # Extend endpoints to reach nearby perpendiculars
NODE_CLUSTER_TOL = 2        # Euclidean distance for merging coincident points (tight)
MIN_EDGE_LEN = 20           # Discard sub-segments shorter than this
NOISE_THRESHOLD = 50        # Remove components with total edge length below this


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
# 2. Normalize axis coordinates
# =============================================================================

def _cluster_values(values, tol):
    """
    Cluster a list of integer values within *tol* of each other.
    Returns a mapping {original_value: canonical_value} where canonical
    is the integer-rounded mean of the cluster.

    Uses greedy sorted clustering (no union-find needed for 1-D).
    """
    if not values:
        return {}

    uniq = sorted(set(values))
    mapping = {}
    cluster = [uniq[0]]

    for v in uniq[1:]:
        if v - cluster[0] <= tol:
            # Still within tolerance of the cluster's first element
            cluster.append(v)
        else:
            # Flush current cluster
            canonical = round(sum(cluster) / len(cluster))
            for cv in cluster:
                mapping[cv] = canonical
            cluster = [v]

    # Flush last cluster
    canonical = round(sum(cluster) / len(cluster))
    for cv in cluster:
        mapping[cv] = canonical

    return mapping


def normalize_axis_coordinates(segments, tol=AXIS_SNAP_TOL):
    """
    Snap near-identical axis coordinates so micro-duplicate walls merge.

    - Collect all X values from vertical segments → cluster within *tol*
    - Collect all Y values from horizontal segments → cluster within *tol*
    - Update every segment endpoint using the snapped coordinates.

    This eliminates cases like x=200 and x=204 getting treated as two
    separate vertical walls.
    """
    # Collect axis values
    v_xs = []
    h_ys = []
    for s in segments:
        if s["orientation"] == "vertical":
            v_xs.append(s["start"][0])
            v_xs.append(s["end"][0])
        else:
            h_ys.append(s["start"][1])
            h_ys.append(s["end"][1])

    x_map = _cluster_values(v_xs, tol)
    y_map = _cluster_values(h_ys, tol)

    snapped_x = len([v for v in x_map.values() if v != x_map.get(v)])
    snapped_y = len([v for v in y_map.values() if v != y_map.get(v)])

    # Apply snapping to segment endpoints
    out = []
    for s in segments:
        sx, sy = s["start"]
        ex, ey = s["end"]
        ori = s["orientation"]

        if ori == "vertical":
            sx = x_map.get(sx, sx)
            ex = x_map.get(ex, ex)
            # Also snap any Y if it happens to be in the horizontal Y map
            sy = y_map.get(sy, sy)
            ey = y_map.get(ey, ey)
        else:
            sy = y_map.get(sy, sy)
            ey = y_map.get(ey, ey)
            # Also snap any X if it happens to be in the vertical X map
            sx = x_map.get(sx, sx)
            ex = x_map.get(ex, ex)

        # Re-canonicalize after snapping
        if ori == "horizontal":
            if sx > ex:
                sx, ex = ex, sx
            ey = sy
        else:
            if sy > ey:
                sy, ey = ey, sy
            ex = sx

        out.append({
            "start": (sx, sy), "end": (ex, ey), "orientation": ori,
        })

    x_clusters = len(set(x_map.values())) if x_map else 0
    y_clusters = len(set(y_map.values())) if y_map else 0
    print(f"Axis normalization:  X clusters={x_clusters}  Y clusters={y_clusters}"
          f"  (tol={tol}px)")
    return out


# =============================================================================
# 2.5  Merge collinear segments (pre-graph)
# =============================================================================

def merge_collinear_segments(segments, gap_tol=COLLINEAR_GAP_TOL):
    """
    Merge collinear segments that share the same snapped axis coordinate
    and whose ranges overlap or have a gap <= gap_tol.

    For horizontal segments:  group by Y, merge overlapping / nearby X-ranges.
    For vertical   segments:  group by X, merge overlapping / nearby Y-ranges.

    This turns fragmented wall pieces (multiple short segments along the
    same line) into single continuous segments, so the downstream graph
    sees a clean perimeter instead of a chain of tiny edges.
    """
    # -- Group segments by (orientation, axis_value) -------------------------
    h_groups = defaultdict(list)   # y -> list of (x_min, x_max)
    v_groups = defaultdict(list)   # x -> list of (y_min, y_max)

    for s in segments:
        if s["orientation"] == "horizontal":
            y = s["start"][1]
            x_min = min(s["start"][0], s["end"][0])
            x_max = max(s["start"][0], s["end"][0])
            h_groups[y].append((x_min, x_max))
        else:
            x = s["start"][0]
            y_min = min(s["start"][1], s["end"][1])
            y_max = max(s["start"][1], s["end"][1])
            v_groups[x].append((y_min, y_max))

    # -- Interval merge helper ----------------------------------------------
    def _merge_intervals(intervals, tol):
        """
        Merge a list of (lo, hi) intervals.  Two intervals are merged if
        they overlap OR the gap between them is <= tol.
        Returns a sorted list of merged (lo, hi) tuples.
        """
        if not intervals:
            return []
        intervals = sorted(intervals)
        merged = [intervals[0]]
        for lo, hi in intervals[1:]:
            prev_lo, prev_hi = merged[-1]
            if lo <= prev_hi + tol:          # overlap or within gap tolerance
                merged[-1] = (prev_lo, max(prev_hi, hi))
            else:
                merged.append((lo, hi))
        return merged

    # -- Rebuild segments from merged intervals -----------------------------
    out = []

    for y, intervals in sorted(h_groups.items()):
        for x_min, x_max in _merge_intervals(intervals, gap_tol):
            out.append({
                "start": (x_min, y), "end": (x_max, y),
                "orientation": "horizontal",
            })

    total_h_before = sum(len(v) for v in h_groups.values())
    total_h_after  = sum(1 for s in out if s["orientation"] == "horizontal")

    for x, intervals in sorted(v_groups.items()):
        for y_min, y_max in _merge_intervals(intervals, gap_tol):
            out.append({
                "start": (x, y_min), "end": (x, y_max),
                "orientation": "vertical",
            })

    total_v_before = sum(len(v) for v in v_groups.values())
    total_v_after  = sum(1 for s in out if s["orientation"] == "vertical")

    h_fused = total_h_before - total_h_after
    v_fused = total_v_before - total_v_after
    print(f"Collinear merge:  {total_h_before + total_v_before} -> {len(out)} segments"
          f"  (H: {total_h_before}->{total_h_after}, fused {h_fused}"
          f"  |  V: {total_v_before}->{total_v_after}, fused {v_fused})"
          f"  (gap_tol={gap_tol}px)")
    return out


# =============================================================================
# 2.75  Extend segment endpoints to meet at corners
# =============================================================================

def extend_to_corners(segments, ext_tol=CORNER_EXTEND_TOL):
    """
    Extend H/V segment endpoints so they meet at corners.

    Hand-drawn walls often end *before* reaching the perpendicular wall,
    leaving a gap of 50–100px at corners.  Strict intersection detection
    then finds nothing and the graph is fully disconnected.

    For every (H, V) pair, compute the theoretical intersection (vx, hy).
    If vx is within ext_tol of H's x-range AND hy is within ext_tol of
    V's y-range, extend both segments to include that intersection:
        - H's x-range grows to include vx
        - V's y-range grows to include hy

    Only *near-miss* corners are fixed; segments hundreds of pixels apart
    are left alone.
    """
    # Work on mutable copies: store as [x_min, x_max, y] for H,
    #                                   [x, y_min, y_max] for V
    h_segs = []  # (index_in_output, [x_min, x_max, y])
    v_segs = []  # (index_in_output, [x, y_min, y_max])

    for i, s in enumerate(segments):
        if s["orientation"] == "horizontal":
            h_segs.append((i, [s["start"][0], s["end"][0], s["start"][1]]))
        else:
            v_segs.append((i, [s["start"][0], s["start"][1], s["end"][1]]))

    extensions = 0

    for _hi, h in h_segs:
        hx1, hx2, hy = h
        for _vi, v in v_segs:
            vx, vy1, vy2 = v

            # How far is vx from H's x-range?
            if vx < hx1:
                h_gap = hx1 - vx
            elif vx > hx2:
                h_gap = vx - hx2
            else:
                h_gap = 0  # already within range

            # How far is hy from V's y-range?
            if hy < vy1:
                v_gap = vy1 - hy
            elif hy > vy2:
                v_gap = hy - vy2
            else:
                v_gap = 0  # already within range

            # Both must be within tolerance to prevent long jumps
            if h_gap <= ext_tol and v_gap <= ext_tol and (h_gap > 0 or v_gap > 0):
                # Extend H to include vx
                if vx < h[0]:
                    h[0] = vx
                elif vx > h[1]:
                    h[1] = vx

                # Extend V to include hy
                if hy < v[1]:
                    v[1] = hy
                elif hy > v[2]:
                    v[2] = hy

                extensions += 1

    # Rebuild segment list
    out = list(segments)  # shallow copy of dicts
    out = [dict(s) for s in out]  # deep copy each dict

    for _hi, h in h_segs:
        out[_hi] = {
            "start": (h[0], h[2]), "end": (h[1], h[2]),
            "orientation": "horizontal",
        }
    for _vi, v in v_segs:
        out[_vi] = {
            "start": (v[0], v[1]), "end": (v[0], v[2]),
            "orientation": "vertical",
        }

    print(f"Corner extension:  {extensions} extensions applied  (ext_tol={ext_tol}px)")
    return out


# =============================================================================
# 3. Detect intersections (strict containment, track segment indices)
# =============================================================================

def detect_intersections(segments):
    """
    Strict H × V intersection with segment-index tracking.

    Intersection exists ONLY if:
        hx1 <= vx <= hx2   (V's x within H's x-range inclusive)
        vy1 <= hy <= vy2   (H's y within V's y-range inclusive)

    NO tolerance applied.  NO range expansion.
    Intersection point is exactly (vx, hy).

    Returns:
        unique_points     – sorted list of unique intersection (x,y) tuples
        seg_intersections – dict  {segment_index: set of intersection points}
    """
    h_indices = [i for i, s in enumerate(segments)
                 if s["orientation"] == "horizontal"]
    v_indices = [i for i, s in enumerate(segments)
                 if s["orientation"] == "vertical"]

    all_points = []
    seg_intersections = defaultdict(set)   # seg_index -> set of (x,y)

    for hi in h_indices:
        h = segments[hi]
        hy  = h["start"][1]
        hx1 = h["start"][0]
        hx2 = h["end"][0]
        for vi in v_indices:
            v = segments[vi]
            vx  = v["start"][0]
            vy1 = v["start"][1]
            vy2 = v["end"][1]
            if hx1 <= vx <= hx2 and vy1 <= hy <= vy2:
                pt = (vx, hy)
                all_points.append(pt)
                seg_intersections[hi].add(pt)
                seg_intersections[vi].add(pt)

    unique_points = sorted(set(all_points))
    print(f"Strict intersections: {len(unique_points)}")
    return unique_points, seg_intersections


# =============================================================================
# 4. Collect candidate nodes
# =============================================================================

def collect_candidates(segments, intersections):
    """Gather all segment endpoints and intersection points.  Nothing else."""
    pts = set()
    for s in segments:
        pts.add(s["start"])
        pts.add(s["end"])
    for ix in intersections:
        pts.add(ix)
    return sorted(pts)


# =============================================================================
# 5. Cluster nodes (union-find, Euclidean <= NODE_CLUSTER_TOL)
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
# 6. Split segments at on-segment nodes (strict membership)
# =============================================================================

def split_segments(segments, node_positions, mapping, seg_intersections):
    """
    Strict membership splitting.  For each segment, the ONLY nodes that may
    appear on it are:

        1. Its own two endpoints (mapped through clustering).
        2. Intersection points that were born from that specific segment
           (looked up via seg_intersections), also mapped through clustering.

    NO geometric proximity check (abs(ny-sy) <= tol) is used.
    NO axis tolerance is applied.

    Valid nodes are sorted along the segment axis and sub-edges are created
    between consecutive nodes.  Sub-segments shorter than MIN_EDGE_LEN are
    discarded.
    """
    edges = []

    for seg_idx, seg in enumerate(segments):
        ori = seg["orientation"]
        sx, sy = seg["start"]
        ex, ey = seg["end"]

        # 1. Segment's own endpoints, mapped through clustering
        sp = mapping.get((sx, sy), (sx, sy))
        ep = mapping.get((ex, ey), (ex, ey))

        on_seg = set()
        on_seg.add(sp)
        on_seg.add(ep)

        # 2. Intersection points that belong to THIS segment, mapped
        for raw_pt in seg_intersections.get(seg_idx, set()):
            clustered_pt = mapping.get(raw_pt, raw_pt)
            on_seg.add(clustered_pt)

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
# 7. Build graph
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
# 8. Clean graph – remove noise components only
# =============================================================================

def clean_graph(nodes, edges, noise_threshold=NOISE_THRESHOLD):
    """
    Remove only noise components.  Keep all valid wall structures.

    A component is noise (and removed) ONLY if:
        - It has fewer than 2 nodes, OR
        - Its total edge length is below noise_threshold.

    All other components are preserved, even if disconnected.
    This avoids destroying valid interior walls that don't
    connect to the outer boundary.
    """
    # Build adjacency
    adj = defaultdict(set)
    for e in edges:
        adj[e["start_node"]].add(e["end_node"])
        adj[e["end_node"]].add(e["start_node"])

    # Find connected components (BFS)
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

    top = str(sizes[:8])
    if len(sizes) > 8:
        top = top[:-1] + ", ...]"
    print(f"Components: {len(components)}  sizes={top}")

    if len(components) <= 1:
        if edges and len(edges) >= len(nodes):
            print("  single component, has cycle")
        return nodes, edges

    # Decide which components to keep
    keep_ids = set()       # set of all node IDs to keep
    kept_count = 0
    noise_count = 0

    for comp in components:
        # Compute total edge length for this component
        comp_edge_len = sum(
            e["length_px"] for e in edges
            if e["start_node"] in comp and e["end_node"] in comp
        )

        is_noise = (len(comp) < 2) or (comp_edge_len < noise_threshold)

        if is_noise:
            noise_count += 1
        else:
            kept_count += 1
            keep_ids.update(comp)

    print(f"  Kept {kept_count} components, removed {noise_count} noise")

    if not keep_ids:
        # Edge case: everything was noise.  Fall back to keeping largest.
        print("  WARNING: all components below threshold, keeping largest")
        keep_ids = components[0]

    # Rebuild with contiguous IDs
    old_to_new = {}
    new_nodes = []
    for n in nodes:
        if n["id"] in keep_ids:
            new_id = len(new_nodes)
            old_to_new[n["id"]] = new_id
            new_nodes.append({"id": new_id, "x": n["x"], "y": n["y"]})

    new_edges = []
    for e in edges:
        if e["start_node"] in keep_ids and e["end_node"] in keep_ids:
            new_edges.append({
                "start_node": old_to_new[e["start_node"]],
                "end_node":   old_to_new[e["end_node"]],
                "length_px":  e["length_px"],
            })

    dropped_n = len(nodes) - len(new_nodes)
    dropped_e = len(edges) - len(new_edges)
    if dropped_n:
        print(f"  Pruned {dropped_n} noise nodes, {dropped_e} noise edges")

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
    short = sum(1 for e in edges if e["length_px"] < MIN_EDGE_LEN)
    print(f"Dup edges: {dupes}  Zero-len: {zl}  Short(<{MIN_EDGE_LEN}px): {short}"
          f"  {'[PASS]' if dupes == 0 and zl == 0 and short == 0 else '[FAIL]'}")


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


def visualize(nodes, edges, img_shape, save_dir=None):
    """Single visualization: final graph overlaid on wall mask (or black bg)."""
    if save_dir is None:
        save_dir = os.path.join("data", "intermediate")
    h, w = img_shape[:2]
    nmap = {n["id"]: (n["x"], n["y"]) for n in nodes}

    # Try wall mask as background; fall back to black
    mp = os.path.join("data", "intermediate", "binary_wall_mask.png")
    if os.path.exists(mp):
        mask = cv2.imread(mp, cv2.IMREAD_GRAYSCALE)
        if mask is not None:
            bg = cv2.cvtColor((mask * 0.35).astype(np.uint8),
                              cv2.COLOR_GRAY2BGR)
        else:
            bg = np.zeros((h, w, 3), np.uint8)
    else:
        bg = np.zeros((h, w, 3), np.uint8)

    for e in edges:
        cv2.line(bg, nmap[e["start_node"]], nmap[e["end_node"]],
                 (0, 255, 0), 2)
    for n in nodes:
        cv2.circle(bg, (n["x"], n["y"]), 5, (0, 0, 255), -1)
        cv2.putText(bg, str(n["id"]), (n["x"] + 6, n["y"] - 4),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 0), 1)

    out_path = os.path.join(save_dir, "wall_graph.png")
    cv2.imwrite(out_path, bg)
    print(f"Visualization -> {out_path}")


# =============================================================================
# Main
# =============================================================================

def main():
    print("=" * 55)
    print("  Stage 3: Wall Graph Construction (Axis-Normalized)")
    print("=" * 55)
    print()

    img_shape = get_image_dimensions()
    print(f"Image: {img_shape[1]}x{img_shape[0]}")
    print(f"Tolerances:  axis_snap={AXIS_SNAP_TOL}px"
          f"  cluster={NODE_CLUSTER_TOL}px"
          f"  min_edge={MIN_EDGE_LEN}px")
    print()

    path = sys.argv[1] if len(sys.argv) >= 2 else None

    # 1. Load
    segments = load_segments(path)

    # 2. Normalize axis coordinates (snap near-identical X/Y)
    segments = normalize_axis_coordinates(segments, AXIS_SNAP_TOL)

    # 2.5 Merge collinear segments (fuse coaxial within gap tolerance)
    segments = merge_collinear_segments(segments, COLLINEAR_GAP_TOL)

    # 2.75 Extend endpoints to meet at nearby perpendicular segments
    segments = extend_to_corners(segments, CORNER_EXTEND_TOL)

    # 3. Strict perpendicular intersections (with segment-index tracking)
    intersections, seg_intersections = detect_intersections(segments)

    # 4. Collect all candidate nodes
    candidates = collect_candidates(segments, intersections)
    print(f"Candidate points: {len(candidates)}")

    # 5. Cluster nearby nodes
    mapping, node_positions = cluster_nodes(candidates, NODE_CLUSTER_TOL)

    # 6. Split segments (strict membership: endpoints + own intersections)
    sub_edges = split_segments(segments, node_positions, mapping,
                               seg_intersections)

    # 7. Build graph
    nodes, edges = build_graph(sub_edges, node_positions)

    # 8. Keep largest component
    nodes, edges = clean_graph(nodes, edges)

    # 9. Report, save, visualize
    print()
    report(nodes, edges)
    save_graph(nodes, edges)
    visualize(nodes, edges, img_shape)

    print(f"\nFinal: {len(nodes)} nodes, {len(edges)} edges")
    print("Stage 3 complete!")


if __name__ == "__main__":
    main()