# stage4_room_detection.py
#
# Stage 4 – Room Detection via Flood Fill (Connected Components)
#
# Detect enclosed rooms directly from the binary wall mask using
# connected component analysis (flood fill).
#
# Input:  data/intermediate/binary_wall_mask.png (from Stage 1)
# Output: data/intermediate/room_polygons.json
#         data/intermediate/room_detection_overlay.png
#
# Algorithm:
#   1. Load binary wall mask (walls = 255, background = 0)
#   2. Invert mask (walls = 0, free space = 255)
#   3. Apply light morphological closing (3x3) to seal 1-2px leaks
#   4. Run connectedComponents to find enclosed regions
#   5. Ignore label 0 (background outside building)
#   6. Filter regions by area and border-touching
#   7. Extract and approximate contours
#   8. Store polygon vertices in room_polygons.json

import sys
import os
import json
import math
import numpy as np
import cv2
from collections import defaultdict
from . import utils


# -- Tolerances ---------------------------------------------------------------
MIN_ROOM_AREA_RATIO = 0.005  # Minimum room area as fraction of image (0.5%)
POLY_EPSILON = 3            # Contour approximation epsilon in pixels
MORPH_KERNEL_SIZE = 3       # Closing kernel to seal tiny leaks


# =============================================================================
# 1. Load binary wall mask
# =============================================================================

def load_wall_mask(mask_path=None):
    """Load binary wall mask from Stage 1 output."""
    mask = utils.load_wall_mask(mask_path)
    print(f"Loaded wall mask: {mask.shape[1]}x{mask.shape[0]}")
    return mask


# =============================================================================
# 2. Invert and preprocess mask
# =============================================================================

def preprocess_mask(mask):
    """
    Preprocess mask for robust room detection.

    Strategy:
    - Invert mask (free space = 255)
    - Seal only narrow gaps using distance transform
    """

    # Invert mask first
    free_space = cv2.bitwise_not(mask)

    # Distance transform (distance to nearest wall)
    dist = cv2.distanceTransform(free_space, cv2.DIST_L2, 5)

    # Threshold for narrow connections (tune 4–8 px)
    gap_threshold = 6

    # Remove narrow corridors
    sealed = free_space.copy()
    sealed[dist < gap_threshold] = 0

    print('Preprocessed: inverted + distance_transform sealing (thresh=6)')
    return sealed


# =============================================================================
# 3. Find connected components (enclosed regions)
# =============================================================================

def find_connected_regions(mask):
    """
    Find connected components in the preprocessed mask.
    
    Returns:
        num_labels: total number of labels (including background)
        labels: 2D array where each pixel has its component label
        stats: statistics for each component (x, y, width, height, area)
        centroids: centroid coordinates for each component
    """
    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(
        mask, connectivity=8
    )
    
    print(f"Connected components: {num_labels - 1} regions (excluding background)")
    return num_labels, labels, stats, centroids


# =============================================================================
# 4. Filter regions to valid rooms
# =============================================================================

def filter_regions(num_labels, stats, img_shape):
    """
    Filter connected components to valid rooms.

    Strategy:
    - Remove components touching image border (exterior)
    - Keep remaining components above minimum area
    """
    h, w = img_shape[:2]
    total_area = h * w
    min_area = total_area * MIN_ROOM_AREA_RATIO

    valid_regions = []

    for label_id in range(1, num_labels):
        x = stats[label_id][cv2.CC_STAT_LEFT]
        y = stats[label_id][cv2.CC_STAT_TOP]
        width = stats[label_id][cv2.CC_STAT_WIDTH]
        height = stats[label_id][cv2.CC_STAT_HEIGHT]
        area = stats[label_id][cv2.CC_STAT_AREA]

        # Check if region touches border
        touches_border = (x == 0 or y == 0 or
                          x + width >= w or
                          y + height >= h)

        if touches_border:
            continue

        if area < min_area:
            continue

        valid_regions.append((label_id, area))

    print(f"After filtering: {len(valid_regions)} valid rooms (border regions removed)")
    return valid_regions


# =============================================================================
# 5. Extract and approximate contours
# =============================================================================

def extract_room_polygons(labels, valid_regions, img_shape):
    """
    Extract and approximate contours for each valid room region.
    
    Returns list of dicts with room_id, polygon, and area.
    """
    rooms = []
    
    for room_id, (label_id, area) in enumerate(valid_regions):
        # Create mask for this region
        region_mask = (labels == label_id).astype(np.uint8) * 255
        
        # Find contours
        contours, _ = cv2.findContours(
            region_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        
        if not contours:
            continue
        
        # Get the largest contour (should be the room boundary)
        contour = max(contours, key=cv2.contourArea)
        
        # Approximate contour to reduce vertices
        epsilon = POLY_EPSILON
        approx = cv2.approxPolyDP(contour, epsilon, closed=True)
        
        # Convert to polygon format (list of [x, y] coordinates)
        polygon = approx.reshape(-1, 2).tolist()
        
        # Ensure polygon has at least 3 vertices
        if len(polygon) < 3:
            continue
        
        rooms.append({
            "room_id": room_id,
            "polygon": polygon,
            "area_px": round(float(area), 1)
        })
    
    print(f"Extracted {len(rooms)} room polygons (epsilon={POLY_EPSILON}px)")
    return rooms


# =============================================================================
# 6. Save outputs
# =============================================================================

def save_outputs(rooms, save_dir=None):
    """Save room polygons to JSON file."""
    if save_dir is None:
        save_dir = os.path.join("data", "intermediate")
    
    json_path = os.path.join(save_dir, "room_polygons.json")
    utils.save_json(rooms, json_path)
    print(f"Saved -> {json_path}")


# =============================================================================
# 7. Visualization
# =============================================================================

def visualize(rooms, mask, save_dir=None):
    """Visualize detected rooms as colored polygons overlaid on wall mask."""
    if save_dir is None:
        save_dir = os.path.join("data", "intermediate")
    
    h, w = mask.shape[:2]
    
    # Create background from wall mask (dimmed)
    bg = cv2.cvtColor((mask * 0.35).astype(np.uint8), cv2.COLOR_GRAY2BGR)
    
    # Draw walls in white for contrast
    wall_overlay = bg.copy()
    wall_overlay[mask > 0] = (200, 200, 200)
    cv2.addWeighted(wall_overlay, 0.5, bg, 0.5, 0, bg)
    
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
    for room in rooms:
        polygon = room["polygon"]
        color = colors[room["room_id"] % len(colors)]
        
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
    print("  Stage 4: Room Detection via Flood Fill")
    print("=" * 55)
    print()
    
    # 1. Load binary wall mask
    mask = load_wall_mask()
    
    # 2. Preprocess (invert + light closing)
    processed = preprocess_mask(mask)
    
    # 3. Find connected components
    num_labels, labels, stats, centroids = find_connected_regions(processed)
    
    # 4. Filter to valid rooms
    valid_regions = filter_regions(num_labels, stats, mask.shape)
    
    # 5. Extract polygons
    rooms = extract_room_polygons(labels, valid_regions, mask.shape)
    
    # 6. Save outputs
    save_outputs(rooms)
    
    # 7. Visualize
    visualize(rooms, mask)
    
    # Summary
    print()
    print(f"Detected {len(rooms)} rooms")
    if rooms:
        areas = [r["area_px"] for r in rooms]
        print(f"Area range: {min(areas):.0f} - {max(areas):.0f} px²")
    
    print("\nStage 4 completed successfully!")


if __name__ == "__main__":
    main()
