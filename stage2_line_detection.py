import sys
import os
import json
import math
import numpy as np
import cv2


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


def compute_length(x1, y1, x2, y2):
    return float(math.hypot(x2 - x1, y2 - y1))


def compute_angle_deg(x1, y1, x2, y2):
    return math.degrees(math.atan2(float(y2) - float(y1), float(x2) - float(x1))) % 180.0


def orientation_label(angle_deg):
    if angle_deg <= 10.0 or angle_deg >= 170.0:
        return "horizontal"
    if abs(angle_deg - 90.0) <= 10.0:
        return "vertical"
    return None

 


def detect_raw_lines(edges):
    h, w = edges.shape[:2]
    max_dim = max(h, w)
    rho = 1
    theta = math.pi / 180.0
    threshold = max(30, int(0.02 * max_dim))
    min_line_len = max(10, int(0.10 * max_dim))
    max_line_gap = max(3, int(0.005 * max_dim))

    lines = cv2.HoughLinesP(
        edges,
        rho,
        theta,
        threshold,
        minLineLength=min_line_len,
        maxLineGap=max_line_gap,
    )
    segs = []
    if lines is not None:
        for l in lines:
            x1, y1, x2, y2 = map(int, l[0])
            segs.append((x1, y1, x2, y2))
    return segs, min_line_len, max_line_gap


def filter_segments(segs, min_len):
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


def filter_by_binary_overlap(filtered, binary, min_overlap_ratio=0.5, min_overlap_pixels=20):
    """
    Keep only segments that sufficiently overlap the binary wall mask.
    Binary geometry is authoritative; edges are helpers.
    """
    if binary is None:
        return filtered
    h, w = binary.shape[:2]
    kept = []
    for (x1, y1, x2, y2, ori, L) in filtered:
        # Clip to image bounds to avoid drawing errors
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
        if overlap_px >= min_overlap_pixels and ratio >= float(min_overlap_ratio):
            kept.append((x1, y1, x2, y2, ori, L))
    return kept


def group_and_merge(filtered, max_gap, img_shape):
    h, w = img_shape[:2]
    max_dim = max(h, w)
    band = max(2, int(0.006 * max_dim))

    horiz = [(x1, y1, x2, y2, L) for (x1, y1, x2, y2, ori, L) in filtered if ori == "horizontal"]
    vert = [(x1, y1, x2, y2, L) for (x1, y1, x2, y2, ori, L) in filtered if ori == "vertical"]

    merged = []

    if horiz:
        items = []
        for x1, y1, x2, y2, L in horiz:
            y_mean = (y1 + y2) / 2.0
            xa, xb = sorted([x1, x2])
            items.append((y_mean, xa, xb, y1, y2))
        items.sort(key=lambda t: t[0])
        groups = []
        cur = []
        cur_ref = None
        for it in items:
            if not cur:
                cur = [it]
                cur_ref = it[0]
            else:
                if abs(it[0] - cur_ref) <= band:
                    cur.append(it)
                    cur_ref = (cur_ref * (len(cur) - 1) + it[0]) / len(cur)
                else:
                    groups.append(cur)
                    cur = [it]
                    cur_ref = it[0]
        if cur:
            groups.append(cur)
        for g in groups:
            g.sort(key=lambda t: t[1])
            y_vals = [t[0] for t in g]
            y_snap = int(round(float(np.median(y_vals))))
            merged_intervals = []
            cur_s, cur_e = None, None
            for _, xa, xb, _, _ in g:
                if cur_s is None:
                    cur_s, cur_e = xa, xb
                else:
                    if xa <= cur_e + max_gap:
                        cur_e = max(cur_e, xb)
                    else:
                        merged_intervals.append((cur_s, cur_e))
                        cur_s, cur_e = xa, xb
            if cur_s is not None:
                merged_intervals.append((cur_s, cur_e))
            for a, b in merged_intervals:
                if b > a:
                    merged.append((int(a), y_snap, int(b), y_snap, "horizontal"))

    if vert:
        items = []
        for x1, y1, x2, y2, L in vert:
            x_mean = (x1 + x2) / 2.0
            ya, yb = sorted([y1, y2])
            items.append((x_mean, ya, yb, x1, x2))
        items.sort(key=lambda t: t[0])
        groups = []
        cur = []
        cur_ref = None
        for it in items:
            if not cur:
                cur = [it]
                cur_ref = it[0]
            else:
                if abs(it[0] - cur_ref) <= band:
                    cur.append(it)
                    cur_ref = (cur_ref * (len(cur) - 1) + it[0]) / len(cur)
                else:
                    groups.append(cur)
                    cur = [it]
                    cur_ref = it[0]
        if cur:
            groups.append(cur)
        for g in groups:
            g.sort(key=lambda t: t[1])
            x_vals = [t[0] for t in g]
            x_snap = int(round(float(np.median(x_vals))))
            merged_intervals = []
            cur_s, cur_e = None, None
            for _, ya, yb, _, _ in g:
                if cur_s is None:
                    cur_s, cur_e = ya, yb
                else:
                    if ya <= cur_e + max_gap:
                        cur_e = max(cur_e, yb)
                    else:
                        merged_intervals.append((cur_s, cur_e))
                        cur_s, cur_e = ya, yb
            if cur_s is not None:
                merged_intervals.append((cur_s, cur_e))
            for a, b in merged_intervals:
                if b > a:
                    merged.append((x_snap, int(a), x_snap, int(b), "vertical"))

    return merged


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
    if save_dir is None:
        save_dir = os.path.join("data", "intermediate")
    canvas = np.zeros((shape[0], shape[1], 3), dtype=np.uint8)
    for s in segments:
        x1, y1 = map(int, s["start"])  # type: ignore
        x2, y2 = map(int, s["end"])    # type: ignore
        color = (0, 255, 0) if s["orientation"] == "horizontal" else (0, 128, 255)
        cv2.line(canvas, (x1, y1), (x2, y2), color, 2, cv2.LINE_AA)
    out_path = os.path.join(save_dir, "wall_line_segments_overlay.png")
    cv2.imwrite(out_path, canvas)
    print(f"Overlay saved to: {out_path}")


def thicken_edges(edges, kernel_size=3, iterations=1):
    e = (edges > 0).astype(np.uint8) * 255
    kernel = cv2.getStructuringElement(cv2.MORPH_CROSS, (kernel_size, kernel_size))
    thick = cv2.dilate(e, kernel, iterations=iterations)
    return thick


def main():
    edge_path = None
    binary_path = None
    if len(sys.argv) >= 2:
        edge_path = sys.argv[1]
    if len(sys.argv) >= 3:
        binary_path = sys.argv[2]

    edges, binary = load_inputs(edge_path, binary_path)
    if binary is None:
        print("Error: Binary wall mask is required.")
        sys.exit(1)
    # Ensure we have an edge map; if missing, derive from binary via morphological gradient
    if edges is None:
        print("Edge map not found. Deriving edges from binary wall mask (morphological gradient)...")
        k = cv2.getStructuringElement(cv2.MORPH_CROSS, (3, 3))
        dil = cv2.dilate(binary, k, iterations=1)
        ero = cv2.erode(binary, k, iterations=1)
        edges = cv2.subtract(dil, ero)

    print("Thickening edges for stable Hough detection...")
    thick_edges = thicken_edges(edges, kernel_size=3, iterations=1)
    h_img, w_img = thick_edges.shape[:2]
    max_dim = max(h_img, w_img)

    segs, min_line_len, max_line_gap = detect_raw_lines(thick_edges)
    print(f"Raw segments detected: {len(segs)}")

    filtered = filter_segments(segs, min_line_len)
    print(f"After orientation/length filtering: {len(filtered)}")

    filtered2 = filter_by_binary_overlap(filtered, binary, min_overlap_ratio=0.5, min_overlap_pixels=20)
    print(f"After binary-overlap filtering: {len(filtered2)} (removed {len(filtered) - len(filtered2)} by binary gating)")

    merged = group_and_merge(filtered2, max_line_gap, thick_edges.shape)
    print(f"Merged segments: {len(merged)}")

    segments = build_output(merged)
    save_outputs(segments)
    visualize_segments(segments, thick_edges.shape)

    if len(segments) > 0:
        horiz = sum(1 for s in segments if s["orientation"] == "horizontal")
        vert = sum(1 for s in segments if s["orientation"] == "vertical")
        total = len(segments)
        axis_aligned_pct = 100.0 * (horiz + vert) / total
        print(f"Axis-aligned segments: {axis_aligned_pct:.2f}% (H: {horiz}, V: {vert})")
        # Segment length bias: fraction of segments longer than 10% of max dimension
        min_long = 0.10 * max_dim
        long_cnt = sum(1 for s in segments if s["length_px"] >= min_long)
        print(f"Long segments (>=10% of max dim): {long_cnt}/{total}")


if __name__ == "__main__":
    main()
