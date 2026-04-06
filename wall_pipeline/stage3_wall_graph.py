# stage3_wall_graph.py
#
# Stage 3 – Wall Graph Construction (Closed Topology)
#
# Build a wall connectivity graph from axis-aligned segments (Stage 2).
#
# Core Principles:
#   - Collinear segments are merged to form continuous walls.
#   - Endpoints are snapped within tolerance to close gaps.
#   - T-junctions are properly split.
#   - Small collinear gaps are bridged.
#   - Graph must have closed cycles for room detection.
#
# Pipeline:
#   1. load_segments
#   2. merge_collinear_segments (form continuous walls)
#   3. bridge_small_gaps (connect nearby collinear endpoints)
#   4. normalize_axis_coordinates (snap near-identical X/Y)
#   5. snap_endpoints (close small gaps at corners)
#   6. detect_intersections (axis-aligned H×V + T-junctions)
#   7. collect_candidates (endpoints + intersections)
#   8. cluster_nodes (merge coincident points)
#   9. split_segments (at endpoints + intersections)
#  10. build_graph (deduplicated, no zero-length)
#  11. clean_graph (remove noise components)
#  12. validate_topology (ensure closed cycles)

import sys
import os
import json
import math
import numpy as np
import cv2
from collections import defaultdict

# -- Tolerances ---------------------------------------------------------------
AXIS_SNAP_TOL = 5           # Snap near-identical axis coordinates
ENDPOINT_SNAP_TOL = 5       # Snap endpoints within this distance
COLLINEAR_GAP_TOL = 0       # Bridge collinear gaps smaller than this
INTERSECTION_TOL = 0        # Strict containment - no tolerance expansion
NODE_MERGE_TOL = 5          # Euclidean distance for merging coincident points
MIN_EDGE_LEN = 20           # Discard sub-segments shorter than this
NOISE_THRESHOLD = 50        # Remove components with total edge length below this

# =============================================================================
# 1. Load segments
# =============================================================================

def load_segments(json_path=None):
    """Load Stage 2 segments. Endpoints remain unchanged."""
    if json_path is None:
        json_path = os.path.join("data", "intermediate", "wall_line_segments.json")
    with open(json_path) as f:
        raw = json.load(f)

    segments = []
    for s in raw:
        sx, sy = int(s["start"][0]), int(s["start"][1])
        ex, ey = int(s["end"][0]), int(s["end"][1])
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
# 2. Merge collinear segments
# =============================================================================

def merge_collinear_segments(segments, gap_tol=COLLINEAR_GAP_TOL):
    """
    Merge collinear segments on the same axis that are close together.
    
    This forms continuous walls instead of fragmented pieces.
    """
    horizontal = [s for s in segments if s["orientation"] == "horizontal"]
    vertical = [s for s in segments if s["orientation"] == "vertical"]
    
    merged_h = _merge_axis_segments(horizontal, 'horizontal', gap_tol)
    merged_v = _merge_axis_segments(vertical, 'vertical', gap_tol)
    
    result = merged_h + merged_v
    print(f"Collinear merge: {len(segments)} -> {len(result)} segments")
    return result


def _merge_axis_segments(segments, orientation, gap_tol):
    """Merge segments on the same axis line."""
    if not segments:
        return []
    
    # Group by axis coordinate (y for horizontal, x for vertical)
    axis_groups = defaultdict(list)
    for s in segments:
        if orientation == 'horizontal':
            axis = s["start"][1]
        else:
            axis = s["start"][0]
        axis_groups[axis].append(s)
    
    merged = []
    for axis, segs in axis_groups.items():
        # Sort by start coordinate
        if orientation == 'horizontal':
            segs_sorted = sorted(segs, key=lambda s: s["start"][0])
            intervals = [(s["start"][0], s["end"][0]) for s in segs_sorted]
        else:
            segs_sorted = sorted(segs, key=lambda s: s["start"][1])
            intervals = [(s["start"][1], s["end"][1]) for s in segs_sorted]
        
        # Merge overlapping/nearby intervals
        merged_intervals = []
        for start, end in intervals:
            if not merged_intervals:
                merged_intervals.append([start, end])
            else:
                prev_start, prev_end = merged_intervals[-1]
                # Check if close enough to merge
                if start <= prev_end + gap_tol:
                    merged_intervals[-1][1] = max(prev_end, end)
                else:
                    merged_intervals.append([start, end])
        
        # Create merged segments
        for start, end in merged_intervals:
            if orientation == 'horizontal':
                merged.append({
                    "start": (start, axis),
                    "end": (end, axis),
                    "orientation": orientation
                })
            else:
                merged.append({
                    "start": (axis, start),
                    "end": (axis, end),
                    "orientation": orientation
                })
    
    return merged


# =============================================================================
# 3. Bridge small collinear gaps
# =============================================================================

def bridge_small_gaps(segments, gap_tol=COLLINEAR_GAP_TOL):
    """
    Bridge small gaps between collinear segment endpoints.
    
    This connects walls that have small breaks (not door gaps).
    """
    horizontal = [s for s in segments if s["orientation"] == "horizontal"]
    vertical = [s for s in segments if s["orientation"] == "vertical"]
    
    bridged_h = _bridge_axis_gaps(horizontal, 'horizontal', gap_tol)
    bridged_v = _bridge_axis_gaps(vertical, 'vertical', gap_tol)
    
    result = bridged_h + bridged_v
    bridges = len(result) - len(segments)
    if bridges > 0:
        print(f"Bridged {bridges} small gaps")
    return result


def _bridge_axis_gaps(segments, orientation, gap_tol):
    """Bridge gaps between collinear segments."""
    if not segments:
        return []
    
    # Group by axis coordinate
    axis_groups = defaultdict(list)
    for s in segments:
        if orientation == 'horizontal':
            axis = s["start"][1]
        else:
            axis = s["start"][0]
        axis_groups[axis].append(s)
    
    result = list(segments)
    
    # For each axis, find nearby endpoints and bridge them
    for axis, segs in axis_groups.items():
        endpoints = []
        for s in segs:
            if orientation == 'horizontal':
                endpoints.append((s["start"][0], 'start', s))
                endpoints.append((s["end"][0], 'end', s))
            else:
                endpoints.append((s["start"][1], 'start', s))
                endpoints.append((s["end"][1], 'end', s))
        
        endpoints.sort(key=lambda x: x[0])
        
        # Find gaps between consecutive endpoints
        for i in range(len(endpoints) - 1):
            pos1, type1, seg1 = endpoints[i]
            pos2, type2, seg2 = endpoints[i + 1]
            
            gap = pos2 - pos1
            
            # Only bridge if gap is small and it's an end-to-start gap
            if 0 < gap <= gap_tol and type1 == 'end' and type2 == 'start':
                # Create bridge segment
                if orientation == 'horizontal':
                    bridge = {
                        "start": (pos1, axis),
                        "end": (pos2, axis),
                        "orientation": orientation
                    }
                else:
                    bridge = {
                        "start": (axis, pos1),
                        "end": (axis, pos2),
                        "orientation": orientation
                    }
                result.append(bridge)
    
    return result


# =============================================================================
# 4. Normalize axis coordinates
# =============================================================================

def _cluster_values(values, tol):
    """
    Cluster a list of integer values within *tol* of each other.
    Returns a mapping {original_value: canonical_value}.
    """
    if not values:
        return {}

    uniq = sorted(set(values))
    mapping = {}
    cluster = [uniq[0]]

    for v in uniq[1:]:
        if v - cluster[0] <= tol:
            cluster.append(v)
        else:
            canonical = round(sum(cluster) / len(cluster))
            for cv in cluster:
                mapping[cv] = canonical
            cluster = [v]

    canonical = round(sum(cluster) / len(cluster))
    for cv in cluster:
        mapping[cv] = canonical

    return mapping


def normalize_axis_coordinates(segments, tol=AXIS_SNAP_TOL):
    """
    Snap near-identical axis coordinates.
    - Vertical segments: cluster X values
    - Horizontal segments: cluster Y values
    """
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

    out = []
    for s in segments:
        sx, sy = s["start"]
        ex, ey = s["end"]
        ori = s["orientation"]

        if ori == "vertical":
            sx = x_map.get(sx, sx)
            ex = x_map.get(ex, ex)
            sy = y_map.get(sy, sy)
            ey = y_map.get(ey, ey)
        else:
            sy = y_map.get(sy, sy)
            ey = y_map.get(ey, ey)
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
    print(f"Axis normalization: X clusters={x_clusters} Y clusters={y_clusters} (tol={tol}px)")
    return out


# =============================================================================
# 5. Snap endpoints (close corner gaps)
# =============================================================================

def snap_endpoints(segments, tol=ENDPOINT_SNAP_TOL):
    """
    Snap endpoints that are close to each other.
    
    This closes small gaps at corners and T-junctions.
    """
    # Collect all endpoints
    endpoints = []
    for i, s in enumerate(segments):
        endpoints.append((s["start"], i, 'start'))
        endpoints.append((s["end"], i, 'end'))
    
    # Cluster nearby endpoints
    n = len(endpoints)
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
    
    # Union endpoints within tolerance
    for i in range(n):
        for j in range(i + 1, n):
            p1 = endpoints[i][0]
            p2 = endpoints[j][0]
            dx = p1[0] - p2[0]
            dy = p1[1] - p2[1]
            if dx * dx + dy * dy <= tol * tol:
                union(i, j)
    
    # Compute centroids for each cluster
    clusters = defaultdict(list)
    for i in range(n):
        clusters[find(i)].append(endpoints[i])
    
    # Map original points to snapped points
    snap_map = {}
    for members in clusters.values():
        cx = round(sum(m[0][0] for m in members) / len(members))
        cy = round(sum(m[0][1] for m in members) / len(members))
        for pt, idx, pos in members:
            snap_map[(idx, pos)] = (cx, cy)
    
    # Apply snapping to segments
    snapped_count = 0
    for i, s in enumerate(segments):
        new_start = snap_map.get((i, 'start'), s["start"])
        new_end = snap_map.get((i, 'end'), s["end"])
        
        if new_start != s["start"] or new_end != s["end"]:
            snapped_count += 1
        
        # Update segment
        s["start"] = new_start
        s["end"] = new_end
        
        # Re-canonicalize
        if s["orientation"] == "horizontal":
            if s["start"][0] > s["end"][0]:
                s["start"], s["end"] = s["end"], s["start"]
            s["end"] = (s["end"][0], s["start"][1])
        else:
            if s["start"][1] > s["end"][1]:
                s["start"], s["end"] = s["end"], s["start"]
            s["end"] = (s["start"][0], s["end"][1])
    
    if snapped_count > 0:
        print(f"Snapped {snapped_count} segment endpoints (tol={tol}px)")
    
    return segments


# =============================================================================
# 6. Detect intersections (axis-aligned + T-junctions)
# =============================================================================

def detect_intersections(segments, tol=INTERSECTION_TOL):
    """
    Detect H×V intersections with axis snapping.
    
    For horizontal segment H with y=hy and x-range [hx1, hx2]:
    For vertical segment V with x=vx and y-range [vy1, vy2]:
    If vx is inside [hx1, hx2] AND hy is inside [vy1, vy2]:
        Create node at (vx, hy) - lies on BOTH segment axes.
    
    Returns:
        unique_points: sorted list of intersection (x,y) tuples
        seg_intersections: dict {segment_index: set of intersection points}
    """
    h_indices = [i for i, s in enumerate(segments) if s["orientation"] == "horizontal"]
    v_indices = [i for i, s in enumerate(segments) if s["orientation"] == "vertical"]

    all_points = []
    seg_intersections = defaultdict(set)

    for hi in h_indices:
        h = segments[hi]
        hy = h["start"][1]
        hx1, hx2 = h["start"][0], h["end"][0]

        for vi in v_indices:
            v = segments[vi]
            vx = v["start"][0]
            vy1, vy2 = v["start"][1], v["end"][1]

            # Strict containment check (no tolerance expansion)
            x_in_range = hx1 <= vx <= hx2
            y_in_range = vy1 <= hy <= vy2

            if x_in_range and y_in_range:
                pt = (vx, hy)  # Lies on both segment axes
                all_points.append(pt)
                seg_intersections[hi].add(pt)
                seg_intersections[vi].add(pt)

    unique_points = sorted(set(all_points))
    print(f"Intersections (tol={tol}px): {len(unique_points)}")
    return unique_points, seg_intersections


# =============================================================================
# 7. Collect candidate nodes
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
# 8. Cluster nodes (merge coincident points)
# =============================================================================

def cluster_nodes(points, tol=NODE_MERGE_TOL):
    """
    Merge points within Euclidean distance <= tol.
    Replace each cluster with integer-rounded centroid.
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

    mapping = {}
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
        print(f"Node clustering: {len(pts)} pts -> {len(centroids)} nodes ({merged} merged)")
    else:
        print(f"Node clustering: {len(centroids)} nodes (no merges)")
    return mapping, centroids


# =============================================================================
# 9. Split segments at nodes
# =============================================================================

def split_segments(segments, node_positions, mapping, seg_intersections):
    """
    Split segments at endpoints and intersections only.
    Each segment is split only at nodes that lie on its axis.
    
    Key: Use original intersection coordinates (vx, hy) which lie exactly
    on both segment axes, NOT clustered centroids which may be off-axis.
    """
    edges = []

    for seg_idx, seg in enumerate(segments):
        ori = seg["orientation"]
        sx, sy = seg["start"]
        ex, ey = seg["end"]

        on_seg = set()

        # Add segment's own endpoints (through mapping)
        sp = mapping.get((sx, sy), (sx, sy))
        ep = mapping.get((ex, ey), (ex, ey))
        on_seg.add(sp)
        on_seg.add(ep)

        # Add intersection points - USE ORIGINAL COORDINATES
        for raw_pt in seg_intersections.get(seg_idx, set()):
            on_seg.add(raw_pt)

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
# 10. Build graph
# =============================================================================

def build_graph(sub_edges, node_positions):
    """Assign unique IDs to all points found in edges."""
    all_coords = set()
    for p1, p2 in sub_edges:
        all_coords.add(p1)
        all_coords.add(p2)

    coord_to_id = {c: i for i, c in enumerate(sorted(all_coords))}
    nodes = [{"id": i, "x": c[0], "y": c[1]} for i, c in enumerate(sorted(all_coords))]

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
            continue
        edges.append({
            "start_node": key[0],
            "end_node": key[1],
            "length_px": round(length, 1),
        })

    print(f"Graph: {len(nodes)} nodes, {len(edges)} edges")
    return nodes, edges


# =============================================================================
# 11. Clean graph – remove noise components
# =============================================================================

def clean_graph(nodes, edges, noise_threshold=NOISE_THRESHOLD):
    """Remove noise components (fewer than 2 nodes or total edge length < threshold)."""
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
    print(f"Components: {len(components)} sizes={sizes[:8]}")

    if len(components) <= 1:
        if edges and len(edges) >= len(nodes):
            print("  single component, has cycle")
        return nodes, edges

    keep_ids = set()
    kept_count = 0
    noise_count = 0

    for comp in components:
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
        print("  WARNING: all components below threshold, keeping largest")
        keep_ids = components[0]

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
                "end_node": old_to_new[e["end_node"]],
                "length_px": e["length_px"],
            })

    dropped_n = len(nodes) - len(new_nodes)
    if dropped_n:
        print(f"  Pruned {dropped_n} noise nodes")

    return new_nodes, new_edges


# =============================================================================
# 12. Validate topology
# =============================================================================

def validate_topology(nodes, edges):
    """
    Validate that the graph has closed topology.
    
    Prints statistics and warnings if graph is not properly closed.
    """
    # Build adjacency
    adj = defaultdict(set)
    for e in edges:
        adj[e["start_node"]].add(e["end_node"])
        adj[e["end_node"]].add(e["start_node"])
    
    # Compute degree statistics
    degrees = [len(adj[n["id"]]) for n in nodes]
    avg_degree = sum(degrees) / len(degrees) if degrees else 0
    degree_1 = sum(1 for d in degrees if d == 1)
    degree_2 = sum(1 for d in degrees if d == 2)
    degree_3plus = sum(1 for d in degrees if d >= 3)
    
    print()
    print("=" * 55)
    print("  TOPOLOGY VALIDATION")
    print("=" * 55)
    print(f"  Total nodes: {len(nodes)}")
    print(f"  Total edges: {len(edges)}")
    print(f"  Average degree: {avg_degree:.2f}")
    print(f"  Degree-1 nodes: {degree_1} (dead ends)")
    print(f"  Degree-2 nodes: {degree_2} (pass-through)")
    print(f"  Degree-3+ nodes: {degree_3plus} (junctions)")
    
    # Check success conditions
    issues = []
    
    if len(edges) < len(nodes):
        issues.append("Edges < Nodes (tree-like, no cycles)")
    
    if degree_1 > len(nodes) * 0.3:
        issues.append(f"Too many degree-1 nodes ({degree_1}/{len(nodes)})")
    
    if avg_degree < 1.5:
        issues.append(f"Low average degree ({avg_degree:.2f})")
    
    if issues:
        print()
        print("  ⚠ WARNING: Graph is not topologically closed!")
        for issue in issues:
            print(f"    - {issue}")
        print("  Rooms may not be detected correctly.")
    else:
        print()
        print("  ✓ Graph topology looks good for room detection.")
    
    print("=" * 55)
    
    return len(issues) == 0


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
    print(f"Degree dist: deg-1={d1}, deg-2={d2}, deg-3+={d3}")

    pairs = [(e["start_node"], e["end_node"]) for e in edges]
    dupes = len(pairs) - len(set(pairs))
    zl = sum(1 for e in edges if e["length_px"] < 0.5)
    short = sum(1 for e in edges if e["length_px"] < MIN_EDGE_LEN)
    print(f"Dup edges: {dupes} Zero-len: {zl} Short(<{MIN_EDGE_LEN}px): {short}"
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
    """Visualize final graph overlaid on wall mask."""
    if save_dir is None:
        save_dir = os.path.join("data", "intermediate")
    h, w = img_shape[:2]
    nmap = {n["id"]: (n["x"], n["y"]) for n in nodes}

    mp = os.path.join("data", "intermediate", "binary_wall_mask.png")
    if os.path.exists(mp):
        mask = cv2.imread(mp, cv2.IMREAD_GRAYSCALE)
        if mask is not None:
            bg = cv2.cvtColor((mask * 0.35).astype(np.uint8), cv2.COLOR_GRAY2BGR)
        else:
            bg = np.zeros((h, w, 3), np.uint8)
    else:
        bg = np.zeros((h, w, 3), np.uint8)

    for e in edges:
        cv2.line(bg, nmap[e["start_node"]], nmap[e["end_node"]], (0, 255, 0), 2)
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
    print("  Stage 3: Wall Graph Construction (Closed Topology)")
    print("=" * 55)
    print()

    img_shape = get_image_dimensions()
    print(f"Image: {img_shape[1]}x{img_shape[0]}")
    print(f"Tolerances: axis_snap={AXIS_SNAP_TOL}px endpoint_snap={ENDPOINT_SNAP_TOL}px collinear_gap={COLLINEAR_GAP_TOL}px")
    print()

    path = sys.argv[1] if len(sys.argv) >= 2 else None

    # 1. Load
    segments = load_segments(path)

    # 2. Merge collinear segments
    segments = merge_collinear_segments(segments, COLLINEAR_GAP_TOL)

    # 4. Normalize axis coordinates
    segments = normalize_axis_coordinates(segments, AXIS_SNAP_TOL)

    # 5. Snap endpoints
    segments = snap_endpoints(segments, ENDPOINT_SNAP_TOL)

    # 6. Detect intersections
    intersections, seg_intersections = detect_intersections(segments)

    # 7. Collect candidates
    candidates = collect_candidates(segments, intersections)
    print(f"Candidate points: {len(candidates)}")

    # 8. Cluster nodes
    mapping, node_positions = cluster_nodes(candidates, NODE_MERGE_TOL)

    # 9. Split segments
    sub_edges = split_segments(segments, node_positions, mapping, seg_intersections)

    # 10. Build graph
    nodes, edges = build_graph(sub_edges, node_positions)

    # 11. Clean graph
    nodes, edges = clean_graph(nodes, edges)

    # 12. Validate topology
    is_valid = validate_topology(nodes, edges)

    # 13. Report, save, visualize
    print()
    report(nodes, edges)
    save_graph(nodes, edges)
    visualize(nodes, edges, img_shape)

    print(f"\nFinal: {len(nodes)} nodes, {len(edges)} edges")
    if is_valid:
        print("Stage 3 complete! Graph has closed topology.")
    else:
        print("Stage 3 complete with warnings. Check topology.")


if __name__ == "__main__":
    main()