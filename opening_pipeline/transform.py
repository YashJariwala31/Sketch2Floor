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


def _segments_from_wall_polygons(wall_polygons):
    segments = []
    sid = 0
    for wall in wall_polygons:
        verts = wall.get('vertices')
        if not isinstance(verts, list) or len(verts) < 2:
            continue
        pts = [np.array(v, dtype=float) for v in verts]
        for i in range(len(pts)):
            p1 = pts[i]
            p2 = pts[(i + 1) % len(pts)]
            if float(np.linalg.norm(p2 - p1)) < 1e-6:
                continue
            segments.append({
                'id': sid,
                'wall_id': int(wall.get('wall_id', -1)),
                'p1': p1,
                'p2': p2,
            })
            sid += 1
    return segments


def _segment_intersection(p1, p2, p3, p4):
    x1, y1 = float(p1[0]), float(p1[1])
    x2, y2 = float(p2[0]), float(p2[1])
    x3, y3 = float(p3[0]), float(p3[1])
    x4, y4 = float(p4[0]), float(p4[1])

    den = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if abs(den) < 1e-9:
        return None

    px = ((x1 * y2 - y1 * x2) * (x3 - x4) - (x1 - x2) * (x3 * y4 - y3 * x4)) / den
    py = ((x1 * y2 - y1 * x2) * (y3 - y4) - (y1 - y2) * (x3 * y4 - y3 * x4)) / den

    def _within(a, b, v):
        return min(a, b) - 1e-6 <= v <= max(a, b) + 1e-6

    if (
        _within(x1, x2, px) and _within(y1, y2, py) and
        _within(x3, x4, px) and _within(y3, y4, py)
    ):
        return np.array([px, py], dtype=float)
    return None


def _angle_between_segments(p1, p2, p3, p4):
    v1 = (np.array(p2, dtype=float) - np.array(p1, dtype=float))
    v2 = (np.array(p4, dtype=float) - np.array(p3, dtype=float))
    n1 = float(np.linalg.norm(v1))
    n2 = float(np.linalg.norm(v2))
    if n1 < 1e-9 or n2 < 1e-9:
        return None
    c = float(np.clip(np.dot(v1, v2) / (n1 * n2), -1.0, 1.0))
    ang = float(math.degrees(math.acos(c)))
    ang = min(ang, 180.0 - ang)
    return ang


def _hinge_candidates_from_wall_segments(wall_segments, *, angle_min=70.0, angle_max=110.0):
    candidates = []
    for i in range(len(wall_segments)):
        s1 = wall_segments[i]
        for j in range(i + 1, len(wall_segments)):
            s2 = wall_segments[j]
            inter = _segment_intersection(s1['p1'], s1['p2'], s2['p1'], s2['p2'])
            if inter is None:
                continue
            ang = _angle_between_segments(s1['p1'], s1['p2'], s2['p1'], s2['p2'])
            if ang is None:
                continue
            if angle_min <= ang <= angle_max:
                candidates.append({
                    'pt': inter,
                    'segments': (s1['id'], s2['id']),
                })
    return candidates


def _extract_door_contours(door_mask, *, close_kernel=5, area_threshold=150.0):
    if door_mask is None:
        return []
    if door_mask.ndim == 3:
        door_mask = cv2.cvtColor(door_mask, cv2.COLOR_BGR2GRAY)
    _, bw = cv2.threshold(door_mask, 127, 255, cv2.THRESH_BINARY)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (close_kernel, close_kernel))
    bw = cv2.morphologyEx(bw, cv2.MORPH_CLOSE, kernel, iterations=1)
    contours, _ = cv2.findContours(bw, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    out = []
    for cnt in contours:
        area = float(cv2.contourArea(cnt))
        if area >= float(area_threshold):
            out.append(cnt)
    return out


def _closest_hinge_candidate_to_contour(contour, hinge_candidates):
    best = None
    best_dist = float('inf')
    for cand in hinge_candidates:
        pt = cand['pt']
        d = abs(float(cv2.pointPolygonTest(contour, (float(pt[0]), float(pt[1])), True)))
        if d < best_dist:
            best_dist = d
            best = cand
    return best, best_dist


def _contour_tip_farthest_from_hinge(contour, hinge_pt):
    pts = contour.reshape(-1, 2).astype(float)
    d = np.linalg.norm(pts - hinge_pt.reshape(1, 2), axis=1)
    idx = int(np.argmax(d))
    return pts[idx]


def _connected_segments_to_point(wall_segments, pt, *, eps=2.0):
    out = []
    for s in wall_segments:
        projx, projy, dist = point_to_segment_projection(
            float(pt[0]), float(pt[1]),
            float(s['p1'][0]), float(s['p1'][1]),
            float(s['p2'][0]), float(s['p2'][1]),
        )
        if dist <= eps:
            out.append(s)
    return out


def _hinge_candidates_on_segment(hinge_candidates, segment, *, eps=2.0):
    p1 = segment['p1']
    p2 = segment['p2']
    out = []
    for cand in hinge_candidates:
        pt = cand['pt']
        _, _, dist = point_to_segment_projection(
            float(pt[0]), float(pt[1]),
            float(p1[0]), float(p1[1]), float(p2[0]), float(p2[1]),
        )
        if dist <= eps:
            out.append(cand)
    return out


def _segment_param_t(p1, p2, pt):
    v = p2 - p1
    denom = float(np.dot(v, v))
    if denom < 1e-9:
        return 0.0
    return float(np.dot(pt - p1, v) / denom)


def reconstruct_doors_3point(template, TEMPLATE_HEIGHT, *, door_mask, wall_polygons, debug_image=None):
    wall_segments = _segments_from_wall_polygons(wall_polygons)
    hinge_candidates = _hinge_candidates_from_wall_segments(wall_segments)
    contours = _extract_door_contours(door_mask)

    placed = []
    debug = debug_image.copy() if debug_image is not None else None

    for did, cnt in enumerate(contours):
        cand, _ = _closest_hinge_candidate_to_contour(cnt, hinge_candidates)
        if cand is None:
            continue
        A = cand['pt']

        C = _contour_tip_farthest_from_hinge(cnt, A)

        connected = _connected_segments_to_point(wall_segments, A)
        if not connected:
            continue

        AC = C - A
        acn = float(np.linalg.norm(AC))
        if acn < 1e-6:
            continue
        ACn = AC / acn

        best_seg = None
        best_align = -1.0
        for s in connected:
            v = s['p2'] - s['p1']
            vn = float(np.linalg.norm(v))
            if vn < 1e-6:
                continue
            v = v / vn
            align = float(abs(np.dot(v, ACn)))
            if align > best_align:
                best_align = align
                best_seg = s
        if best_seg is None:
            continue

        p1 = best_seg['p1']
        p2 = best_seg['p2']
        v = p2 - p1
        vn = float(np.linalg.norm(v))
        if vn < 1e-6:
            continue
        v = v / vn
        if float(np.dot(v, ACn)) < 0:
            v = -v

        on_seg = _hinge_candidates_on_segment(hinge_candidates, best_seg)
        if len(on_seg) < 2:
            continue

        tA = _segment_param_t(p1, p2, A)
        next_pts = []
        for c2 in on_seg:
            pt2 = c2['pt']
            t2 = _segment_param_t(p1, p2, pt2)
            if t2 > tA + 1e-3:
                next_pts.append((t2, pt2))
        if not next_pts:
            for c2 in on_seg:
                pt2 = c2['pt']
                t2 = _segment_param_t(p1, p2, pt2)
                if t2 < tA - 1e-3:
                    next_pts.append((t2, pt2))
            if not next_pts:
                continue
            next_pts.sort(key=lambda x: x[0], reverse=True)
        else:
            next_pts.sort(key=lambda x: x[0])

        B = next_pts[0][1]

        AB = B - A
        width = float(np.linalg.norm(AB))
        if width < 1e-6:
            continue

        rotation_deg = float(math.degrees(math.atan2(AB[1], AB[0])))

        cross = float(AB[0] * (C - A)[1] - AB[1] * (C - A)[0])
        swing_direction = 'ccw' if cross > 0 else 'cw'

        scale = float(width) / float(TEMPLATE_HEIGHT)
        leaf_local = np.array(template['leaf'], dtype=float)
        arc_local = np.array(template['arc'], dtype=float)
        if swing_direction == 'cw':
            leaf_local = leaf_local.copy()
            arc_local = arc_local.copy()
            leaf_local[:, 0] *= -1
            arc_local[:, 0] *= -1

        leaf_world = rotate_points(leaf_local * scale, rotation_deg) + A
        arc_world = rotate_points(arc_local * scale, rotation_deg) + A

        placed.append({
            'id': int(did),
            'hinge': [float(A[0]), float(A[1])],
            'leaf': leaf_world.tolist(),
            'arc': arc_world.tolist(),
            'strike': [float(B[0]), float(B[1])],
            'tip': [float(C[0]), float(C[1])],
            'rotation_deg': float(rotation_deg),
            'width': float(width),
            'swing_direction': str(swing_direction),
        })

        if debug is not None:
            cv2.circle(debug, (int(A[0]), int(A[1])), 6, (0, 255, 0), -1)
            cv2.circle(debug, (int(B[0]), int(B[1])), 6, (0, 255, 255), -1)
            cv2.circle(debug, (int(C[0]), int(C[1])), 6, (0, 0, 255), -1)
            cv2.line(debug, (int(A[0]), int(A[1])), (int(B[0]), int(B[1])), (0, 255, 255), 2)
            cv2.line(debug, (int(A[0]), int(A[1])), (int(C[0]), int(C[1])), (0, 0, 255), 2)

    if debug is not None:
        for cand in hinge_candidates:
            pt = cand['pt']
            cv2.circle(debug, (int(pt[0]), int(pt[1])), 2, (255, 0, 0), -1)

    return placed, debug


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
