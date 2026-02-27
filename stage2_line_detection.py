# stage2_line_detection.py
#
# Stage 2 - Wall Line Segment Detection
# Extract clean, fully merged, axis-aligned wall segments with snapped
# endpoints and no fragmentation.
#
# Input:  data/intermediate/edge_map.png          (from Stage 1)
#         data/intermediate/binary_wall_mask.png   (from Stage 1)
# Output: data/intermediate/wall_line_segments.json
#         data/intermediate/wall_line_segments_overlay.png

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

def compute_length(x1, y1, x2, y2):
    return float(math.hypot(x2 - x1, y2 - y1))


def compute_angle_deg(x1, y1, x2, y2):
    return math.degrees(math.atan2(float(y2) - float(y1),
                                   float(x2) - float(x1))) % 180.0


def orientation_label(angle_deg):
    """Keep only segments within +/-10 deg of 0 deg or 90 deg."""
    if angle_deg <= 10.0 or angle_deg >= 170.0:
        return "horizontal"
    if abs(angle_deg - 90.0) <= 10.0:
        return "vertical"
    return None


# ---------------------------------------------------------------------------
# Step 1: Load inputs
# ---------------------------------------------------------------------------

def load_inputs(edge_path=None, binary_path=None):
    if edge_path is None:
        edge_path = os.path.join("data", "intermediate", "edge_map.png")
    if binary_path is None:
        binary_path = os.path.join("data", "intermediate", "binary_wall_mask.png")

    edges = None
    if os.path.exists(edge_path):
        e = cv2.imread(edge_path, cv2.IMREAD_GRAYSCALE)
        if e is not None:
            edges = (e > 0).astype(np.uint8) * 255
        else:
            print(f"Warning: Could not load edge map at {edge_path}.")

    binary = None
    if os.path.exists(binary_path):
        b = cv2.imread(binary_path, cv2.IMREAD_GRAYSCALE)
        if b is not None:
            binary = (b > 0).astype(np.uint8) * 255
        else:
            print(f"Warning: Could not load binary wall mask at {binary_path}.")
    else:
        print(f"Warning: Binary wall mask not found at {binary_path}.")

    return edges, binary


def thicken_edges(edges, kernel_size=3, iterations=1):
    """Dilate edge map for more stable Hough detection."""
    e = (edges > 0).astype(np.uint8) * 255
    kernel = cv2.getStructuringElement(cv2.MORPH_CROSS, (kernel_size, kernel_size))
    thick = cv2.dilate(e, kernel, iterations=iterations)
    return thick


def detect_boundary_segments(binary, min_seg_len):
    """
    Extract outer boundary wall segments from the binary wall mask using
    contour approximation. Hand-drawn walls are too wobbly for Hough to
    detect as full-length lines, so this captures them from the polygon
    approximation of the largest external contour.

    Returns list of (x1, y1, x2, y2, orientation, length) tuples.
    """
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL,
                                    cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return []

    # Largest external contour = outer boundary
    outer = max(contours, key=cv2.contourArea)
    peri = cv2.arcLength(outer, True)
    approx = cv2.approxPolyDP(outer, 0.03 * peri, True)
    pts = [tuple(pt[0]) for pt in approx]

    boundary_segs = []
    n = len(pts)
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]

        L = compute_length(x1, y1, x2, y2)
        if L < min_seg_len:
            continue

        ang = compute_angle_deg(x1, y1, x2, y2)

        # Snap near-horizontal/vertical edges (within 15 deg)
        if ang <= 15.0 or ang >= 165.0:
            # Horizontal: average y, keep x span
            y_avg = int(round((y1 + y2) / 2.0))
            xa, xb = min(x1, x2), max(x1, x2)
            boundary_segs.append((xa, y_avg, xb, y_avg, "horizontal", float(xb - xa)))
        elif abs(ang - 90.0) <= 15.0:
            # Vertical: average x, keep y span
            x_avg = int(round((x1 + x2) / 2.0))
            ya, yb = min(y1, y2), max(y1, y2)
            boundary_segs.append((x_avg, ya, x_avg, yb, "vertical", float(yb - ya)))
        # Diagonal edges are skipped (spec: axis-aligned only)

    if boundary_segs:
        print(f"Boundary contour segments: {len(boundary_segs)}")
        for s in boundary_segs:
            ori = s[4]
            if ori == 'horizontal':
                print(f"  H  y={s[1]}  x=[{s[0]}, {s[2]}]  len={s[5]:.0f}")
            else:
                print(f"  V  x={s[0]}  y=[{s[1]}, {s[3]}]  len={s[5]:.0f}")
    return boundary_segs


# ---------------------------------------------------------------------------
# Step 2: Hough line detection
# ---------------------------------------------------------------------------

def detect_raw_lines(edges, max_dim):
    """Run HoughLinesP with spec-defined ratios."""
    rho = 1
    theta = math.pi / 180.0
    threshold = max(30, int(0.02 * max_dim))
    min_line_len = max(10, int(0.04 * max_dim))    # 4% of max_dim per spec
    max_line_gap = max(5, int(0.02 * max_dim))      # 2% of max_dim per spec

    lines = cv2.HoughLinesP(
        edges, rho, theta, threshold,
        minLineLength=min_line_len,
        maxLineGap=max_line_gap,
    )
    segs = []
    if lines is not None:
        for l in lines:
            x1, y1, x2, y2 = map(int, l[0])
            segs.append((x1, y1, x2, y2))
    return segs, min_line_len, max_line_gap


# ---------------------------------------------------------------------------
# Step 3: Orientation filtering
# ---------------------------------------------------------------------------

def filter_by_orientation(segs, min_len):
    """Keep only H/V segments within +/-10 deg and above min length."""
    filtered = []
    for (x1, y1, x2, y2) in segs:
        L = compute_length(x1, y1, x2, y2)
        if L < min_len:
            continue
        ang = compute_angle_deg(x1, y1, x2, y2)
        ori = orientation_label(ang)
        if ori is None:
            continue
        filtered.append((x1, y1, x2, y2, ori, L))
    return filtered


# ---------------------------------------------------------------------------
# Step 4: Binary overlap validation
# ---------------------------------------------------------------------------

def filter_by_binary_overlap(filtered, binary, min_overlap_ratio=0.5,
                              min_overlap_pixels=30):
    """Keep only segments that sufficiently overlap the binary wall mask."""
    if binary is None:
        return filtered
    h, w = binary.shape[:2]
    kept = []
    for (x1, y1, x2, y2, ori, L) in filtered:
        x1c = int(max(0, min(w - 1, x1)))
        x2c = int(max(0, min(w - 1, x2)))
        yc1 = int(max(0, min(h - 1, y1)))
        yc2 = int(max(0, min(h - 1, y2)))
        line_mask = np.zeros((h, w), dtype=np.uint8)
        cv2.line(line_mask, (x1c, yc1), (x2c, yc2), 255, 1, cv2.LINE_8)
        line_px = int(np.count_nonzero(line_mask))
        if line_px == 0:
            continue
        overlap_px = int(np.count_nonzero(cv2.bitwise_and(line_mask, binary)))
        ratio = overlap_px / float(line_px)
        if overlap_px >= min_overlap_pixels and ratio >= min_overlap_ratio:
            kept.append((x1, y1, x2, y2, ori, L))
    return kept


# ---------------------------------------------------------------------------
# Step 5: Collinear grouping + interval merging
# ---------------------------------------------------------------------------

def group_and_merge(filtered, gap_tolerance, band_distance, img_shape):
    """
    Group co-linear segments (same axis within band_distance), then merge
    overlapping or near-touching intervals using gap_tolerance.
    """
    h, w = img_shape[:2]
    max_dim = max(h, w)

    horiz = [(x1, y1, x2, y2, L)
             for (x1, y1, x2, y2, ori, L) in filtered if ori == "horizontal"]
    vert = [(x1, y1, x2, y2, L)
            for (x1, y1, x2, y2, ori, L) in filtered if ori == "vertical"]

    merged = []

    # --- Horizontal segments: group by y-band ---
    if horiz:
        items = []
        for x1, y1, x2, y2, L in horiz:
            y_mean = (y1 + y2) / 2.0
            xa, xb = sorted([x1, x2])
            items.append((y_mean, xa, xb))
        items.sort(key=lambda t: t[0])

        groups = []
        cur = []
        cur_ref = None
        for it in items:
            if not cur:
                cur = [it]
                cur_ref = it[0]
            else:
                if abs(it[0] - cur_ref) <= band_distance:
                    cur.append(it)
                    # running average reference
                    cur_ref = (cur_ref * (len(cur) - 1) + it[0]) / len(cur)
                else:
                    groups.append(cur)
                    cur = [it]
                    cur_ref = it[0]
        if cur:
            groups.append(cur)

        for g in groups:
            y_vals = [t[0] for t in g]
            y_snap = int(round(float(np.median(y_vals))))
            intervals = sorted([(xa, xb) for (_, xa, xb) in g])

            # Merge overlapping / near-touching intervals
            merged_intervals = []
            cur_s, cur_e = intervals[0]
            for xa, xb in intervals[1:]:
                if xa <= cur_e + gap_tolerance:
                    cur_e = max(cur_e, xb)
                else:
                    merged_intervals.append((cur_s, cur_e))
                    cur_s, cur_e = xa, xb
            merged_intervals.append((cur_s, cur_e))

            for a, b in merged_intervals:
                if b > a:
                    merged.append((int(a), y_snap, int(b), y_snap, "horizontal"))

    # --- Vertical segments: group by x-band ---
    if vert:
        items = []
        for x1, y1, x2, y2, L in vert:
            x_mean = (x1 + x2) / 2.0
            ya, yb = sorted([y1, y2])
            items.append((x_mean, ya, yb))
        items.sort(key=lambda t: t[0])

        groups = []
        cur = []
        cur_ref = None
        for it in items:
            if not cur:
                cur = [it]
                cur_ref = it[0]
            else:
                if abs(it[0] - cur_ref) <= band_distance:
                    cur.append(it)
                    cur_ref = (cur_ref * (len(cur) - 1) + it[0]) / len(cur)
                else:
                    groups.append(cur)
                    cur = [it]
                    cur_ref = it[0]
        if cur:
            groups.append(cur)

        for g in groups:
            x_vals = [t[0] for t in g]
            x_snap = int(round(float(np.median(x_vals))))
            intervals = sorted([(ya, yb) for (_, ya, yb) in g])

            merged_intervals = []
            cur_s, cur_e = intervals[0]
            for ya, yb in intervals[1:]:
                if ya <= cur_e + gap_tolerance:
                    cur_e = max(cur_e, yb)
                else:
                    merged_intervals.append((cur_s, cur_e))
                    cur_s, cur_e = ya, yb
            merged_intervals.append((cur_s, cur_e))

            for a, b in merged_intervals:
                if b > a:
                    merged.append((x_snap, int(a), x_snap, int(b), "vertical"))

    return merged


# ---------------------------------------------------------------------------
# Step 6: Endpoint snapping
# ---------------------------------------------------------------------------

def snap_endpoints(merged, snap_radius=8):
    """
    Cluster endpoints that are within snap_radius of each other and
    replace them with the centroid of the cluster.
    """
    # Collect all unique endpoints
    endpoints = []
    for (x1, y1, x2, y2, ori) in merged:
        endpoints.append([x1, y1])
        endpoints.append([x2, y2])

    if not endpoints:
        return merged

    pts = np.array(endpoints, dtype=np.float64)

    # Build clusters using greedy nearest-neighbour
    n = len(pts)
    visited = [False] * n
    cluster_map = {}  # index -> centroid (x, y)

    for i in range(n):
        if visited[i]:
            continue
        # Find all points within snap_radius of pts[i]
        cluster = [i]
        visited[i] = True
        for j in range(i + 1, n):
            if visited[j]:
                continue
            d = math.hypot(pts[j][0] - pts[i][0], pts[j][1] - pts[i][1])
            if d <= snap_radius:
                cluster.append(j)
                visited[j] = True

        # Compute centroid
        cx = int(round(np.mean([pts[k][0] for k in cluster])))
        cy = int(round(np.mean([pts[k][1] for k in cluster])))
        for k in cluster:
            cluster_map[k] = (cx, cy)

    # Rebuild segments with snapped endpoints
    result = []
    for idx, (x1, y1, x2, y2, ori) in enumerate(merged):
        ep1_idx = idx * 2
        ep2_idx = idx * 2 + 1
        nx1, ny1 = cluster_map[ep1_idx]
        nx2, ny2 = cluster_map[ep2_idx]

        # Ensure axis alignment after snapping
        if ori == "horizontal":
            y_avg = (ny1 + ny2) // 2
            ny1 = ny2 = y_avg
            if nx1 > nx2:
                nx1, nx2 = nx2, nx1
        else:
            x_avg = (nx1 + nx2) // 2
            nx1 = nx2 = x_avg
            if ny1 > ny2:
                ny1, ny2 = ny2, ny1

        # Skip zero-length segments created by snapping
        if nx1 == nx2 and ny1 == ny2:
            continue
        result.append((nx1, ny1, nx2, ny2, ori))

    return result


# ---------------------------------------------------------------------------
# Step 7: Remove short segments
# ---------------------------------------------------------------------------

def remove_short_segments(merged, max_dim):
    """Remove segments shorter than 5% of max image dimension."""
    min_len = max(10, int(0.05 * max_dim))
    kept = []
    removed = 0
    for (x1, y1, x2, y2, ori) in merged:
        L = compute_length(x1, y1, x2, y2)
        if L >= min_len:
            kept.append((x1, y1, x2, y2, ori))
        else:
            removed += 1
    if removed:
        print(f"  Removed {removed} short segment(s) (< {min_len}px)")
    return kept


# ---------------------------------------------------------------------------
# Build output + save + visualize
# ---------------------------------------------------------------------------

def build_output(merged):
    out = []
    for x1, y1, x2, y2, ori in merged:
        length = compute_length(x1, y1, x2, y2)
        out.append({
            "start": [int(x1), int(y1)],
            "end": [int(x2), int(y2)],
            "orientation": ori,
            "length_px": float(length)
        })
    return out


def save_outputs(segments, save_dir=None):
    if save_dir is None:
        save_dir = os.path.join("data", "intermediate")
    os.makedirs(save_dir, exist_ok=True)
    json_path = os.path.join(save_dir, "wall_line_segments.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(segments, f, indent=2)
    print(f"Segments saved to: {json_path}")


def visualize_segments(segments, shape, save_dir=None):
    """Draw segments on black canvas + on dim wall mask."""
    if save_dir is None:
        save_dir = os.path.join("data", "intermediate")
    os.makedirs(save_dir, exist_ok=True)

    def _draw(canvas):
        for s in segments:
            x1, y1 = map(int, s["start"])
            x2, y2 = map(int, s["end"])
            color = (0, 255, 0) if s["orientation"] == "horizontal" else (0, 128, 255)
            cv2.line(canvas, (x1, y1), (x2, y2), color, 2, cv2.LINE_AA)
            # Draw endpoints
            cv2.circle(canvas, (x1, y1), 4, (0, 0, 255), -1, cv2.LINE_AA)
            cv2.circle(canvas, (x2, y2), 4, (0, 0, 255), -1, cv2.LINE_AA)
        return canvas

    # Black background
    canvas = np.zeros((shape[0], shape[1], 3), dtype=np.uint8)
    _draw(canvas)
    out_path = os.path.join(save_dir, "wall_line_segments_overlay.png")
    cv2.imwrite(out_path, canvas)
    print(f"Overlay saved to: {out_path}")

    # Wall mask background
    mask_path = os.path.join("data", "intermediate", "binary_wall_mask.png")
    if os.path.exists(mask_path):
        mask = cv2.imread(mask_path, cv2.IMREAD_GRAYSCALE)
        if mask is not None:
            bg = cv2.cvtColor(mask // 3, cv2.COLOR_GRAY2BGR)
            _draw(bg)
            out_path2 = os.path.join(save_dir, "wall_line_segments_on_mask.png")
            cv2.imwrite(out_path2, bg)
            print(f"Overlay-on-mask saved to: {out_path2}")


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print("  Stage 2: Wall Line Segment Detection")
    print("=" * 60)
    print()

    edge_path = None
    binary_path = None
    if len(sys.argv) >= 2:
        edge_path = sys.argv[1]
    if len(sys.argv) >= 3:
        binary_path = sys.argv[2]

    # 1. Load inputs
    edges, binary = load_inputs(edge_path, binary_path)
    if binary is None:
        print("Error: Binary wall mask is required.")
        sys.exit(1)
    if edges is None:
        print("Edge map not found. Deriving from binary wall mask...")
        k = cv2.getStructuringElement(cv2.MORPH_CROSS, (3, 3))
        dil = cv2.dilate(binary, k, iterations=1)
        ero = cv2.erode(binary, k, iterations=1)
        edges = cv2.subtract(dil, ero)

    h_img, w_img = edges.shape[:2]
    max_dim = max(h_img, w_img)
    print(f"Image: {w_img}x{h_img}  max_dim={max_dim}")

    # 2. Thicken edges for stable Hough
    thick_edges = thicken_edges(edges, kernel_size=3, iterations=1)

    # 3. Hough detection
    segs, min_line_len, max_line_gap = detect_raw_lines(thick_edges, max_dim)
    print(f"Raw Hough segments: {len(segs)}"
          f"  (min_len={min_line_len}, max_gap={max_line_gap})")

    # 4. Orientation filtering
    filtered = filter_by_orientation(segs, min_line_len)
    print(f"After orientation filtering: {len(filtered)}")

    # 5. Binary overlap validation
    filtered = filter_by_binary_overlap(filtered, binary,
                                         min_overlap_ratio=0.5,
                                         min_overlap_pixels=30)
    print(f"After binary-overlap validation: {len(filtered)}")

    # 5b. Inject contour-based boundary segments (no validation needed -
    #     they come from the mask contour itself)
    boundary = detect_boundary_segments(binary, min_line_len)
    if boundary:
        filtered.extend(boundary)
        print(f"Injected {len(boundary)} boundary segment(s)")

    # 6. Collinear grouping + interval merging
    #    Scale tolerances with image size for hand-drawn sketches
    band_distance = max(10, int(0.035 * max_dim))   # ~70px at 2000px
    gap_tolerance = max(12, int(0.03 * max_dim))     # ~60px at 2000px
    merged = group_and_merge(filtered, gap_tolerance, band_distance,
                             thick_edges.shape)
    print(f"After grouping & merging: {len(merged)}"
          f"  (band={band_distance}, gap={gap_tolerance})")

    # 7. Endpoint snapping
    snap_radius = max(8, int(0.01 * max_dim))        # ~20px at 2000px
    merged = snap_endpoints(merged, snap_radius)
    print(f"After endpoint snapping: {len(merged)}  (radius={snap_radius})")

    # 7b. Second pass of grouping + merging (after snapping may align axes)
    merged2 = group_and_merge(
        [(x1, y1, x2, y2, ori, compute_length(x1, y1, x2, y2))
         for (x1, y1, x2, y2, ori) in merged],
        gap_tolerance, band_distance, thick_edges.shape)
    if len(merged2) < len(merged):
        print(f"After 2nd merge pass: {len(merged2)}")
        merged = merged2

    # 8. Remove short segments
    merged = remove_short_segments(merged, max_dim)
    print(f"Final segment count: {len(merged)}")

    # Build and save output
    segments = build_output(merged)
    save_outputs(segments)
    visualize_segments(segments, thick_edges.shape)

    # Summary
    if segments:
        horiz = sum(1 for s in segments if s["orientation"] == "horizontal")
        vert = sum(1 for s in segments if s["orientation"] == "vertical")
        print(f"\nH={horiz}  V={vert}  total={len(segments)}")
        lengths = [s["length_px"] for s in segments]
        if lengths:
            print(f"Length range: {min(lengths):.0f} - {max(lengths):.0f} px")

    print("\nStage 2 completed successfully!")


if __name__ == "__main__":
    main()
