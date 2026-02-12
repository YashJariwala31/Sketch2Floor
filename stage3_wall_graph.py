# stage3_wall_graph.py
#
# Stage 3 - Wall Graph Construction
# Construct a geometrically accurate connectivity graph from merged wall
# segments produced by Stage 2.
#
# Input:  data/intermediate/wall_line_segments.json  (from Stage 2)
# Output: data/intermediate/wall_graph.json
#         data/intermediate/wall_graph_overlay.png
#         data/intermediate/wall_graph_on_mask.png
#
# Processing pipeline (per spec):
#   1. Intersection computation (tolerance_px=6)
#   2. Endpoint injection
#   3. Point deduplication  (tolerance_px=6)
#   4. Graph construction   (nodes + edges)
#   5. Dangling edge removal (min_length_px=20)
#   6. Connected component validation

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
            y2 = y1
        else:   # vertical
            if y1 > y2:
                y1, y2 = y2, y1
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
# Step 1b: Normalize segments - extend/snap endpoints to perpendicular walls
# ---------------------------------------------------------------------------

def normalize_segments(segments, max_dim):
    """
    Extend/snap segment endpoints to nearby perpendicular wall axis lines.
    Uses aggressive tolerance (10% of max_dim) to handle hand-drawn sketches
    where inner walls stop well short of the outer boundary.

    Runs iteratively since extending one endpoint may create new opportunities
    for other segments to connect.
    """
    ext_tol = max(40, int(0.10 * max_dim))    # 200px at 2000px - aggressive
    micro_tol = max(8, int(0.015 * max_dim))  # 30px unconditional snap

    def _run_one_pass(segs):
        horiz = [s for s in segs if s["orientation"] == "horizontal"]
        vert  = [s for s in segs if s["orientation"] == "vertical"]
        v_xs = sorted(set(v["start"][0] for v in vert))
        h_ys = sorted(set(h["start"][1] for h in horiz))

        adjustments = 0
        result = []

        def _try_snap(val, axis_candidates, perp_segs, seg_coord, tol, mt, is_horiz, direction):
            """Try snapping val to a perpendicular axis within tol.
            direction: -1 = only snap to smaller values (extend left/up),
                       +1 = only snap to larger values (extend right/down).
            Micro-snaps (gap <= mt) are exempt from direction constraint."""
            candidates = []
            for c in axis_candidates:
                d = abs(c - val)
                if d == 0:
                    continue
                if d > tol:
                    continue
                # For non-micro snaps, enforce direction constraint
                if d > mt:
                    if direction == -1 and c > val:
                        continue  # want to go left/up but candidate is right/down
                    if direction == +1 and c < val:
                        continue  # want to go right/down but candidate is left/up
                candidates.append((d, c))
            if not candidates:
                return val, False
            candidates.sort()

            for gap, best in candidates:
                # Micro-snap: very small gap, snap unconditionally
                if gap <= mt:
                    return best, True

                # Span verification: perpendicular segment must cover seg_coord
                for ps in perp_segs:
                    if is_horiz:
                        if ps["start"][0] == best:
                            vy_min, vy_max = ps["start"][1], ps["end"][1]
                            if vy_min - tol <= seg_coord <= vy_max + tol:
                                return best, True
                    else:
                        if ps["start"][1] == best:
                            hx_min, hx_max = ps["start"][0], ps["end"][0]
                            if hx_min - tol <= seg_coord <= hx_max + tol:
                                return best, True

            return val, False

        for seg in segs:
            x1, y1 = seg["start"]
            x2, y2 = seg["end"]
            ori = seg["orientation"]

            if ori == "horizontal":
                # Left endpoint: only extend left (dir=-1) or micro-snap
                new_x1, ch1 = _try_snap(x1, v_xs, vert, y1, ext_tol, micro_tol, True, -1)
                # Right endpoint: only extend right (dir=+1) or micro-snap
                new_x2, ch2 = _try_snap(x2, v_xs, vert, y1, ext_tol, micro_tol, True, +1)
                if ch1: x1 = new_x1; adjustments += 1
                if ch2: x2 = new_x2; adjustments += 1
                if x1 > x2: x1, x2 = x2, x1
                result.append({"start": (x1, y1), "end": (x2, y1), "orientation": ori})
            else:
                # Top endpoint: only extend up (dir=-1) or micro-snap
                new_y1, ch1 = _try_snap(y1, h_ys, horiz, x1, ext_tol, micro_tol, False, -1)
                # Bottom endpoint: only extend down (dir=+1) or micro-snap
                new_y2, ch2 = _try_snap(y2, h_ys, horiz, x1, ext_tol, micro_tol, False, +1)
                if ch1: y1 = new_y1; adjustments += 1
                if ch2: y2 = new_y2; adjustments += 1
                if y1 > y2: y1, y2 = y2, y1
                result.append({"start": (x1, y1), "end": (x1, y2), "orientation": ori})

        return result, adjustments

    total_adj = 0
    for pass_num in range(3):
        segments, adj = _run_one_pass(segments)
        total_adj += adj
        if adj == 0:
            break

    if total_adj:
        print(f"Normalized {total_adj} endpoint(s) in {pass_num+1} pass(es)"
              f"  (ext_tol={ext_tol}px)")
    else:
        print("No normalization needed")
    return segments


# ---------------------------------------------------------------------------
# Step 2: Compute intersections WITH tolerance
# ---------------------------------------------------------------------------

def compute_intersections(segments, tolerance=6):
    """
    For every (horizontal, vertical) pair, check if projections overlap
    within tolerance and compute (x, y) intersection point.

    The intersection point is placed at (vx, hy) - the exact geometric
    crossing - but the overlap check allows tolerance for near-misses.
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
            # Check overlap with tolerance
            if (hx_min - tolerance <= vx <= hx_max + tolerance and
                    vy_min - tolerance <= hy <= vy_max + tolerance):
                intersections.append((vx, hy))

    # Deduplicate
    intersections = list(set(intersections))
    print(f"Intersections found: {len(intersections)}  (tolerance={tolerance}px)")
    return intersections


# ---------------------------------------------------------------------------
# Step 3: Inject intersection points into segments (endpoint injection)
# ---------------------------------------------------------------------------

def inject_intersections(segments, intersections, tolerance=6):
    """
    Insert intersection points into corresponding segments if they lie
    within segment bounds (with tolerance). This ensures segments get
    split at junction points.

    Returns updated segments split at injection points.
    """
    # Build lookup: intersection points per axis value
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
            # Collect x-coords of intersections on or near this line
            candidate_xs = []
            for line_y, x_list in pts_by_y.items():
                if abs(line_y - y1) <= tolerance:
                    for cx in x_list:
                        if x1 <= cx <= x2:
                            candidate_xs.append(cx)
            all_xs = sorted(set([x1, x2] + candidate_xs))
            for i in range(len(all_xs) - 1):
                split_segs.append({
                    "start": (all_xs[i],   y1),
                    "end":   (all_xs[i+1], y1),
                    "orientation": "horizontal",
                })
        else:  # vertical
            candidate_ys = []
            for line_x, y_list in pts_by_x.items():
                if abs(line_x - x1) <= tolerance:
                    for cy in y_list:
                        if y1 <= cy <= y2:
                            candidate_ys.append(cy)
            all_ys = sorted(set([y1, y2] + candidate_ys))
            for i in range(len(all_ys) - 1):
                split_segs.append({
                    "start": (x1, all_ys[i]),
                    "end":   (x1, all_ys[i+1]),
                    "orientation": "vertical",
                })

    print(f"Segments after injection/splitting: {len(split_segs)}"
          f"  (from {len(segments)} originals)")
    return split_segs


# ---------------------------------------------------------------------------
# Step 4: Point deduplication
# ---------------------------------------------------------------------------

def deduplicate_points(split_segments, tolerance=6):
    """
    Merge nearly identical points (within tolerance_px).
    Uses greedy clustering: for each unvisited point, find all points
    within tolerance, replace them all with the centroid.
    Returns updated segments with deduplicated coordinates.
    """
    # Collect all unique endpoints
    all_pts = set()
    for seg in split_segments:
        all_pts.add(seg["start"])
        all_pts.add(seg["end"])

    pts_list = sorted(all_pts)
    n = len(pts_list)
    visited = [False] * n
    merge_map = {}  # original coord -> merged centroid

    for i in range(n):
        if visited[i]:
            continue
        cluster = [i]
        visited[i] = True
        for j in range(i + 1, n):
            if visited[j]:
                continue
            dx = abs(pts_list[j][0] - pts_list[i][0])
            dy = abs(pts_list[j][1] - pts_list[i][1])
            if dx <= tolerance and dy <= tolerance:
                cluster.append(j)
                visited[j] = True

        # Compute centroid
        cx = int(round(sum(pts_list[k][0] for k in cluster) / len(cluster)))
        cy = int(round(sum(pts_list[k][1] for k in cluster) / len(cluster)))
        for k in cluster:
            merge_map[pts_list[k]] = (cx, cy)

    # Count merges
    num_merged = sum(1 for k, v in merge_map.items() if k != v)

    # Apply merge map to segments
    result = []
    for seg in split_segments:
        new_start = merge_map[seg["start"]]
        new_end = merge_map[seg["end"]]
        # Skip zero-length segments created by merging
        if new_start == new_end:
            continue
        result.append({
            "start": new_start,
            "end": new_end,
            "orientation": seg["orientation"],
        })

    if num_merged:
        print(f"Point deduplication: {num_merged} point(s) merged"
              f"  (tolerance={tolerance}px)")
    else:
        print(f"Point deduplication: no changes needed")
    return result


# ---------------------------------------------------------------------------
# Step 5: Build nodes
# ---------------------------------------------------------------------------

def build_nodes(split_segments):
    """
    Create graph nodes from all unique (x, y) coordinates.
    Returns:
        nodes      - list of {"id": int, "x": int, "y": int}
        coord_to_id - dict mapping (x, y) -> node id
    """
    coord_set = set()
    for seg in split_segments:
        coord_set.add(seg["start"])
        coord_set.add(seg["end"])

    sorted_coords = sorted(coord_set)
    coord_to_id = {}
    nodes = []
    for idx, (x, y) in enumerate(sorted_coords):
        coord_to_id[(x, y)] = idx
        nodes.append({"id": idx, "x": x, "y": y})

    print(f"Graph nodes: {len(nodes)}")
    return nodes, coord_to_id


# ---------------------------------------------------------------------------
# Step 6: Build edges
# ---------------------------------------------------------------------------

def build_edges(split_segments, coord_to_id):
    """
    Create graph edges from split wall segments.
    Each edge stores: start_node_id, end_node_id, length_px.
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
            "length_px":     round(length, 2),
        })

    print(f"Graph edges: {len(edges)}")
    return edges


# ---------------------------------------------------------------------------
# Step 7: Dangling edge removal
# ---------------------------------------------------------------------------

def _degree_map(nodes, edges):
    deg = {n["id"]: 0 for n in nodes}
    for e in edges:
        deg[e["start_node_id"]] = deg.get(e["start_node_id"], 0) + 1
        deg[e["end_node_id"]]   = deg.get(e["end_node_id"], 0) + 1
    return deg


def remove_dangling_edges(nodes, edges, min_length=20):
    """
    Remove edges whose endpoints both have degree 1, unless they are
    longer than min_length (likely part of outer boundary).
    Also iteratively remove short degree-1 stub edges.
    """
    total_removed = 0
    changed = True

    while changed:
        changed = False
        deg = _degree_map(nodes, edges)
        keep = []
        for e in edges:
            s_deg = deg.get(e["start_node_id"], 0)
            e_deg = deg.get(e["end_node_id"], 0)

            # Both endpoints degree-1: isolated floating edge
            if s_deg == 1 and e_deg == 1 and e["length_px"] < min_length:
                changed = True
                total_removed += 1
                continue

            # Single degree-1 endpoint: dangling stub
            if (s_deg == 1 or e_deg == 1) and e["length_px"] < min_length:
                changed = True
                total_removed += 1
                continue

            keep.append(e)
        edges = keep

    if total_removed:
        print(f"Removed {total_removed} dangling edge(s)"
              f"  (min_length={min_length}px)")
    else:
        print(f"No dangling edges removed  (min_length={min_length}px)")
    return edges


# ---------------------------------------------------------------------------
# Step 8: Connected component validation
# ---------------------------------------------------------------------------

def connected_components(nodes, edges):
    """
    Union-find connected-component analysis.
    Check that outer boundary forms at least one closed cycle.
    """
    if not nodes:
        print("Connected components: 0 nodes - skipped")
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

    # Check for cycles (necessary for room detection)
    deg = _degree_map(nodes, edges)
    has_cycle = any(v >= 2 for v in deg.values()) and len(edges) >= len(active_ids)

    if num_comp == 0:
        print("Connected components: 0 (no edges)")
    elif num_comp == 1:
        cycle_str = "has cycle" if has_cycle else "no cycle"
        print(f"Connected components: 1  ({sorted_sizes[0]} nodes, {cycle_str})  [PASS]")
    else:
        largest = sorted_sizes[0]
        pct = largest / len(active_ids) * 100 if active_ids else 0
        status = "PASS" if pct >= 50 else "WARN"
        cycle_str = "has cycle" if has_cycle else "no cycle"
        print(f"Connected components: {num_comp}  "
              f"sizes={sorted_sizes[:8]}{'...' if num_comp > 8 else ''}  "
              f"largest={largest} ({pct:.0f}%, {cycle_str})  [{status}]")

    return num_comp


# ---------------------------------------------------------------------------
# Prune orphan nodes
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

    # Re-index to contiguous 0..N-1
    old_to_new = {}
    renumbered = []
    for new_id, n in enumerate(pruned):
        old_to_new[n["id"]] = new_id
        renumbered.append({"id": new_id, "x": n["x"], "y": n["y"]})

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
            bg = cv2.cvtColor(mask // 3, cv2.COLOR_GRAY2BGR)
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
    print("  Stage 3: Wall Graph Construction")
    print("=" * 55)
    print()

    # Image dimensions for thresholds
    img_shape = get_image_dimensions()
    max_dim = max(img_shape)
    print(f"Image: {img_shape[1]}x{img_shape[0]}  max_dim={max_dim}")

    # 1. Load & normalise segments
    segments = load_segments(json_path)

    # 1b. Normalize: extend/snap endpoints to perpendicular walls
    segments = normalize_segments(segments, max_dim)

    # 2. Compute intersections with tolerance
    tolerance = max(6, int(0.01 * max_dim))   # 20px at 2000px
    intersections = compute_intersections(segments, tolerance)

    # 3. Inject intersections & split segments
    split_segs = inject_intersections(segments, intersections, tolerance)

    # 4. Point deduplication
    split_segs = deduplicate_points(split_segs, tolerance)

    # 5. Build nodes
    nodes, coord_to_id = build_nodes(split_segs)

    # 6. Build edges
    edges = build_edges(split_segs, coord_to_id)

    # 7. Dangling edge removal
    edges = remove_dangling_edges(nodes, edges, min_length=20)

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
