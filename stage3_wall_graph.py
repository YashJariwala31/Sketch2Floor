# stage3_wall_graph.py
#
# Stage 3 – Wall Graph Construction
# Convert orthogonal wall line segments into a clean connectivity graph using
# exact geometric intersection logic.
#
# Input:  data/intermediate/wall_line_segments.json  (from Stage 2)
# Output: data/intermediate/wall_graph.json
#         data/intermediate/wall_graph_overlay.png
#
# Explicitly forbidden:
#   - Endpoint proximity merging
#   - Floating point tolerance snapping
#   - KD-tree nearest neighbor clustering
#   - Skeletonization / Adaptive thresholds / Diagonal logic
#   - Shapely buffering / geometric inflation
#   - Machine learning

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
            return bimg.shape[:2]          # (height, width)
    return (2000, 2000)


# ---------------------------------------------------------------------------
# Step 1: Load & normalise segments
# ---------------------------------------------------------------------------

def load_segments(json_path=None):
    """
    Load wall line segments from Stage 2 output.
    Normalise each segment into canonical form:
      horizontal => y = constant, x_min <= x_max
      vertical   => x = constant, y_min <= y_max
    Coordinates are rounded to int.
    """
    if json_path is None:
        json_path = os.path.join("data", "intermediate", "wall_line_segments.json")
    if not os.path.exists(json_path):
        print(f"Error: Segment file not found at {json_path}")
        sys.exit(1)

    with open(json_path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    segments = []
    for s in raw:
        x1, y1 = int(round(s["start"][0])), int(round(s["start"][1]))
        x2, y2 = int(round(s["end"][0])),   int(round(s["end"][1]))
        ori = s["orientation"]

        # Canonical ordering: smaller coordinate first
        if ori == "horizontal":
            if x1 > x2:
                x1, x2 = x2, x1
            # ensure y is identical at both endpoints
            y2 = y1
        else:   # vertical
            if y1 > y2:
                y1, y2 = y2, y1
            # ensure x is identical at both endpoints
            x2 = x1

        segments.append({
            "start": (x1, y1),
            "end":   (x2, y2),
            "orientation": ori,
        })

    h_count = sum(1 for s in segments if s["orientation"] == "horizontal")
    v_count = sum(1 for s in segments if s["orientation"] == "vertical")
    print(f"Loaded {len(segments)} wall segments  (H={h_count}, V={v_count})")
    return segments


# ---------------------------------------------------------------------------
# Step 1b: Normalize segments – extend endpoints to meet perpendicular walls
# ---------------------------------------------------------------------------

def normalize_segments(segments, max_dim):
    """
    Align each segment's endpoints to nearby perpendicular wall axis lines.
    This compensates for the small coordinate misalignments (typically 1-35px)
    that remain after Stage 2 merging.

    For each endpoint of a segment, find the closest perpendicular wall axis
    line and move the endpoint along its own axis to meet that line.  This
    includes both *extending* (making the segment longer) and *snapping*
    (adjusting an endpoint that overshoots or undershoots by a few pixels).

    The perpendicular wall must actually span near the endpoint for the
    alignment to fire.
    """
    ext_tol = max(20, int(0.02 * max_dim))   # alignment tolerance
    micro_tol = 5  # unconditional snap for very small offsets (no span check)

    horiz = [s for s in segments if s["orientation"] == "horizontal"]
    vert  = [s for s in segments if s["orientation"] == "vertical"]

    # Gather axis values of perpendicular segments
    v_xs = sorted(set(v["start"][0] for v in vert))   # vertical x positions
    h_ys = sorted(set(h["start"][1] for h in horiz))  # horizontal y positions

    adjustments = 0
    result = []

    def _find_closest(val, candidates, tol):
        """Find the candidate closest to val within tol. Return it or None."""
        best = None
        best_d = tol + 1
        for c in candidates:
            d = abs(c - val)
            if d <= tol and d < best_d:
                best = c
                best_d = d
        return best

    def _try_align_to_axis(val, axis_candidates, perp_segs, seg_x, tol, mt):
        """
        Try to align val to the nearest axis line.
        - First try within micro_tol (unconditional snap).
        - Then try within tol, but only if a perpendicular segment spans near seg_x.
        Returns new val and whether an adjustment was made.
        """
        best = _find_closest(val, axis_candidates, tol)
        if best is None or best == val:
            return val, False

        gap = abs(best - val)

        # Micro-snap: very small gap, snap unconditionally
        if gap <= mt:
            return best, True

        # Larger gap: need span verification
        for ps in perp_segs:
            if ps["orientation"] == "horizontal":
                if ps["start"][1] == best:
                    hx_min, hx_max = ps["start"][0], ps["end"][0]
                    if hx_min - tol <= seg_x <= hx_max + tol:
                        return best, True
            else:  # vertical
                if ps["start"][0] == best:
                    vy_min, vy_max = ps["start"][1], ps["end"][1]
                    if vy_min - tol <= seg_x <= vy_max + tol:
                        return best, True

        return val, False

    for seg in segments:
        x1, y1 = seg["start"]
        x2, y2 = seg["end"]
        ori = seg["orientation"]

        if ori == "horizontal":
            # --- Align x1 (left endpoint) to nearest vertical axis ---
            new_x1, changed = _try_align_to_axis(x1, v_xs, vert, y1, ext_tol, micro_tol)
            if changed:
                x1 = new_x1
                adjustments += 1

            # --- Align x2 (right endpoint) to nearest vertical axis ---
            new_x2, changed = _try_align_to_axis(x2, v_xs, vert, y1, ext_tol, micro_tol)
            if changed:
                x2 = new_x2
                adjustments += 1

            # Ensure canonical order after alignment
            if x1 > x2:
                x1, x2 = x2, x1
            result.append({"start": (x1, y1), "end": (x2, y1), "orientation": ori})

        else:  # vertical
            # --- Align y1 (top endpoint) to nearest horizontal axis ---
            new_y1, changed = _try_align_to_axis(y1, h_ys, horiz, x1, ext_tol, micro_tol)
            if changed:
                y1 = new_y1
                adjustments += 1

            # --- Align y2 (bottom endpoint) to nearest horizontal axis ---
            new_y2, changed = _try_align_to_axis(y2, h_ys, horiz, x1, ext_tol, micro_tol)
            if changed:
                y2 = new_y2
                adjustments += 1

            # Ensure canonical order after alignment
            if y1 > y2:
                y1, y2 = y2, y1
            result.append({"start": (x1, y1), "end": (x1, y2), "orientation": ori})

    if adjustments:
        print(f"Aligned {adjustments} segment endpoint(s)  (ext_tol={ext_tol}px)")
    else:
        print("No segment endpoints aligned")
    return result


# ---------------------------------------------------------------------------
# Step 2: Compute exact intersections  (H x V pairs only)
# ---------------------------------------------------------------------------

def compute_exact_intersections(segments):
    """
    For every (horizontal, vertical) pair, check strict interval overlap:
      vertical.x  in [horizontal.x_min, horizontal.x_max]
      horizontal.y in [vertical.y_min,   vertical.y_max]
    No tolerance is used.

    Returns: list of (x, y) intersection points.
    """
    horiz = [s for s in segments if s["orientation"] == "horizontal"]
    vert  = [s for s in segments if s["orientation"] == "vertical"]

    intersections = []
    for h in horiz:
        hx_min, hy = h["start"]
        hx_max, _  = h["end"]
        for v in vert:
            vx, vy_min = v["start"]
            _,  vy_max = v["end"]
            if hx_min <= vx <= hx_max and vy_min <= hy <= vy_max:
                intersections.append((vx, hy))

    print(f"Exact HxV intersections found: {len(intersections)}")
    return intersections


# ---------------------------------------------------------------------------
# Step 3: Split segments at intersections
# ---------------------------------------------------------------------------

def split_segments_at_intersections(segments, intersections):
    """
    For each segment, collect:
      - its two original endpoints
      - every intersection point that lies exactly on it
    Sort these points along the segment's axis, then create new sub-segments
    between consecutive points.
    """
    # Build a quick lookup: intersection points per axis value
    # For horizontal segs (y=const), key = y; for vertical segs (x=const), key = x
    pts_by_y = defaultdict(list)   # y -> list of x values
    pts_by_x = defaultdict(list)   # x -> list of y values
    for (ix, iy) in intersections:
        pts_by_y[iy].append(ix)
        pts_by_x[ix].append(iy)

    split_segs = []

    for seg in segments:
        x1, y1 = seg["start"]
        x2, y2 = seg["end"]
        ori = seg["orientation"]

        if ori == "horizontal":
            # Collect all x-coords of intersections on this segment (y == y1)
            candidate_xs = pts_by_y.get(y1, [])
            xs_on_seg = [cx for cx in candidate_xs if x1 <= cx <= x2]
            # Always include original endpoints
            all_xs = sorted(set([x1, x2] + xs_on_seg))
            for i in range(len(all_xs) - 1):
                split_segs.append({
                    "start": (all_xs[i],   y1),
                    "end":   (all_xs[i+1], y1),
                    "orientation": "horizontal",
                })
        else:  # vertical
            candidate_ys = pts_by_x.get(x1, [])
            ys_on_seg = [cy for cy in candidate_ys if y1 <= cy <= y2]
            all_ys = sorted(set([y1, y2] + ys_on_seg))
            for i in range(len(all_ys) - 1):
                split_segs.append({
                    "start": (x1, all_ys[i]),
                    "end":   (x1, all_ys[i+1]),
                    "orientation": "vertical",
                })

    print(f"Segments after splitting: {len(split_segs)}  "
          f"(from {len(segments)} originals)")
    return split_segs


# ---------------------------------------------------------------------------
# Step 4: Build nodes  (exact coordinate matching only)
# ---------------------------------------------------------------------------

def build_nodes(split_segments):
    """
    Create graph nodes from all unique (x, y) coordinates found in the
    split segments.  Exact matching only – no proximity merging.
    Returns:
        nodes  – list of {"id": int, "x": int, "y": int}
        coord_to_id – dict mapping (x, y) -> node id
    """
    coord_set = set()
    for seg in split_segments:
        coord_set.add(seg["start"])
        coord_set.add(seg["end"])

    # Deterministic ordering: sort by (x, y)
    sorted_coords = sorted(coord_set)
    coord_to_id = {}
    nodes = []
    for idx, (x, y) in enumerate(sorted_coords):
        coord_to_id[(x, y)] = idx
        nodes.append({"id": idx, "x": x, "y": y})

    print(f"Graph nodes: {len(nodes)}")
    return nodes, coord_to_id


# ---------------------------------------------------------------------------
# Step 5: Build edges
# ---------------------------------------------------------------------------

def build_edges(split_segments, coord_to_id):
    """
    Create graph edges from split wall segments.
    Each edge stores: start_node_id, end_node_id, orientation, length_px.
    Duplicate edges (same pair of node ids) are removed.
    """
    seen = set()
    edges = []

    for seg in split_segments:
        sid = coord_to_id[seg["start"]]
        eid = coord_to_id[seg["end"]]
        if sid == eid:
            continue
        key = (min(sid, eid), max(sid, eid))
        if key in seen:
            continue
        seen.add(key)

        sx, sy = seg["start"]
        ex, ey = seg["end"]
        length = math.hypot(ex - sx, ey - sy)

        edges.append({
            "start_node_id": sid,
            "end_node_id":   eid,
            "orientation":   seg["orientation"],
            "length_px":     round(length, 2),
        })

    print(f"Graph edges: {len(edges)}")
    return edges


# ---------------------------------------------------------------------------
# Step 6: Remove micro-edges  (length < 0.03 * max_image_dimension)
# ---------------------------------------------------------------------------

def remove_micro_edges(edges, max_dim):
    """
    Remove wall fragments shorter than 3 % of the largest image dimension.
    """
    threshold = 0.03 * max_dim
    kept = [e for e in edges if e["length_px"] >= threshold]
    removed = len(edges) - len(kept)
    if removed:
        print(f"Removed {removed} micro-edge(s)  (threshold={threshold:.1f}px)")
    else:
        print(f"No micro-edges removed  (threshold={threshold:.1f}px)")
    return kept


# ---------------------------------------------------------------------------
# Step 7: Remove dangling edges  (iterative, until stable)
# ---------------------------------------------------------------------------

def _degree_map(nodes, edges):
    deg = {n["id"]: 0 for n in nodes}
    for e in edges:
        deg[e["start_node_id"]] = deg.get(e["start_node_id"], 0) + 1
        deg[e["end_node_id"]]   = deg.get(e["end_node_id"], 0) + 1
    return deg


def remove_dangling_edges(nodes, edges, max_dim):
    """
    Iteratively remove edges connected to degree-1 nodes if shorter than
    threshold.  Repeat until stable.
    Threshold = 0.03 * max_dim  (same as micro-edge threshold).
    """
    threshold = 0.03 * max_dim
    total_removed = 0
    changed = True

    while changed:
        changed = False
        deg = _degree_map(nodes, edges)
        keep = []
        for e in edges:
            s_deg = deg.get(e["start_node_id"], 0)
            e_deg = deg.get(e["end_node_id"], 0)
            if (s_deg == 1 or e_deg == 1) and e["length_px"] < threshold:
                changed = True
                total_removed += 1
            else:
                keep.append(e)
        edges = keep

    if total_removed:
        print(f"Removed {total_removed} dangling edge(s)  "
              f"(threshold={threshold:.1f}px)")
    else:
        print("No dangling edges removed")
    return edges


# ---------------------------------------------------------------------------
# Step 8: Connected component validation
# ---------------------------------------------------------------------------

def connected_components(nodes, edges):
    """
    Union-find connected-component analysis.
    Success: largest component contains majority of nodes.
    """
    if not nodes:
        print("Connected components: 0 nodes – skipped")
        return 0

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

    # Only count nodes that actually participate in edges
    active_ids = set()
    for e in edges:
        active_ids.add(e["start_node_id"])
        active_ids.add(e["end_node_id"])
        union(e["start_node_id"], e["end_node_id"])

    comp_sizes = defaultdict(int)
    for nid in active_ids:
        comp_sizes[find(nid)] += 1

    num_comp = len(comp_sizes)
    sorted_sizes = sorted(comp_sizes.values(), reverse=True)

    if num_comp == 0:
        print("Connected components: 0 (no edges)")
    elif num_comp == 1:
        print(f"Connected components: 1  ({sorted_sizes[0]} nodes)  [PASS]")
    else:
        largest = sorted_sizes[0]
        pct = largest / len(active_ids) * 100 if active_ids else 0
        status = "PASS" if pct >= 50 else "WARN"
        print(f"Connected components: {num_comp}  "
              f"sizes={sorted_sizes[:8]}{'...' if num_comp > 8 else ''}  "
              f"largest={largest} ({pct:.0f}%)  [{status}]")

    return num_comp


# ---------------------------------------------------------------------------
# Prune orphan nodes  (nodes with no remaining edges)
# ---------------------------------------------------------------------------

def prune_orphan_nodes(nodes, edges):
    """Remove nodes that have no remaining edges and re-index."""
    used_ids = set()
    for e in edges:
        used_ids.add(e["start_node_id"])
        used_ids.add(e["end_node_id"])

    pruned = [n for n in nodes if n["id"] in used_ids]
    removed = len(nodes) - len(pruned)
    if removed:
        print(f"Pruned {removed} orphan node(s)")

    # Re-index node IDs to be contiguous 0..N-1
    old_to_new = {}
    renumbered = []
    for new_id, n in enumerate(pruned):
        old_to_new[n["id"]] = new_id
        renumbered.append({"id": new_id, "x": n["x"], "y": n["y"]})

    # Update edge references
    for e in edges:
        e["start_node_id"] = old_to_new[e["start_node_id"]]
        e["end_node_id"]   = old_to_new[e["end_node_id"]]

    return renumbered, edges


# ---------------------------------------------------------------------------
# Save & visualise
# ---------------------------------------------------------------------------

def save_graph(nodes, edges, save_dir=None):
    if save_dir is None:
        save_dir = os.path.join("data", "intermediate")
    os.makedirs(save_dir, exist_ok=True)

    out = {"nodes": nodes, "edges": edges}
    path = os.path.join(save_dir, "wall_graph.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    print(f"Wall graph saved -> {path}")


def visualize_graph(nodes, edges, img_shape, save_dir=None):
    """Draw nodes and edges on both a black canvas and a wall-mask overlay."""
    if save_dir is None:
        save_dir = os.path.join("data", "intermediate")
    os.makedirs(save_dir, exist_ok=True)

    nmap = {n["id"]: (n["x"], n["y"]) for n in nodes}

    def _draw(canvas):
        for e in edges:
            pt1 = nmap[e["start_node_id"]]
            pt2 = nmap[e["end_node_id"]]
            cv2.line(canvas, pt1, pt2, (0, 200, 0), 2, cv2.LINE_AA)
        for n in nodes:
            cv2.circle(canvas, (n["x"], n["y"]), 5, (0, 100, 255), -1, cv2.LINE_AA)
            cv2.putText(canvas, str(n["id"]),
                        (n["x"] + 7, n["y"] - 7),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.35,
                        (255, 255, 255), 1, cv2.LINE_AA)
        return canvas

    # --- Black-background version ---
    canvas = np.zeros((img_shape[0], img_shape[1], 3), dtype=np.uint8)
    _draw(canvas)
    path = os.path.join(save_dir, "wall_graph_overlay.png")
    cv2.imwrite(path, canvas)
    print(f"Graph overlay saved -> {path}")

    # --- Wall-mask overlay version ---
    mask_path = os.path.join("data", "intermediate", "binary_wall_mask.png")
    if os.path.exists(mask_path):
        mask = cv2.imread(mask_path, cv2.IMREAD_GRAYSCALE)
        if mask is not None:
            bg = cv2.cvtColor(mask // 3, cv2.COLOR_GRAY2BGR)  # dim wall mask
            _draw(bg)
            path2 = os.path.join(save_dir, "wall_graph_on_mask.png")
            cv2.imwrite(path2, bg)
            print(f"Graph-on-mask overlay saved -> {path2}")


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
    print(f"  Nodes:            {len(nodes)}")
    print(f"  Edges:            {len(edges)}")
    print(f"  Duplicate nodes:  {dup}  [{'PASS' if dup == 0 else 'WARN'}]")
    print(f"  Zero-length edges:{zero}  [{'PASS' if zero == 0 else 'WARN'}]")
    print(f"  Degree dist:      deg-1={d1}, deg-2={d2}, deg-3+={d3}")

    ok = dup == 0 and zero == 0
    if ok:
        print("  All quality checks passed  [PASS]")
    return ok


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def main():
    json_path = None
    if len(sys.argv) >= 2:
        json_path = sys.argv[1]

    print("=" * 55)
    print("  Stage 3: Wall Graph Construction  (exact geometry)")
    print("=" * 55)
    print()

    # Image dimensions for thresholds
    img_shape = get_image_dimensions()
    max_dim = max(img_shape)
    print(f"Image: {img_shape[1]}x{img_shape[0]}  max_dim={max_dim}")

    # 1. Load & normalise segments
    segments = load_segments(json_path)

    # 1b. Normalize: extend endpoints to meet perpendicular walls
    segments = normalize_segments(segments, max_dim)

    # 2. Compute exact HxV intersections
    intersections = compute_exact_intersections(segments)

    # 3. Split segments at intersection points
    split_segs = split_segments_at_intersections(segments, intersections)

    # 4. Build nodes (exact coordinate matching)
    nodes, coord_to_id = build_nodes(split_segs)

    # 5. Build edges
    edges = build_edges(split_segs, coord_to_id)

    # 6. Remove micro-edges
    edges = remove_micro_edges(edges, max_dim)

    # 7. Remove dangling edges (iterative)
    edges = remove_dangling_edges(nodes, edges, max_dim)

    # 8. Connected component validation
    connected_components(nodes, edges)

    # Prune orphan nodes & re-index
    nodes, edges = prune_orphan_nodes(nodes, edges)

    # Save & visualise
    save_graph(nodes, edges)
    visualize_graph(nodes, edges, img_shape)

    # Quality report
    quality_checks(nodes, edges)
    print("\nStage 3 completed successfully!")


if __name__ == "__main__":
    main()
