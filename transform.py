"""Door template placement and transformations.

Implements utilities to scale/rotate/translate a door template (leaf + swing arc)
onto detected door bounding boxes. Supports wall snapping (hinge projection onto
nearest wall), true wall-angle rotation, and open-direction flipping.
"""

import os
import json
import cv2
import numpy as np
import math


def rotate_points(points, angle_degrees):
    angle = math.radians(angle_degrees)
    c = math.cos(angle)
    s = math.sin(angle)
    R = np.array([[c, -s], [s, c]])
    return points @ R.T


def point_to_segment_projection(px, py, x1, y1, x2, y2):
    vx, vy = x2 - x1, y2 - y1
    wx, wy = px - x1, py - y1
    denom = vx*vx + vy*vy
    if denom == 0:
        return x1, y1, 9999
    t = (wx*vx + wy*vy) / denom
    t = max(0, min(1, t))
    projx = x1 + t*vx
    projy = y1 + t*vy
    dist = ((px-projx)**2 + (py-projy)**2)**0.5
    return projx, projy, dist


def find_nearest_wall(cx, cy, walls):
    best = None
    best_dist = 1e9
    best_proj = None

    for w in walls:
        px, py, dist = point_to_segment_projection(
            cx, cy, w['x1'], w['y1'], w['x2'], w['y2']
        )
        if dist < best_dist:
            best_dist = dist
            best = w
            best_proj = (px, py)

    return best, best_proj, best_dist


def get_door_angle(rotated_box):
    pts = np.array(rotated_box)

    # find longest edge
    edges = []
    for i in range(4):
        p1 = pts[i]
        p2 = pts[(i + 1) % 4]
        length = np.linalg.norm(p2 - p1)
        edges.append((length, p1, p2))

    _, p1, p2 = max(edges, key=lambda x: x[0])

    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]

    angle = math.degrees(math.atan2(dy, dx))

    return angle


def get_hinge_from_rotated_box(rotated_box):
    import numpy as np
    pts = np.array(rotated_box)

    # find shortest edge (door thickness side)
    min_len = float('inf')
    hinge_point = None

    for i in range(4):
        p1 = pts[i]
        p2 = pts[(i+1)%4]
        length = np.linalg.norm(p2 - p1)

        if length < min_len:
            min_len = length
            hinge_point = (p1 + p2) / 2

    return hinge_point


def place_single_door(template, detected, TEMPLATE_HEIGHT):
    with open('transform_config.json') as f:
        config = json.load(f)

    # ------- BASE CENTER -------
    cx = float(detected['center_x'])
    cy = float(detected['center_y'])

    x = int(detected['x'])
    y = int(detected['y'])
    w = int(detected['width'])
    h = int(detected['height'])

    door_width = min(w, h)
    scale = float(door_width) / TEMPLATE_HEIGHT

    rotated_box = detected['rotated_box']

    hinge = get_hinge_from_rotated_box(rotated_box)

    pts = np.array(rotated_box, dtype=float)
    max_len = -1.0
    direction = np.array([1.0, 0.0], dtype=float)
    for i in range(4):
        p1 = pts[i]
        p2 = pts[(i + 1) % 4]
        v = p2 - p1
        length = float(np.linalg.norm(v))
        if length > max_len:
            max_len = length
            if length > 0:
                direction = v / length

    to_center = np.array([cx - hinge[0], cy - hinge[1]], dtype=float)
    if float(np.dot(direction, to_center)) < 0:
        direction = -direction

    strike = hinge + direction * float(door_width)

    direction_angle = math.degrees(math.atan2(direction[1], direction[0]))
    rotation_deg = direction_angle

    image_id = os.environ.get('IMAGE_ID')
    mask_path = f'predictions/{image_id}_door.png' if image_id else None
    mask = cv2.imread(mask_path, cv2.IMREAD_GRAYSCALE) if mask_path else None

    if mask is not None:
        crop = mask[y:y + h, x:x + w]
        pts = np.column_stack(np.where(crop > 0))
        if pts.shape[0] > 0:
            pts[:, 0] += y
            pts[:, 1] += x
            distances = np.linalg.norm(pts - hinge[::-1], axis=1)
            tip_idx = int(np.argmax(distances))
            tip = np.array([pts[tip_idx][1], pts[tip_idx][0]], dtype=float)

            AB = strike - hinge
            AC = tip - hinge
            cross = AB[0] * AC[1] - AB[1] * AC[0]
            if cross < 0:
                direction = -direction
                strike = hinge + direction * float(door_width)
                direction_angle = math.degrees(math.atan2(direction[1], direction[0]))
                rotation_deg = direction_angle

    # ------- TRANSFORM -------
    leaf_local = np.array(template['leaf'], dtype=float) * scale
    arc_local  = np.array(template['arc'],  dtype=float) * scale

    leaf_world = rotate_points(leaf_local, rotation_deg) + hinge
    arc_world  = rotate_points(arc_local,  rotation_deg) + hinge

    return {
        'id':   detected['id'],
        'hinge': hinge.tolist(),
        'leaf':  leaf_world.tolist(),
        'arc':   arc_world.tolist()
    }
