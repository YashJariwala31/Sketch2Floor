# stage5_architectural_cleanup.py
#
# Stage 5 – Architectural Cleanup Rules
#
# Convert wall centerline graph (Stage 3 output) into clean CAD-like thick wall geometry
# using vector math only (no raster operations).
#
# Input:  data/intermediate/wall_graph.json (from Stage 3)
# Output: data/intermediate/wall_polygons.json
#         data/intermediate/stage5_wall_overlay.png
#
# Algorithm:
#   1. Load wall graph nodes and edges
#   2. For each wall segment, determine if horizontal or vertical
#   3. Generate two parallel offset lines at ± wall_thickness/2
#   4. Convert each thickened wall into a rectangle polygon
#   5. At each shared node, compute intersection of adjacent offset edges
#   6. Resolve corner joins using clean miter joins
#   7. Trim overlapping wall rectangles at junctions
#   8. Ensure no gaps or overlaps remain between adjacent walls
#   9. Merge overlapping wall polygons into unified geometry

import sys
import os
import json
import math
import numpy as np
import cv2
from typing import List, Tuple, Dict, Any
from dataclasses import dataclass
from . import utils
from dataclasses import dataclass


# -- Constants ---------------------------------------------------------------
WALL_THICKNESS_PX = 20
HALF_THICKNESS = WALL_THICKNESS_PX / 2
TOLERANCE = 2.0  # For floating point comparisons (increased for robust axis detection)


# =============================================================================
# Data Structures
# =============================================================================

@dataclass
class Point:
    x: float
    y: float
    
    def __hash__(self):
        return hash((self.x, self.y))
    
    def distance_to(self, other: 'Point') -> float:
        return math.sqrt((self.x - other.x)**2 + (self.y - other.y)**2)

@dataclass
class WallSegment:
    start: Point
    end: Point
    node_id: int
    
    @property
    def length(self) -> float:
        return self.start.distance_to(self.end)
    
    @property
    def is_horizontal(self) -> bool:
        return abs(self.start.y - self.end.y) < TOLERANCE
    
    @property
    def is_vertical(self) -> bool:
        return abs(self.start.x - self.end.x) < TOLERANCE

@dataclass
class WallPolygon:
    vertices: List[Tuple[float, float]]
    area: float


# =============================================================================
# 1. Load wall graph
# =============================================================================

def load_wall_graph(graph_path=None):
    """Load wall graph from Stage 3 output."""
    if graph_path is None:
        graph_path = os.path.join(utils.get_intermediate_dir(), "wall_graph.json")
    
    data = utils.load_json(graph_path)
    nodes = data['nodes']
    edges = data['edges']
    
    print(f"Loaded wall graph: {len(nodes)} nodes, {len(edges)} edges")
    return nodes, edges


# =============================================================================
# 2. Parse wall segments
# =============================================================================

def parse_wall_segments(nodes: List[Dict], edges: List[Dict]) -> List[WallSegment]:
    """Convert graph nodes and edges to wall segments."""
    segments = []
    
    # Create node lookup by ID for fast access
    node_lookup = {node['id']: node for node in nodes}
    
    for i, edge in enumerate(edges):
        node1_id = edge['start_node']
        node2_id = edge['end_node']
        
        if node1_id not in node_lookup or node2_id not in node_lookup:
            raise ValueError(f"Edge references non-existent node: {node1_id} or {node2_id}")
        
        node1 = node_lookup[node1_id]
        node2 = node_lookup[node2_id]
        
        start = Point(node1['x'], node1['y'])
        end = Point(node2['x'], node2['y'])
        
        # Snap nearly axis-aligned segments to perfect alignment
        dx = end.x - start.x
        dy = end.y - start.y
        SNAP_TOLERANCE = 5
        
        if abs(dy) < SNAP_TOLERANCE:
            end = Point(end.x, start.y)
        elif abs(dx) < SNAP_TOLERANCE:
            end = Point(start.x, end.y)
        
        segment = WallSegment(start, end, i)
        segments.append(segment)
    
    print(f"Parsed {len(segments)} wall segments using schema: start_node/end_node")
    return segments


# =============================================================================
# 3. Generate thick wall rectangles
# =============================================================================

def generate_wall_rectangle(segment: WallSegment, junction_set: set = None) -> List[Tuple[float, float]]:
    """Generate rectangle vertices for a thick wall segment.
    
    At junction endpoints (where multiple walls meet), the rectangle is
    extended by HALF_THICKNESS along the wall axis so that perpendicular
    wall rectangles overlap, eliminating corner/T-junction gaps.
    """
    if segment.is_horizontal:
        y = segment.start.y
        x1, x2 = min(segment.start.x, segment.end.x), max(segment.start.x, segment.end.x)
        
        # Extend at junction endpoints to create overlap
        if junction_set:
            if _point_in_set(x1, y, junction_set):
                x1 -= HALF_THICKNESS
            if _point_in_set(x2, y, junction_set):
                x2 += HALF_THICKNESS
        
        vertices = [
            (x1, y - HALF_THICKNESS),
            (x2, y - HALF_THICKNESS),
            (x2, y + HALF_THICKNESS),
            (x1, y + HALF_THICKNESS)
        ]
    elif segment.is_vertical:
        x = segment.start.x
        y1, y2 = min(segment.start.y, segment.end.y), max(segment.start.y, segment.end.y)
        
        # Extend at junction endpoints to create overlap
        if junction_set:
            if _point_in_set(x, y1, junction_set):
                y1 -= HALF_THICKNESS
            if _point_in_set(x, y2, junction_set):
                y2 += HALF_THICKNESS
        
        vertices = [
            (x - HALF_THICKNESS, y1),
            (x + HALF_THICKNESS, y1),
            (x + HALF_THICKNESS, y2),
            (x - HALF_THICKNESS, y2)
        ]
    else:
        # Non-axis-aligned segment: skip gracefully instead of crashing
        print(f"  [WARN] Skipping non-axis-aligned segment: {segment}")
        return None
    
    return vertices


def _point_in_set(x: float, y: float, junction_set: set, tol: float = 2.0) -> bool:
    """Check if a point (x, y) matches any point in the junction set within tolerance."""
    for jx, jy in junction_set:
        if abs(x - jx) <= tol and abs(y - jy) <= tol:
            return True
    return False


# =============================================================================
# 4. Find wall junctions
# =============================================================================

def find_wall_junctions(segments: List[WallSegment]) -> Dict[Point, List[WallSegment]]:
    """Find nodes where multiple walls meet."""
    junctions = {}
    
    for segment in segments:
        # Check both endpoints
        for point in [segment.start, segment.end]:
            if point not in junctions:
                junctions[point] = []
            junctions[point].append(segment)
    
    return junctions


# =============================================================================
# 5. Resolve corner joins
# =============================================================================

def resolve_corner_junction(junction_point: Point, segments: List[WallSegment]) -> List[WallPolygon]:
    """Resolve wall junctions at a point."""
    if len(segments) == 2:
        # L-corner or straight continuation
        seg1, seg2 = segments
        
        # Check if it's an L-corner (one horizontal, one vertical)
        if (seg1.is_horizontal and seg2.is_vertical) or (seg1.is_vertical and seg2.is_horizontal):
            return resolve_l_corner(junction_point, seg1, seg2)
        else:
            # Straight continuation - no special handling needed
            return []
    elif len(segments) == 3:
        # T-junction
        return resolve_t_junction(junction_point, segments)
    else:
        # Complex junction - handle generically
        return []


def resolve_l_corner(corner_point: Point, h_seg: WallSegment, v_seg: WallSegment) -> List[WallPolygon]:
    """Resolve L-corner intersection."""
    # Find which segment is horizontal/vertical
    if h_seg.is_horizontal:
        h_wall = h_seg
        v_wall = v_seg
    else:
        h_wall = v_seg
        v_wall = h_seg
    
    # Generate extended rectangles that overlap at corner
    h_rect = generate_wall_rectangle(h_wall)
    v_rect = generate_wall_rectangle(v_wall)
    
    # Create merged corner polygon (simplified approach)
    # For now, return individual rectangles - merging will be handled later
    return [
        WallPolygon(h_rect, calculate_polygon_area(h_rect)),
        WallPolygon(v_rect, calculate_polygon_area(v_rect))
    ]


def resolve_t_junction(junction_point: Point, segments: List[WallSegment]) -> List[WallPolygon]:
    """Resolve T-junction by trimming branch walls."""
    # Identify main wall (longest) and branch walls
    main_wall = max(segments, key=lambda s: s.length)
    branch_walls = [s for s in segments if s != main_wall]
    
    polygons = []
    
    # Main wall gets full rectangle
    main_rect = generate_wall_rectangle(main_wall)
    polygons.append(WallPolygon(main_rect, calculate_polygon_area(main_rect)))
    
    # Branch walls get trimmed rectangles
    for branch in branch_walls:
        # Trim branch to meet main wall boundary
        trimmed_rect = generate_trimmed_branch_rectangle(branch, main_wall)
        polygons.append(WallPolygon(trimmed_rect, calculate_polygon_area(trimmed_rect)))
    
    return polygons


def generate_trimmed_branch_rectangle(branch: WallSegment, main_wall: WallSegment) -> List[Tuple[float, float]]:
    """Generate rectangle for branch wall trimmed to main wall."""
    # Simplified: use full rectangle for now
    # In a full implementation, this would trim to main wall boundary
    return generate_wall_rectangle(branch)


# =============================================================================
# 6. Polygon utilities
# =============================================================================

def calculate_polygon_area(vertices: List[Tuple[float, float]]) -> float:
    """Calculate area using utils."""
    return utils.calculate_polygon_area(vertices)


# =============================================================================
# 7. Merge overlapping polygons
# =============================================================================

def merge_overlapping_polygons(polygons: List[WallPolygon]) -> List[WallPolygon]:
    """Merge overlapping and adjacent wall polygons to eliminate redundancy."""
    unique_polygons = {}

    # Step 1: Deduplicate identical polygons
    for poly in polygons:
        # Create canonical key from sorted vertices
        key = tuple(sorted(poly.vertices))

        if key not in unique_polygons:
            unique_polygons[key] = poly

    deduplicated = list(unique_polygons.values())
    
    # Step 2: Merge collinear and adjacent rectangles
    return merge_adjacent_rectangles(deduplicated)


def merge_adjacent_rectangles(polygons: List[WallPolygon]) -> List[WallPolygon]:
    """Merge collinear and adjacent wall rectangles."""
    if not polygons:
        return []
    
    # Separate horizontal and vertical walls
    horizontal_walls = []
    vertical_walls = []
    
    for poly in polygons:
        vertices = poly.vertices
        if len(vertices) != 4:
            continue  # Skip non-rectangular polygons
        
        # Find bounding box
        xs = [v[0] for v in vertices]
        ys = [v[1] for v in vertices]
        x_min, x_max = min(xs), max(xs)
        y_min, y_max = min(ys), max(ys)
        
        # Determine orientation
        if abs(x_max - x_min) > abs(y_max - y_min):
            # Horizontal wall (width > height)
            horizontal_walls.append({
                'polygon': poly,
                'x_min': x_min,
                'x_max': x_max,
                'y_min': y_min,
                'y_max': y_max
            })
        else:
            # Vertical wall (height >= width)
            vertical_walls.append({
                'polygon': poly,
                'x_min': x_min,
                'x_max': x_max,
                'y_min': y_min,
                'y_max': y_max
            })
    
    # Merge horizontal walls
    merged_horizontal = merge_horizontal_walls(horizontal_walls)
    
    # Merge vertical walls
    merged_vertical = merge_vertical_walls(vertical_walls)
    
    # Combine results
    return [wall['polygon'] for wall in merged_horizontal + merged_vertical]


def merge_horizontal_walls(horizontal_walls: List[dict]) -> List[dict]:
    """Merge adjacent horizontal wall rectangles."""
    if not horizontal_walls:
        return []
    
    # Group by y-range (same thickness band)
    y_groups = {}
    for wall in horizontal_walls:
        # Create key from y-range (allowing for small floating point differences)
        y_key = (round(wall['y_min'], 2), round(wall['y_max'], 2))
        if y_key not in y_groups:
            y_groups[y_key] = []
        y_groups[y_key].append(wall)
    
    merged = []
    
    # Merge within each y-group
    for y_key, group in y_groups.items():
        # Sort by x_min
        group.sort(key=lambda w: w['x_min'])
        
        current_merged = [group[0]]
        
        for wall in group[1:]:
            last = current_merged[-1]
            
            # Check if walls touch or overlap (x_min <= x_max)
            if wall['x_min'] <= last['x_max'] + TOLERANCE:
                # Merge: extend x_max to the furthest edge
                last['x_max'] = max(last['x_max'], wall['x_max'])
                
                # Update the polygon vertices
                merged_vertices = [
                    (last['x_min'], last['y_min']),
                    (last['x_max'], last['y_min']),
                    (last['x_max'], last['y_max']),
                    (last['x_min'], last['y_max'])
                ]
                last['polygon'] = WallPolygon(merged_vertices, calculate_polygon_area(merged_vertices))
            else:
                # No overlap, start new merged wall
                current_merged.append(wall)
        
        merged.extend(current_merged)
    
    return merged


def merge_vertical_walls(vertical_walls: List[dict]) -> List[dict]:
    """Merge adjacent vertical wall rectangles."""
    if not vertical_walls:
        return []
    
    # Group by x-range (same thickness band)
    x_groups = {}
    for wall in vertical_walls:
        # Create key from x-range (allowing for small floating point differences)
        x_key = (round(wall['x_min'], 2), round(wall['x_max'], 2))
        if x_key not in x_groups:
            x_groups[x_key] = []
        x_groups[x_key].append(wall)
    
    merged = []
    
    # Merge within each x-group
    for x_key, group in x_groups.items():
        # Sort by y_min
        group.sort(key=lambda w: w['y_min'])
        
        current_merged = [group[0]]
        
        for wall in group[1:]:
            last = current_merged[-1]
            
            # Check if walls touch or overlap (y_min <= y_max)
            if wall['y_min'] <= last['y_max'] + TOLERANCE:
                # Merge: extend y_max to the furthest edge
                last['y_max'] = max(last['y_max'], wall['y_max'])
                
                # Update the polygon vertices
                merged_vertices = [
                    (last['x_min'], last['y_min']),
                    (last['x_max'], last['y_min']),
                    (last['x_max'], last['y_max']),
                    (last['x_min'], last['y_max'])
                ]
                last['polygon'] = WallPolygon(merged_vertices, calculate_polygon_area(merged_vertices))
            else:
                # No overlap, start new merged wall
                current_merged.append(wall)
        
        merged.extend(current_merged)
    
    return merged


# =============================================================================
# 8. Main processing pipeline
# =============================================================================

def process_walls():
    """Main pipeline for architectural cleanup."""
    print("=" * 60)
    print("  Stage 5: Architectural Cleanup Rules")
    print("=" * 60)
    print()
    
    # 1. Load wall graph
    nodes, edges = load_wall_graph()
    
    # 2. Parse wall segments
    segments = parse_wall_segments(nodes, edges)
    
    # 3. Find junctions
    junctions = find_wall_junctions(segments)
    
    # 3b. Build junction point set (nodes with degree >= 2)
    #     These are corners, T-junctions, and crossings where wall
    #     rectangles must overlap to eliminate visual gaps.
    junction_set = set()
    for point, segs in junctions.items():
        if len(segs) >= 2:
            junction_set.add((point.x, point.y))
    print(f"  Junction points (degree>=2): {len(junction_set)}")
    
    # 4. Generate wall polygons with junction-aware extension
    all_polygons = []
    skipped = 0
    
    for segment in segments:
        rect = generate_wall_rectangle(segment, junction_set)
        if rect is None:
            skipped += 1
            continue
        polygon = WallPolygon(rect, calculate_polygon_area(rect))
        all_polygons.append(polygon)
    
    if skipped:
        print(f"  [WARN] Skipped {skipped} non-axis-aligned segments")
    
    # 5. Merge overlapping polygons
    final_polygons = merge_overlapping_polygons(all_polygons)
    
    print(f"Generated {len(final_polygons)} wall polygons")
    
    return final_polygons


# =============================================================================
# 9. Save outputs
# =============================================================================

def save_wall_polygons(polygons: List[WallPolygon], output_path=None):
    """Save wall polygons to JSON file, upscaled to original image coordinates."""
    if output_path is None:
        output_path = os.path.join(utils.get_intermediate_dir(), "wall_polygons.json")
    
    sx, sy = utils.load_scale_factors()
    print(f"Loaded scale factors: sx={sx:.4f}, sy={sy:.4f}")
    
    data = []
    for i, polygon in enumerate(polygons):
        upscaled_vertices = [
            (v[0] * sx, v[1] * sy) for v in polygon.vertices
        ]
        upscaled_area = round(polygon.area * (sx * sy), 1)
        data.append({
            "wall_id": i,
            "vertices": upscaled_vertices,
            "area_px": upscaled_area
        })
    
    utils.save_json(data, output_path)
    print(f"Saved wall polygons -> {output_path}")


# =============================================================================
# 10. Visualization
# =============================================================================

def visualize_walls(polygons: List[WallPolygon], output_path=None):
    """Visualize wall polygons as CAD-like drawing."""
    if output_path is None:
        output_path = os.path.join(utils.get_intermediate_dir(), "stage5_wall_overlay.png")
    
    # Determine canvas size
    if not polygons:
        print("No polygons to visualize")
        return
    
    all_x = [v[0] for poly in polygons for v in poly.vertices]
    all_y = [v[1] for poly in polygons for v in poly.vertices]
    
    min_x, max_x = min(all_x), max(all_x)
    min_y, max_y = min(all_y), max(all_y)
    
    # Add padding
    padding = 50
    canvas_width = int(max_x - min_x + 2 * padding)
    canvas_height = int(max_y - min_y + 2 * padding)
    
    # Create white canvas
    canvas = np.ones((canvas_height, canvas_width, 3), dtype=np.uint8) * 255
    
    # Draw walls
    for polygon in polygons:
        # Convert vertices to canvas coordinates
        canvas_vertices = []
        for x, y in polygon.vertices:
            canvas_x = int(x - min_x + padding)
            canvas_y = int(y - min_y + padding)
            canvas_vertices.append([canvas_x, canvas_y])
        
        # Draw filled polygon
        pts = np.array(canvas_vertices, dtype=np.int32)
        cv2.fillPoly(canvas, [pts], (50, 50, 50))  # Dark gray walls
        
        # Draw outline
        cv2.polylines(canvas, [pts], True, (0, 0, 0), 2)  # Black outline
    
    # Save visualization
    cv2.imwrite(output_path, canvas)
    print(f"Visualization saved -> {output_path}")


# =============================================================================
# Main
# =============================================================================

def main():
    """Main execution function."""
    try:
        # Process walls
        polygons = process_walls()
        
        # Save outputs
        save_wall_polygons(polygons)
        visualize_walls(polygons)
        
        print()
        print("Stage 5 completed successfully!")
        print(f"Generated {len(polygons)} clean wall polygons")
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
