# stage3_wall_graph.py
#
# Stage 3 � Wall Graph Construction (Closed Topology)
#
# Build a wall connectivity graph from axis-aligned segments (Stage 2).
#
# Core Principles:
#   - Collinear segments are merged to form continuous walls.
#   - T-junctions and Corners are created via Ray-Casting Extension.
#   - Topology hashing uses high precision floats to perfectly merge intersections.

import sys
import os
import json
import math
import numpy as np
import cv2
from collections import defaultdict
from . import utils

# -- Tolerances ---------------------------------------------------------------
AXIS_SNAP_TOL = 5           # Snap near-identical axis coordinates
COLLINEAR_GAP_TOL = 20      # Bridge collinear gaps smaller than this
INTERSECTION_TOL = 25       # Ray-casting distance for finding intersections
NOISE_THRESHOLD = 50        # Remove components with total edge length below this

# =============================================================================
# 1. Load segments
# =============================================================================

def load_segments(json_path=None):
    if json_path is None:
        json_path = os.path.join(utils.get_intermediate_dir(), "wall_line_segments.json")
    with open(json_path) as f:
        raw = json.load(f)

    segments = []
    for s in raw:
        sx, sy = float(s["start"][0]), float(s["start"][1])
        ex, ey = float(s["end"][0]), float(s["end"][1])
        ori = s["orientation"]

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
    if not values:
        return {}
    uniq = sorted(set(values))
    mapping = {}
    cluster = [uniq[0]]
    for v in uniq[1:]:
        if v - cluster[0] <= tol:
            cluster.append(v)
        else:
            canonical = sum(cluster) / len(cluster)
            for cv in cluster:
                mapping[cv] = canonical
            cluster = [v]
    canonical = sum(cluster) / len(cluster)
    for cv in cluster:
        mapping[cv] = canonical
    return mapping

def normalize_axis_coordinates(segments, tol=AXIS_SNAP_TOL):
    v_xs = []
    h_ys = []
    for s in segments:
        if s["orientation"] == "vertical":
            v_xs.extend([s["start"][0], s["end"][0]])
        else:
            h_ys.extend([s["start"][1], s["end"][1]])

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

        if ori == "horizontal":
            if sx > ex: sx, ex = ex, sx
            ey = sy
        else:
            if sy > ey: sy, ey = ey, sy
            ex = sx

        out.append({"start": (sx, sy), "end": (ex, ey), "orientation": ori})
    return out

# =============================================================================
# 3. Merge collinear segments
# =============================================================================

def merge_collinear_segments(segments, gap_tol=COLLINEAR_GAP_TOL):
    def _merge(segs, ori):
        if not segs:
            return []
        groups = defaultdict(list)
        for s in segs:
            axis = round(s["start"][1] if ori == 'horizontal' else s["start"][0], 3)
            groups[axis].append(s)
            
        merged = []
        for axis, group in groups.items():
            if ori == 'horizontal':
                intervals = sorted([(s["start"][0], s["end"][0], s["start"][1]) for s in group])
            else:
                intervals = sorted([(s["start"][1], s["end"][1], s["start"][0]) for s in group])
                
            res = []
            for start, end, true_axis in intervals:
                if not res:
                    res.append([start, end, true_axis])
                else:
                    prev_start, prev_end, prev_axis = res[-1]
                    if start <= prev_end + gap_tol:
                        res[-1][1] = max(prev_end, end)
                    else:
                        res.append([start, end, true_axis])
                        
            for start, end, true_axis in res:
                if ori == 'horizontal':
                    merged.append({"start": (start, true_axis), "end": (end, true_axis), "orientation": ori})
                else:
                    merged.append({"start": (true_axis, start), "end": (true_axis, end), "orientation": ori})
        return merged

    h = [s for s in segments if s["orientation"] == "horizontal"]
    v = [s for s in segments if s["orientation"] == "vertical"]
    return _merge(h, 'horizontal') + _merge(v, 'vertical')

# =============================================================================
# 4. Detect Intersections (Ray-Casting)
# =============================================================================

def detect_intersections(segments, tol=INTERSECTION_TOL):
    h_indices = [i for i, s in enumerate(segments) if s["orientation"] == "horizontal"]
    v_indices = [i for i, s in enumerate(segments) if s["orientation"] == "vertical"]

    seg_intersections = defaultdict(set)
    pts = []

    for hi in h_indices:
        h = segments[hi]
        hy = h["start"][1]
        hx1, hx2 = h["start"][0], h["end"][0]

        for vi in v_indices:
            v = segments[vi]
            vx = v["start"][0]
            vy1, vy2 = v["start"][1], v["end"][1]

            if (hx1 - tol) <= vx <= (hx2 + tol) and (vy1 - tol) <= hy <= (vy2 + tol):
                pt = (vx, hy)
                seg_intersections[hi].add(pt)
                seg_intersections[vi].add(pt)
                pts.append(pt)
                
    return pts, seg_intersections

# =============================================================================
# 5. Split segments (Endpoint Extension)
# =============================================================================

def split_segments(segments, seg_intersections):
    edges = []
    for i, seg in enumerate(segments):
        ori = seg["orientation"]
        on_seg = {seg["start"], seg["end"]}
        on_seg.update(seg_intersections.get(i, set()))
        
        if ori == "horizontal":
            ordered = sorted(on_seg, key=lambda p: round(p[0], 3))
        else:
            ordered = sorted(on_seg, key=lambda p: round(p[1], 3))
            
        for j in range(len(ordered) - 1):
            p1, p2 = ordered[j], ordered[j + 1]
            if math.hypot(p2[0] - p1[0], p2[1] - p1[1]) >= 1.0:
                edges.append((p1, p2))
    return edges

# =============================================================================
# 6. Build graph (Precision Hashing)
# =============================================================================

def build_graph(sub_edges):
    all_coords = set()
    for p1, p2 in sub_edges:
        all_coords.add((round(p1[0], 3), round(p1[1], 3)))
        all_coords.add((round(p2[0], 3), round(p2[1], 3)))

    sorted_coords = sorted(list(all_coords))
    coord_to_id = {c: i for i, c in enumerate(sorted_coords)}
    nodes = [{"id": i, "x": c[0], "y": c[1]} for i, c in enumerate(sorted_coords)]

    seen = set()
    edges = []
    for p1, p2 in sub_edges:
        c1 = (round(p1[0], 3), round(p1[1], 3))
        c2 = (round(p2[0], 3), round(p2[1], 3))
        
        a = coord_to_id[c1]
        b = coord_to_id[c2]
        if a == b: continue
        
        key = (min(a, b), max(a, b))
        if key in seen: continue
        seen.add(key)
        
        edges.append({
            "start_node": key[0],
            "end_node": key[1],
            "length_px": round(math.hypot(p2[0] - p1[0], p2[1] - p1[1]), 1)
        })
    return nodes, edges

# =============================================================================
# 7. Clean graph
# =============================================================================

def clean_graph(nodes, edges, noise_threshold=NOISE_THRESHOLD):
    adj = defaultdict(set)
    for e in edges:
        adj[e["start_node"]].add(e["end_node"])
        adj[e["end_node"]].add(e["start_node"])

    visited = set()
    components = []
    for n in nodes:
        nid = n["id"]
        if nid in visited: continue
        queue = [nid]
        comp = set()
        while queue:
            cur = queue.pop(0)
            if cur in visited: continue
            visited.add(cur)
            comp.add(cur)
            for nb in adj[cur]:
                if nb not in visited: queue.append(nb)
        if comp: components.append(comp)

    components.sort(key=len, reverse=True)
    if len(components) <= 1: return nodes, edges

    keep_ids = set()
    for comp in components:
        comp_edge_len = sum(e["length_px"] for e in edges if e["start_node"] in comp and e["end_node"] in comp)
        if len(comp) >= 2 and comp_edge_len >= noise_threshold:
            keep_ids.update(comp)

    if not keep_ids: keep_ids = components[0]

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
    return new_nodes, new_edges

# =============================================================================
# 8. Validate topology
# =============================================================================

def validate_topology(nodes, edges):
    adj = defaultdict(set)
    for e in edges:
        adj[e["start_node"]].add(e["end_node"])
        adj[e["end_node"]].add(e["start_node"])
    
    degrees = [len(adj[n["id"]]) for n in nodes]
    avg_degree = sum(degrees) / len(degrees) if degrees else 0
    degree_1 = sum(1 for d in degrees if d == 1)
    
    issues = []
    if len(edges) < len(nodes): issues.append("Edges < Nodes (tree-like, no cycles)")
    if degree_1 > len(nodes) * 0.3: issues.append(f"Too many degree-1 nodes")
    if avg_degree < 1.5: issues.append(f"Low average degree")
    return len(issues) == 0

def report(nodes, edges):
    pass

# =============================================================================
# Save & Visualize
# =============================================================================

def get_image_dimensions():
    return utils.get_image_dimensions()

def save_graph(nodes, edges, path=None):
    if path is None: path = os.path.join(utils.get_intermediate_dir(), "wall_graph.json")
    utils.save_json({"nodes": nodes, "edges": edges}, path)

def visualize(nodes, edges, img_shape, save_dir=None):
    if save_dir is None: save_dir = utils.get_intermediate_dir()
    h, w = img_shape[:2]
    nmap = {n["id"]: (int(round(n["x"])), int(round(n["y"]))) for n in nodes}

    mp = os.path.join(utils.get_intermediate_dir(), "binary_wall_mask.png")
    if os.path.exists(mp):
        mask = cv2.imread(mp, cv2.IMREAD_GRAYSCALE)
        if mask is not None:
            bg = cv2.cvtColor((mask * 0.35).astype(np.uint8), cv2.COLOR_GRAY2BGR)
        else: bg = np.zeros((h, w, 3), np.uint8)
    else: bg = np.zeros((h, w, 3), np.uint8)

    for e in edges:
        cv2.line(bg, nmap[e["start_node"]], nmap[e["end_node"]], (0, 255, 0), 2)
    for n in nodes:
        nx, ny = int(round(n["x"])), int(round(n["y"]))
        cv2.circle(bg, (nx, ny), 5, (0, 0, 255), -1)
        cv2.putText(bg, str(n["id"]), (nx + 6, ny - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 0), 1)

    out_path = os.path.join(save_dir, "wall_graph.png")
    cv2.imwrite(out_path, bg)
    print(f"Visualization -> {out_path}")

# =============================================================================
# Main
# =============================================================================

def main():
    print("=" * 55)
    print("  Stage 3: Topology-Aware Wall Graph")
    print("=" * 55)
    print()

    img_shape = get_image_dimensions()
    path = sys.argv[1] if len(sys.argv) >= 2 else None

    segments = load_segments(path)
    segments = normalize_axis_coordinates(segments, AXIS_SNAP_TOL)
    segments = merge_collinear_segments(segments, COLLINEAR_GAP_TOL)
    
    pts, seg_inters = detect_intersections(segments, INTERSECTION_TOL)
    edges = split_segments(segments, seg_inters)
    nodes, edges = build_graph(edges)
    nodes, edges = clean_graph(nodes, edges, NOISE_THRESHOLD)
    
    validate_topology(nodes, edges)
    report(nodes, edges)
    save_graph(nodes, edges)
    visualize(nodes, edges, img_shape)

if __name__ == '__main__':
    main()
