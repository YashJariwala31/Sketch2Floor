# stage4_room_detection.py
#
# Stage 4 – Room Detection from Wall Graph
#
# Detect enclosed rooms by finding closed cycles in the wall graph
# and converting them into polygon regions.
#
# Input:  data/intermediate/wall_graph.json (from Stage 3)
# Output: data/intermediate/room_polygons.json
#         data/intermediate/room_detection_overlay.png
#
# Algorithm:
#   1. Build adjacency list from edges
#   2. Find simple closed cycles using DFS with path tracking
#   3. Normalize cycles to remove duplicates
#   4. Convert cycles to polygons using node coordinates
#   5. Compute polygon area using shoelace formula
#   6. Filter rooms by area (reject noise and outer boundary)

import sys
import os
import json
import math
import numpy as np
import cv2
from collections import defaultdict


# -- Tolerances ---------------------------------------------------------------
MIN_CYCLE_NODES = 4       # Minimum nodes for a valid room cycle
MIN_ROOM_AREA = 2000      # Minimum area in px² (reject noise regions)


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
# 2. Build adjacency list
# =============================================================================

def build_adjacency(edges):
    """
    Create adjacency list from edges.
    Each node maps to a list of its neighbors.
    """
    adj = defaultdict(set)
    for e in edges:
        a, b = e["start_node"], e["end_node"]
        adj[a].add(b)
        adj[b].add(a)
    
    return adj


# =============================================================================
# 3. Find cycles using DFS
# =============================================================================

def find_all_cycles(adj, min_nodes=MIN_CYCLE_NODES):
    """
    Find all simple closed cycles in the graph using DFS with path tracking.
    
    A cycle is found when we revisit a node that's already in our current path.
    We extract the cycle from the path and store it.
    
    Returns list of cycles, where each cycle is a list of node IDs.
    """
    all_cycles = []
    visited_global = set()
    
    def dfs(start, current, path, visited_in_path):
        """
        DFS from 'start' node, tracking the current path.
        
        When we encounter a node already in our path, we've found a cycle.
        Extract the cycle from the path.
        """
        for neighbor in adj[current]:
            if neighbor == start and len(path) >= min_nodes:
                # Found a cycle back to start
                cycle = path[:]  # copy current path
                all_cycles.append(cycle)
            elif neighbor not in visited_in_path:
                # Continue DFS
                visited_in_path.add(neighbor)
                path.append(neighbor)
                dfs(start, neighbor, path, visited_in_path)
                path.pop()
                visited_in_path.remove(neighbor)
    
    # Start DFS from each unvisited node
    for start_node in adj.keys():
        if start_node not in visited_global:
            dfs(start_node, start_node, [start_node], {start_node})
            visited_global.add(start_node)
    
    print(f"DFS found {len(all_cycles)} raw cycles")
    return all_cycles


# =============================================================================
# 4. Normalize cycles to remove duplicates
# =============================================================================

def normalize_cycle(cycle):
    """
    Normalize a cycle for deduplication.
    
    1. Rotate cycle so minimum node ID is first
    2. Choose direction (forward/reverse) that gives smaller second element
    
    This ensures the same cycle is always represented identically
    regardless of starting point or traversal direction.
    """
    if not cycle:
        return tuple()
    
    n = len(cycle)
    
    # Find position of minimum node ID
    min_node = min(cycle)
    min_idx = cycle.index(min_node)
    
    # Rotate so min_node is first
    rotated = cycle[min_idx:] + cycle[:min_idx]
    
    # Choose direction: compare second element in both directions
    if n > 1:
        forward_second = rotated[1]
        reverse_second = rotated[-1]  # second element if reversed
        
        if reverse_second < forward_second:
            # Reverse direction is "smaller", use it
            rotated = [rotated[0]] + list(reversed(rotated[1:]))
    
    return tuple(rotated)


def deduplicate_cycles(cycles):
    """
    Remove duplicate cycles by normalizing each cycle and using a set.
    """
    seen = set()
    unique = []
    
    for cycle in cycles:
        normalized = normalize_cycle(cycle)
        if normalized not in seen and len(normalized) >= MIN_CYCLE_NODES:
            seen.add(normalized)
            unique.append(list(normalized))
    
    print(f"After deduplication: {len(unique)} unique cycles")
    return unique


# =============================================================================
# 5. Convert cycles to polygons
# =============================================================================

def cycle_to_polygon(cycle, node_coords):
    """
    Convert a cycle (list of node IDs) to a polygon (list of [x, y] coordinates).
    """
    polygon = []
    for node_id in cycle:
        if node_id in node_coords:
            x, y = node_coords[node_id]
            polygon.append([int(x), int(y)])
    return polygon


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
    2. Reject the largest polygon (outer boundary)
    
    Returns filtered list of (polygon, area) tuples.
    """
    if not polygons_with_areas:
        return []
    
    # Sort by area descending
    sorted_rooms = sorted(polygons_with_areas, key=lambda x: x[1], reverse=True)
    
    # Filter by minimum area
    filtered = [(poly, area) for poly, area in sorted_rooms if area >= min_area]
    
    if not filtered:
        print(f"All rooms filtered out (min_area={min_area})")
        return []
    
    # Remove the largest (outer boundary)
    # The largest enclosed region is typically the outer boundary of the floor plan
    rooms = filtered[1:] if len(filtered) > 1 else []
    
    removed_outer = len(filtered) - len(rooms)
    removed_small = len(polygons_with_areas) - len(filtered)
    
    print(f"Filtered: {len(polygons_with_areas)} -> {len(rooms)} rooms")
    print(f"  Removed {removed_small} small regions (< {min_area} px²)")
    print(f"  Removed {removed_outer} outer boundary")
    
    return rooms


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

def main():
    print("=" * 55)
    print("  Stage 4: Room Detection from Wall Graph")
    print("=" * 55)
    print()
    
    # 1. Load wall graph
    nodes, edges, node_coords = load_wall_graph()
    
    # 2. Build adjacency list
    adj = build_adjacency(edges)
    print(f"Adjacency: {len(adj)} nodes with neighbors")
    
    # 3. Find all cycles
    cycles = find_all_cycles(adj, MIN_CYCLE_NODES)
    
    # 4. Deduplicate cycles
    unique_cycles = deduplicate_cycles(cycles)
    
    # 5. Convert cycles to polygons and compute areas
    polygons_with_areas = []
    for cycle in unique_cycles:
        polygon = cycle_to_polygon(cycle, node_coords)
        if len(polygon) >= 3:  # Valid polygon needs at least 3 vertices
            area = compute_polygon_area(polygon)
            polygons_with_areas.append((polygon, area))
    
    print(f"Converted {len(polygons_with_areas)} cycles to polygons")
    
    # 6. Filter rooms
    rooms = filter_rooms(polygons_with_areas, MIN_ROOM_AREA)
    
    # 7. Build output
    output = build_output(rooms)
    
    # 8. Save outputs
    save_outputs(output)
    
    # 9. Visualize
    img_shape = get_image_dimensions()
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
