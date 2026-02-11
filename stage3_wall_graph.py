# stage3_wall_graph.py
#
# Stage 3 - Wall Graph Construction
# Convert merged wall line segments into a clean topological wall connectivity
# graph suitable for room detection.
#
# Input:  data/intermediate/wall_line_segments.json  (from Stage 2)
# Output: data/intermediate/wall_graph.json
#         data/intermediate/wall_graph_overlay.png

import sys
import os
import json
import math
import numpy as np
import cv2
from collections import defaultdict


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_image_dimensions():
    """Read the binary wall mask to determine image dimensions."""
    binary_path = os.path.join("data", "intermediate", "binary_wall_mask.png")
    if os.path.exists(binary_path):
        bimg = cv2.imread(binary_path, cv2.IMREAD_GRAYSCALE)
        if bimg is not None:
            return bimg.shape[:2]
    return (2000, 2000)


# ---------------------------------------------------------------------------
# 1. Load segments
# ---------------------------------------------------------------------------

def load_segments(json_path=None):
    """Load wall line segments from Stage 2 output and normalise to int."""
    if json_path is None:
        json_path = os.path.join("data", "intermediate", "wall_line_segments.json")
    if not os.path.exists(json_path):
        print(f"Error: Segment file not found at {json_path}")
        sys.exit(1)
    with open(json_path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    segments = []
    for idx, s in enumerate(raw):
        x1, y1 = int(round(s["start"][0])), int(round(s["start"][1]))
        x2, y2 = int(round(s["end"][0])), int(round(s["end"][1]))
        ori = s["orientation"]
        if ori == "horizontal":
            if x1 > x2:
                x1, x2 = x2, x1
        else:
            if y1 > y2:
                y1, y2 = y2, y1
        segments.append({
            "idx": idx,
            "start": (x1, y1),
            "end": (x2, y2),
            "orientation": ori,
        })
    h_count = sum(1 for s in segments if s["orientation"] == "horizontal")
    v_count = sum(1 for s in segments if s["orientation"] == "vertical")
    print(f"Loaded {len(segments)} wall segments (H: {h_count}, V: {v_count})")
    return segments


# ---------------------------------------------------------------------------
# 2-3. Build points with segment membership tracking
# ---------------------------------------------------------------------------

def _point_on_seg(px, py, seg, tol=0):
    """Check if point (px,py) lies on segment within tolerance."""
    x1, y1 = seg["start"]
    x2, y2 = seg["end"]
    if seg["orientation"] == "horizontal":
        return abs(py - y1) <= tol and (x1 - tol) <= px <= (x2 + tol)
    else:
        return abs(px - x1) <= tol and (y1 - tol) <= py <= (y2 + tol)


def compute_all_graph_points(segments, max_dim):
    """
    Build the full set of graph node candidates with segment membership.

    Each point tracks which segment indices it belongs to. This ensures
    that when segments are later split, every point is found on the correct
    segments.

    Returns: list of (x, y, set_of_segment_indices)
    """
    snap_tol = max(5, int(0.01 * max_dim))
    corner_tol = max(15, int(0.025 * max_dim))

    # point -> set of segment indices
    point_segs = defaultdict(set)

    # --- (A) All segment endpoints ---
    for seg in segments:
        point_segs[seg["start"]].add(seg["idx"])
        point_segs[seg["end"]].add(seg["idx"])

    # --- (B) Exact H x V intersections ---
    horiz = [s for s in segments if s["orientation"] == "horizontal"]
    vert = [s for s in segments if s["orientation"] == "vertical"]
    exact_count = 0
    for h in horiz:
        hx1, hy = h["start"]
        hx2, _ = h["end"]
        for v in vert:
            vx, vy1 = v["start"]
            _, vy2 = v["end"]
            if hx1 <= vx <= hx2 and vy1 <= hy <= vy2:
                pt = (vx, hy)
                point_segs[pt].add(h["idx"])
                point_segs[pt].add(v["idx"])
                exact_count += 1

    # --- (C) T-junction snap: endpoint near body of another segment ---
    snap_count = 0
    for seg in segments:
        for ep_key in ("start", "end"):
            px, py = seg[ep_key]
            for other in segments:
                if seg["idx"] == other["idx"]:
                    continue
                ox1, oy1 = other["start"]
                ox2, oy2 = other["end"]
                if other["orientation"] == "horizontal":
                    # other is y=oy1, x in [ox1, ox2]
                    if (ox1 - snap_tol <= px <= ox2 + snap_tol
                            and abs(py - oy1) <= snap_tol):
                        proj_x = max(ox1, min(ox2, px))
                        pt = (proj_x, oy1)
                        point_segs[pt].add(seg["idx"])
                        point_segs[pt].add(other["idx"])
                        snap_count += 1
                else:
                    # other is x=ox1, y in [oy1, oy2]
                    if (oy1 - snap_tol <= py <= oy2 + snap_tol
                            and abs(px - ox1) <= snap_tol):
                        proj_y = max(oy1, min(oy2, py))
                        pt = (ox1, proj_y)
                        point_segs[pt].add(seg["idx"])
                        point_segs[pt].add(other["idx"])
                        snap_count += 1

    # --- (D) L-corner: endpoints of H-V pairs that are close ---
    corner_count = 0
    for h in horiz:
        for h_ep in ("start", "end"):
            hx, hy = h[h_ep]
            for v in vert:
                for v_ep in ("start", "end"):
                    vx, vy = v[v_ep]
                    d = math.hypot(hx - vx, hy - vy)
                    if 0 < d <= corner_tol:
                        # Create intersection at the axis crossing point
                        pt = (vx, hy)
                        point_segs[pt].add(h["idx"])
                        point_segs[pt].add(v["idx"])
                        corner_count += 1

    print(f"Intersections: {exact_count} exact + {snap_count} T-snap + "
          f"{corner_count} L-corner (snap_tol={snap_tol}, corner_tol={corner_tol})")
    print(f"Unique candidate points: {len(point_segs)}")

    # Convert to list form
    result = []
    for (x, y), seg_ids in point_segs.items():
        result.append((x, y, seg_ids))
    return result


# ---------------------------------------------------------------------------
# 4. Merge near-duplicate points
# ---------------------------------------------------------------------------

def merge_near_points(point_list, tolerance=5):
    """
    Union-find merge: any two points within `tolerance` px (Chebyshev)
    collapse into their centroid.  Segment membership sets are unioned.
    """
    n = len(point_list)
    parent = list(range(n))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    coords = [(p[0], p[1]) for p in point_list]
    for i in range(n):
        for j in range(i + 1, n):
            dx = abs(coords[i][0] - coords[j][0])
            dy = abs(coords[i][1] - coords[j][1])
            if dx <= tolerance and dy <= tolerance:
                union(i, j)

    groups = {}
    for i in range(n):
        r = find(i)
        groups.setdefault(r, []).append(i)

    merged = []
    for indices in groups.values():
        xs = [point_list[i][0] for i in indices]
        ys = [point_list[i][1] for i in indices]
        cx = int(round(sum(xs) / len(xs)))
        cy = int(round(sum(ys) / len(ys)))
        all_segs = set()
        for i in indices:
            all_segs.update(point_list[i][2])
        merged.append((cx, cy, all_segs))

    removed = n - len(merged)
    if removed:
        print(f"Merged {removed} near-duplicate points (tolerance={tolerance}px)")
    print(f"Nodes after merge: {len(merged)}")
    return merged


# ---------------------------------------------------------------------------
# 5. Build graph nodes
# ---------------------------------------------------------------------------

def build_nodes(merged_points):
    """Assign sequential integer IDs. Returns nodes list and seg->nodes map."""
    nodes = []
    seg_to_nodes = defaultdict(list)
    for idx, (x, y, seg_ids) in enumerate(merged_points):
        node = {"id": idx, "x": x, "y": y}
        nodes.append(node)
        for sid in seg_ids:
            seg_to_nodes[sid].append(node)
    return nodes, seg_to_nodes


# ---------------------------------------------------------------------------
# 6. Build edges by splitting segments at their registered nodes
# ---------------------------------------------------------------------------

def build_edges(segments, seg_to_nodes):
    """
    For each segment, sort its registered nodes along the segment axis,
    then create an edge between every consecutive pair.
    """
    edges = []
    for seg in segments:
        nodes_on = seg_to_nodes.get(seg["idx"], [])
        if len(nodes_on) < 2:
            continue
        if seg["orientation"] == "horizontal":
            nodes_on.sort(key=lambda n: n["x"])
        else:
            nodes_on.sort(key=lambda n: n["y"])

        for i in range(len(nodes_on) - 1):
            a, b = nodes_on[i], nodes_on[i + 1]
            if a["id"] == b["id"]:
                continue
            length = math.hypot(b["x"] - a["x"], b["y"] - a["y"])
            if length > 0:
                edges.append({
                    "start_node": a["id"],
                    "end_node": b["id"],
                    "length_px": round(length, 2),
                })

    # Deduplicate
    seen = set()
    unique = []
    for e in edges:
        key = (min(e["start_node"], e["end_node"]),
               max(e["start_node"], e["end_node"]))
        if key not in seen:
            seen.add(key)
            unique.append(e)
    print(f"Graph edges after splitting: {len(unique)}")
    return unique


# ---------------------------------------------------------------------------
# 7. Remove dangling edges
# ---------------------------------------------------------------------------

def _degree_map(nodes, edges):
    deg = {n["id"]: 0 for n in nodes}
    for e in edges:
        deg[e["start_node"]] += 1
        deg[e["end_node"]] += 1
    return deg


def remove_dangling_edges(nodes, edges, min_length):
    """
    Iteratively remove edges where at least one endpoint is degree-1 and
    the edge is shorter than min_length. Repeat until stable.
    """
    changed = True
    removed_total = 0
    while changed:
        changed = False
        deg = _degree_map(nodes, edges)
        keep = []
        for e in edges:
            s_deg = deg[e["start_node"]]
            e_deg = deg[e["end_node"]]
            if (s_deg == 1 or e_deg == 1) and e["length_px"] < min_length:
                changed = True
                removed_total += 1
            else:
                keep.append(e)
        edges = keep
    if removed_total:
        print(f"Removed {removed_total} dangling short edge(s) "
              f"(min_length={min_length:.1f}px)")
    else:
        print("No dangling edges removed")
    return edges


# ---------------------------------------------------------------------------
# 8. Connected component analysis
# ---------------------------------------------------------------------------

def connected_components(nodes, edges):
    """Union-find connected-component analysis. Reports diagnostics only."""
    parent = {n["id"]: n["id"] for n in nodes}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for e in edges:
        union(e["start_node"], e["end_node"])

    comp_sizes = {}
    for n in nodes:
        r = find(n["id"])
        comp_sizes[r] = comp_sizes.get(r, 0) + 1

    num_components = len(comp_sizes)
    sorted_comps = sorted(comp_sizes.values(), reverse=True)

    if num_components == 1:
        print(f"Connected components: 1 (single component, {sorted_comps[0]} nodes)")
    else:
        print(f"Connected components: {num_components}  "
              f"sizes: {sorted_comps[:8]}{'...' if num_components > 8 else ''}")
    return num_components


# ---------------------------------------------------------------------------
# 9. Prune orphan nodes
# ---------------------------------------------------------------------------

def prune_orphan_nodes(nodes, edges):
    """Remove nodes that have no remaining edges."""
    used = set()
    for e in edges:
        used.add(e["start_node"])
        used.add(e["end_node"])
    pruned = [n for n in nodes if n["id"] in used]
    removed = len(nodes) - len(pruned)
    if removed:
        print(f"Pruned {removed} orphan node(s)")
    return pruned


# ---------------------------------------------------------------------------
# 10. Save & visualise
# ---------------------------------------------------------------------------

def save_graph(nodes, edges, save_dir=None):
    if save_dir is None:
        save_dir = os.path.join("data", "intermediate")
    os.makedirs(save_dir, exist_ok=True)
    out = {"nodes": nodes, "edges": edges}
    path = os.path.join(save_dir, "wall_graph.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    print(f"Wall graph saved to: {path}")


def visualize_graph(nodes, edges, img_shape, save_dir=None):
    """Draw nodes (circles) and edges (lines) on a black canvas."""
    if save_dir is None:
        save_dir = os.path.join("data", "intermediate")
    os.makedirs(save_dir, exist_ok=True)

    canvas = np.zeros((img_shape[0], img_shape[1], 3), dtype=np.uint8)
    nmap = {n["id"]: (n["x"], n["y"]) for n in nodes}

    for e in edges:
        cv2.line(canvas, nmap[e["start_node"]], nmap[e["end_node"]],
                 (0, 200, 0), 2, cv2.LINE_AA)
    for n in nodes:
        cv2.circle(canvas, (n["x"], n["y"]), 5, (0, 100, 255), -1, cv2.LINE_AA)
        cv2.putText(canvas, str(n["id"]), (n["x"] + 7, n["y"] - 7),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 255, 255), 1,
                    cv2.LINE_AA)

    path = os.path.join(save_dir, "wall_graph_overlay.png")
    cv2.imwrite(out_path := path, canvas)
    print(f"Graph overlay saved to: {out_path}")


# ---------------------------------------------------------------------------
# Quality checks
# ---------------------------------------------------------------------------

def quality_checks(nodes, edges):
    coords = [(n["x"], n["y"]) for n in nodes]
    dup = len(coords) - len(set(coords))
    zero = sum(1 for e in edges if e["length_px"] == 0)
    deg = _degree_map(nodes, edges)
    d1 = sum(1 for v in deg.values() if v == 1)
    d2 = sum(1 for v in deg.values() if v == 2)
    d3 = sum(1 for v in deg.values() if v >= 3)

    print("\n--- Quality Checks ---")
    print(f"  Nodes: {len(nodes)}")
    print(f"  Edges: {len(edges)}")
    print(f"  Duplicate nodes: {dup}  [{'PASS' if dup == 0 else 'WARN'}]")
    print(f"  Zero-length edges: {zero}  [{'PASS' if zero == 0 else 'WARN'}]")
    print(f"  Degree distribution: deg-1={d1}, deg-2={d2}, deg-3+={d3}")
    ok = dup == 0 and zero == 0
    if ok:
        print("  All quality checks passed [PASS]")
    return ok


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    json_path = None
    if len(sys.argv) >= 2:
        json_path = sys.argv[1]

    print("Stage 3: Wall Graph Construction")
    print("=" * 50)

    img_shape = get_image_dimensions()
    max_dim = max(img_shape)
    print(f"Image: {img_shape[1]}x{img_shape[0]} (max_dim={max_dim})")

    # Step 1 - Load
    segments = load_segments(json_path)

    # Step 2-3 - Compute all graph points with segment membership
    point_list = compute_all_graph_points(segments, max_dim)

    # Step 4 - Merge near-duplicates
    merge_tol = max(3, int(0.003 * max_dim))
    merged = merge_near_points(point_list, tolerance=merge_tol)

    # Step 5 - Build nodes
    nodes, seg_to_nodes = build_nodes(merged)

    # Step 6 - Build edges
    edges = build_edges(segments, seg_to_nodes)

    # Step 7 - Remove dangling short stubs
    min_dangle = 0.10 * max_dim
    edges = remove_dangling_edges(nodes, edges, min_dangle)

    # Step 8 - Connected components (report only)
    num_comp = connected_components(nodes, edges)

    # Step 9 - Prune orphans
    nodes = prune_orphan_nodes(nodes, edges)

    # Save & visualise
    save_graph(nodes, edges)
    visualize_graph(nodes, edges, img_shape)

    # Quality
    quality_checks(nodes, edges)
    print("\nStage 3 completed successfully!")


if __name__ == "__main__":
    main()
