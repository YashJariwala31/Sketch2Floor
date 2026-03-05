# stage4_room_detection.py
#
# Stage 4 – Room Detection from Wall Graph
#
# Detect enclosed rooms by finding rectangular regions bounded by
# perpendicular wall segments.
#
# Input:  data/intermediate/wall_graph.json (from Stage 3)
# Output: data/intermediate/room_polygons.json
#         data/intermediate/room_detection_overlay.png
#
# Algorithm:
#   1. Extract horizontal and vertical wall segments from graph edges
#   2. Find corner candidates where H and V walls share endpoints
#   3. Identify potential rectangles from corner pairs
#   4. Validate rectangles have enclosing walls on all sides
#   5. Filter rooms by area (reject noise and outer boundary)

import sys
import os
import json
import math
import numpy as np
import cv2
from collections import defaultdict


# -- Tolerances ---------------------------------------------------------------
MIN_ROOM_AREA = 2000      # Minimum area in px² (reject noise regions)
WALL_GAP_TOL = 50         # Max gap for walls to be considered connected


# =============================================================================
# 1. Load wall graph
# =============================================================================

def load_wall_graph(json_path=None):
    """Load wall graph from Stage 3 output."""
    if json_path is None:
        json_path = os.path.join("data", "intermediate", "wall_graph.json")
    
    with open(json_path, "r") as f:
        data = json.load(f)
    
    nodes = data["nodes"]
    edges = data["edges"]
    
    # Build coordinate lookup
    node_coords = {n["id"]: (n["x"], n["y"]) for n in nodes}
    
    print(f"Loaded wall graph: {len(nodes)} nodes, {len(edges)} edges")
    return nodes, edges, node_coords


# =============================================================================
# 2. Extract wall segments from edges
# =============================================================================

def extract_wall_segments(edges, node_coords):
    """
    Categorize edges as horizontal or vertical segments.
    
    Returns:
        h_walls: list of (y, x_min, x_max) for horizontal walls
        v_walls: list of (x, y_min, y_max) for vertical walls
    """
    h_walls = []  # (y, x_min, x_max)
    v_walls = []  # (x, y_min, y_max)
    
    for e in edges:
        n1, n2 = e["start_node"], e["end_node"]
        x1, y1 = node_coords[n1]
        x2, y2 = node_coords[n2]
        
        if abs(y1 - y2) < 5:  # Horizontal (same Y)
            y = y1
            x_min, x_max = min(x1, x2), max(x1, x2)
            h_walls.append((y, x_min, x_max))
        elif abs(x1 - x2) < 5:  # Vertical (same X)
            x = x1
            y_min, y_max = min(y1, y2), max(y1, y2)
            v_walls.append((x, y_min, y_max))
    
    print(f"Wall segments: {len(h_walls)} horizontal, {len(v_walls)} vertical")
    return h_walls, v_walls


# =============================================================================
# 3. Find corner points (H/V intersections)
# =============================================================================

def find_corners(h_walls, v_walls):
    """
    Find corner points where horizontal and vertical walls intersect.
    
    A corner exists where:
        - A vertical wall's x is within a horizontal wall's x-range
        - A horizontal wall's y is within a vertical wall's y-range
    
    Returns list of (x, y) corner coordinates.
    """
    corners = set()
    
    for hy, hx1, hx2 in h_walls:
        for vx, vy1, vy2 in v_walls:
            # Check if V's x is within H's x-range
            if hx1 <= vx <= hx2:
                # Check if H's y is within V's y-range
                if vy1 <= hy <= vy2:
                    corners.add((vx, hy))
    
    print(f"Found {len(corners)} corner points")
    return list(corners)


# =============================================================================
# 4. Detect rooms from binary wall mask (contour-based)
# =============================================================================

def detect_rooms_from_mask(binary_path=None, min_area=MIN_ROOM_AREA):
    """
    Detect enclosed rooms by finding empty regions surrounded by walls.
    
    Rooms are the BACKGROUND regions enclosed by walls, not holes in walls.
    We flood-fill from the image edges to mark exterior, then find remaining
    enclosed white regions.
    
    Returns list of (x1, y1, x2, y2, area, contour) tuples.
    """
    if binary_path is None:
        binary_path = os.path.join("data", "intermediate", "binary_wall_mask.png")
    
    if not os.path.exists(binary_path):
        print(f"Binary wall mask not found at {binary_path}")
        return [], (720, 1024)
    
    # Load binary mask (walls are white/255, background is black/0)
    mask = cv2.imread(binary_path, cv2.IMREAD_GRAYSCALE)
    if mask is None:
        print("Failed to load binary wall mask")
        return [], (720, 1024)
    
    h, w = mask.shape
    print(f"Binary mask: {w}x{h}")
    
    # Close small gaps in walls to prevent flood-fill leakage
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    closed_mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    
    # Create a mask for flood filling - need 2 pixels larger
    flood_mask = np.zeros((h + 2, w + 2), np.uint8)
    
    # Invert: walls become 0 (barriers), background becomes 255 (fillable)
    inverted = cv2.bitwise_not(closed_mask)
    
    # Flood fill from all four corners to mark exterior regions
    # Use 128 as the fill value to distinguish from rooms (255)
    corners = [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)]
    
    for cx, cy in corners:
        if inverted[cy, cx] == 255:
            cv2.floodFill(inverted, flood_mask, (cx, cy), 128)
    
    # Now: 128 = exterior (connected to edges), 255 = enclosed rooms, 0 = walls
    room_mask = (inverted == 255).astype(np.uint8) * 255
    
    # Debug: count pixels
    exterior_px = np.count_nonzero(inverted == 128)
    room_px = np.count_nonzero(room_mask)
    wall_px = np.count_nonzero(closed_mask)
    print(f"  Exterior: {exterior_px}px, Rooms: {room_px}px, Walls: {wall_px}px")
    
    # Find contours of enclosed regions
    contours, _ = cv2.findContours(room_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    rooms = []
    for contour in contours:
        area = cv2.contourArea(contour)
        if area >= min_area:
            x, y, bw, bh = cv2.boundingRect(contour)
            rooms.append((x, y, x + bw, y + bh, area, contour))
    
    print(f"Detected {len(rooms)} enclosed regions from mask")
    return rooms, (h, w)


# =============================================================================
# 5. Deduplicate and filter rectangles
# =============================================================================

def deduplicate_rectangles(rectangles):
    """
    Remove duplicate and nested rectangles.
    Keep only the smallest rectangle at each location.
    """
    if not rectangles:
        return []
    
    # Sort by area (ascending) - process smallest first
    sorted_rects = sorted(rectangles, key=lambda r: (r[2]-r[0])*(r[3]-r[1]))
    
    unique = []
    for rect in sorted_rects:
        rx1, ry1, rx2, ry2 = rect
        is_duplicate = False
        
        for existing in unique:
            ex1, ey1, ex2, ey2 = existing
            # Check if rect is inside existing
            if ex1 <= rx1 and ey1 <= ry1 and ex2 >= rx2 and ey2 >= ry2:
                is_duplicate = True
                break
        
        if not is_duplicate:
            unique.append(rect)
    
    print(f"After deduplication: {len(unique)} unique rectangles")
    return unique


# =============================================================================
# 6. Compute polygon area (shoelace formula)
# =============================================================================

def compute_polygon_area(polygon):
    """
    Compute polygon area using the shoelace formula.
    
    Area = 0.5 * |sum(x_i * y_{i+1} - x_{i+1} * y_i)|
    
    Works for any simple polygon (convex or concave).
    """
    if len(polygon) < 3:
        return 0.0
    
    n = len(polygon)
    area = 0.0
    
    for i in range(n):
        j = (i + 1) % n
        area += polygon[i][0] * polygon[j][1]
        area -= polygon[j][0] * polygon[i][1]
    
    return abs(area) / 2.0


# =============================================================================
# 7. Filter rooms
# =============================================================================

def filter_rooms(polygons_with_areas, min_area=MIN_ROOM_AREA):
    """
    Filter rooms based on area criteria:
    
    1. Reject polygons smaller than min_area (noise regions)
    
    Note: We do NOT remove the largest polygon because the flood-fill
    already excluded the exterior. The remaining regions are all rooms.
    
    Returns filtered list of (polygon, area) tuples.
    """
    if not polygons_with_areas:
        return []
    
    # Filter by minimum area
    filtered = [(poly, area) for poly, area in polygons_with_areas if area >= min_area]
    
    removed_small = len(polygons_with_areas) - len(filtered)
    
    print(f"Filtered: {len(polygons_with_areas)} -> {len(filtered)} rooms")
    if removed_small > 0:
        print(f"  Removed {removed_small} small regions (< {min_area} px²)")
    
    return filtered


# =============================================================================
# 8. Build output
# =============================================================================

def build_output(rooms):
    """
    Build the output format for room polygons.
    """
    output = []
    for i, (polygon, area) in enumerate(rooms):
        output.append({
            "room_id": i,
            "polygon": polygon,
            "area_px": round(area, 1)
        })
    return output


# =============================================================================
# 9. Save outputs
# =============================================================================

def save_outputs(rooms, save_dir=None):
    """Save room polygons to JSON file."""
    if save_dir is None:
        save_dir = os.path.join("data", "intermediate")
    
    os.makedirs(save_dir, exist_ok=True)
    
    json_path = os.path.join(save_dir, "room_polygons.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(rooms, f, indent=2)
    
    print(f"Saved -> {json_path}")


# =============================================================================
# 10. Visualization
# =============================================================================

def get_image_dimensions():
    """Get image dimensions from binary wall mask."""
    p = os.path.join("data", "intermediate", "binary_wall_mask.png")
    if os.path.exists(p):
        img = cv2.imread(p, cv2.IMREAD_GRAYSCALE)
        if img is not None:
            return img.shape
    return (720, 1024)


def visualize(rooms, nodes, edges, node_coords, img_shape, save_dir=None):
    """
    Visualize detected rooms as colored polygons overlaid on wall graph.
    """
    if save_dir is None:
        save_dir = os.path.join("data", "intermediate")
    
    h, w = img_shape[:2]
    
    # Try to load wall graph image as background
    graph_path = os.path.join(save_dir, "wall_graph.png")
    if os.path.exists(graph_path):
        bg = cv2.imread(graph_path)
        if bg is None:
            bg = np.zeros((h, w, 3), np.uint8)
    else:
        # Try binary wall mask
        mask_path = os.path.join("data", "intermediate", "binary_wall_mask.png")
        if os.path.exists(mask_path):
            mask = cv2.imread(mask_path, cv2.IMREAD_GRAYSCALE)
            if mask is not None:
                bg = cv2.cvtColor((mask * 0.35).astype(np.uint8), cv2.COLOR_GRAY2BGR)
            else:
                bg = np.zeros((h, w, 3), np.uint8)
        else:
            bg = np.zeros((h, w, 3), np.uint8)
    
    # Generate distinct colors for rooms
    colors = [
        (255, 200, 150),   # Light orange
        (150, 255, 200),   # Light green
        (200, 150, 255),   # Light purple
        (255, 255, 150),   # Light yellow
        (150, 200, 255),   # Light blue
        (255, 150, 200),   # Light pink
        (200, 255, 150),   # Light lime
        (150, 255, 255),   # Light cyan
    ]
    
    # Draw each room as a filled polygon
    for i, room in enumerate(rooms):
        polygon = room["polygon"]
        color = colors[i % len(colors)]
        
        # Convert to numpy array for cv2.fillPoly
        pts = np.array(polygon, dtype=np.int32)
        pts = pts.reshape((-1, 1, 2))
        
        # Draw filled polygon with transparency effect
        overlay = bg.copy()
        cv2.fillPoly(overlay, [pts], color)
        cv2.addWeighted(overlay, 0.4, bg, 0.6, 0, bg)
        
        # Draw polygon outline
        cv2.polylines(bg, [pts], True, (0, 0, 0), 2)
        
        # Add room label at centroid
        cx = sum(p[0] for p in polygon) // len(polygon)
        cy = sum(p[1] for p in polygon) // len(polygon)
        label = f"R{room['room_id']}"
        cv2.putText(bg, label, (cx - 10, cy + 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 2)
        cv2.putText(bg, label, (cx - 10, cy + 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
    
    # Save visualization
    out_path = os.path.join(save_dir, "room_detection_overlay.png")
    cv2.imwrite(out_path, bg)
    print(f"Visualization -> {out_path}")


# =============================================================================
# Main
# =============================================================================

def rectangle_to_polygon(rect):
    """Convert rectangle (x1, y1, x2, y2) to polygon vertices."""
    x1, y1, x2, y2 = rect
    return [[x1, y1], [x2, y1], [x2, y2], [x1, y2]]


def main():
    print("=" * 55)
    print("  Stage 4: Room Detection from Wall Graph")
    print("=" * 55)
    print()
    
    # 1. Load wall graph (for visualization overlay)
    nodes, edges, node_coords = load_wall_graph()
    
    # 2. Detect rooms from binary wall mask (contour-based)
    rooms_data, img_shape = detect_rooms_from_mask(min_area=MIN_ROOM_AREA)
    
    # 3. Convert to polygons and compute areas
    polygons_with_areas = []
    for x1, y1, x2, y2, area, contour in rooms_data:
        # Approximate contour to polygon
        peri = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, 0.02 * peri, True)
        polygon = [[int(pt[0][0]), int(pt[0][1])] for pt in approx]
        
        # Ensure polygon has at least 3 vertices
        if len(polygon) >= 3:
            # Recompute area from polygon
            poly_area = compute_polygon_area(polygon)
            polygons_with_areas.append((polygon, poly_area))
    
    print(f"Converted {len(polygons_with_areas)} contours to polygons")
    
    # 4. Filter rooms
    rooms = filter_rooms(polygons_with_areas, MIN_ROOM_AREA)
    
    # 5. Build output
    output = build_output(rooms)
    
    # 6. Save outputs
    save_outputs(output)
    
    # 7. Visualize
    visualize(output, nodes, edges, node_coords, img_shape)
    
    # Summary
    print()
    print(f"Detected {len(output)} rooms")
    if output:
        areas = [r["area_px"] for r in output]
        print(f"Area range: {min(areas):.0f} - {max(areas):.0f} px²")
    
    print("\nStage 4 completed successfully!")


if __name__ == "__main__":
    main()
