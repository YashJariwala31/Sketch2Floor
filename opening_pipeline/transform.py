"""Door template placement and transformations.

This module turns detected door geometry into world-space hinge, leaf, and arc
coordinates. The placement logic prefers inferred wall openings reconstructed
from gaps between aligned wall segments, then falls back to direct wall-segment
projection, and finally to a conservative legacy bbox heuristic.
"""

import json
import logging
import math
from pathlib import Path

import cv2
import numpy as np


BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent

with open(BASE_DIR / "transform_config.json", "r", encoding="utf-8") as _config_file:
    TRANSFORM_CONFIG = json.load(_config_file)

DEFAULT_WALLS_PATH = TRANSFORM_CONFIG.get("paths", {}).get("walls")
DEFAULT_WALL_SNAP_DISTANCE = float(
    TRANSFORM_CONFIG.get("wall_snap", {}).get("max_distance", 15.0)
)
LEGACY_HINGE_RULES = TRANSFORM_CONFIG.get("hinge_strategy", {}).get("bbox_rules", {})

LOGGER = logging.getLogger(__name__)


def _normalize_vector(vector, *, name="vector", min_norm=1e-9):
    """Return a unit-length numpy vector or None for invalid / degenerate input."""
    try:
        array = np.asarray(vector, dtype=float).reshape(-1)
    except (TypeError, ValueError) as exc:
        LOGGER.warning("Failed to coerce %s for normalization: %s", name, exc)
        return None

    if array.size != 2:
        LOGGER.warning("Expected %s to contain exactly 2 values, got %s", name, array.size)
        return None

    if not np.isfinite(array).all():
        LOGGER.warning("Refusing to normalize %s with non-finite values: %s", name, array.tolist())
        return None

    norm = float(np.linalg.norm(array))
    if norm < float(min_norm):
        LOGGER.debug("Skipping normalization for near-zero %s: %s", name, array.tolist())
        return None

    return array / norm


def rotate_points(points, angle_degrees):
    angle = math.radians(angle_degrees)
    cosine = math.cos(angle)
    sine = math.sin(angle)
    rotation = np.array([[cosine, -sine], [sine, cosine]])
    return points @ rotation.T


def _segments_from_wall_polygons(wall_polygons):
    segments = []
    segment_id = 0
    for wall in wall_polygons:
        vertices = wall.get("vertices")
        if not isinstance(vertices, list) or len(vertices) < 2:
            continue
        points = [np.array(vertex, dtype=float) for vertex in vertices]
        for index in range(len(points)):
            point_1 = points[index]
            point_2 = points[(index + 1) % len(points)]
            if float(np.linalg.norm(point_2 - point_1)) < 1e-6:
                continue
            segments.append(
                {
                    "id": segment_id,
                    "wall_id": int(wall.get("wall_id", -1)),
                    "p1": point_1,
                    "p2": point_2,
                }
            )
            segment_id += 1
    return segments


def _segment_intersection(point_1, point_2, point_3, point_4):
    x1, y1 = float(point_1[0]), float(point_1[1])
    x2, y2 = float(point_2[0]), float(point_2[1])
    x3, y3 = float(point_3[0]), float(point_3[1])
    x4, y4 = float(point_4[0]), float(point_4[1])

    denominator = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if abs(denominator) < 1e-9:
        return None

    px = ((x1 * y2 - y1 * x2) * (x3 - x4) - (x1 - x2) * (x3 * y4 - y3 * x4)) / denominator
    py = ((x1 * y2 - y1 * x2) * (y3 - y4) - (y1 - y2) * (x3 * y4 - y3 * x4)) / denominator

    def _within(start, end, value):
        return min(start, end) - 1e-6 <= value <= max(start, end) + 1e-6

    if (
        _within(x1, x2, px)
        and _within(y1, y2, py)
        and _within(x3, x4, px)
        and _within(y3, y4, py)
    ):
        return np.array([px, py], dtype=float)
    return None


def _angle_between_segments(point_1, point_2, point_3, point_4):
    vector_1 = np.array(point_2, dtype=float) - np.array(point_1, dtype=float)
    vector_2 = np.array(point_4, dtype=float) - np.array(point_3, dtype=float)
    norm_1 = float(np.linalg.norm(vector_1))
    norm_2 = float(np.linalg.norm(vector_2))
    if norm_1 < 1e-9 or norm_2 < 1e-9:
        return None
    cosine = float(np.clip(np.dot(vector_1, vector_2) / (norm_1 * norm_2), -1.0, 1.0))
    angle = float(math.degrees(math.acos(cosine)))
    return min(angle, 180.0 - angle)


def _hinge_candidates_from_wall_segments(wall_segments, *, angle_min=70.0, angle_max=110.0):
    candidates = []
    for first_index in range(len(wall_segments)):
        first_segment = wall_segments[first_index]
        for second_index in range(first_index + 1, len(wall_segments)):
            second_segment = wall_segments[second_index]
            intersection = _segment_intersection(
                first_segment["p1"],
                first_segment["p2"],
                second_segment["p1"],
                second_segment["p2"],
            )
            if intersection is None:
                continue

            angle = _angle_between_segments(
                first_segment["p1"],
                first_segment["p2"],
                second_segment["p1"],
                second_segment["p2"],
            )
            if angle is None or not (angle_min <= angle <= angle_max):
                continue

            candidates.append(
                {
                    "pt": intersection,
                    "segments": (first_segment["id"], second_segment["id"]),
                }
            )
    return candidates


def _extract_door_contours(door_mask, *, close_kernel=5, area_threshold=150.0):
    if door_mask is None:
        return []
    if door_mask.ndim == 3:
        door_mask = cv2.cvtColor(door_mask, cv2.COLOR_BGR2GRAY)

    _, binary = cv2.threshold(door_mask, 127, 255, cv2.THRESH_BINARY)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (close_kernel, close_kernel))
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel, iterations=1)
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)

    output = []
    for contour in contours:
        area = float(cv2.contourArea(contour))
        if area >= float(area_threshold):
            output.append(contour)
    return output


def _closest_hinge_candidate_to_contour(contour, hinge_candidates):
    best_candidate = None
    best_distance = float("inf")
    for candidate in hinge_candidates:
        point = candidate["pt"]
        distance = abs(float(cv2.pointPolygonTest(contour, (float(point[0]), float(point[1])), True)))
        if distance < best_distance:
            best_distance = distance
            best_candidate = candidate
    return best_candidate, best_distance


def _contour_tip_farthest_from_hinge(contour, hinge_point):
    points = contour.reshape(-1, 2).astype(float)
    distances = np.linalg.norm(points - hinge_point.reshape(1, 2), axis=1)
    return points[int(np.argmax(distances))]


def point_to_segment_projection(px, py, x1, y1, x2, y2):
    vector_x, vector_y = x2 - x1, y2 - y1
    offset_x, offset_y = px - x1, py - y1
    denominator = vector_x * vector_x + vector_y * vector_y
    if denominator == 0:
        return x1, y1, 9999
    t_value = (offset_x * vector_x + offset_y * vector_y) / denominator
    t_value = max(0, min(1, t_value))
    proj_x = x1 + t_value * vector_x
    proj_y = y1 + t_value * vector_y
    distance = ((px - proj_x) ** 2 + (py - proj_y) ** 2) ** 0.5
    return proj_x, proj_y, distance


def _connected_segments_to_point(wall_segments, point, *, eps=2.0):
    output = []
    for segment in wall_segments:
        _, _, distance = point_to_segment_projection(
            float(point[0]),
            float(point[1]),
            float(segment["p1"][0]),
            float(segment["p1"][1]),
            float(segment["p2"][0]),
            float(segment["p2"][1]),
        )
        if distance <= eps:
            output.append(segment)
    return output


def _hinge_candidates_on_segment(hinge_candidates, segment, *, eps=2.0):
    output = []
    point_1 = segment["p1"]
    point_2 = segment["p2"]
    for candidate in hinge_candidates:
        point = candidate["pt"]
        _, _, distance = point_to_segment_projection(
            float(point[0]),
            float(point[1]),
            float(point_1[0]),
            float(point_1[1]),
            float(point_2[0]),
            float(point_2[1]),
        )
        if distance <= eps:
            output.append(candidate)
    return output


def _segment_param_t(point_1, point_2, point):
    vector = point_2 - point_1
    denominator = float(np.dot(vector, vector))
    if denominator < 1e-9:
        return 0.0
    return float(np.dot(point - point_1, vector) / denominator)


def reconstruct_doors_3point(template, TEMPLATE_HEIGHT, *, door_mask, wall_polygons, debug_image=None):
    wall_segments = _segments_from_wall_polygons(wall_polygons)
    hinge_candidates = _hinge_candidates_from_wall_segments(wall_segments)
    contours = _extract_door_contours(door_mask)

    placed = []
    debug = debug_image.copy() if debug_image is not None else None

    for door_id, contour in enumerate(contours):
        candidate, _ = _closest_hinge_candidate_to_contour(contour, hinge_candidates)
        if candidate is None:
            continue
        hinge_point = candidate["pt"]
        tip_point = _contour_tip_farthest_from_hinge(contour, hinge_point)

        connected_segments = _connected_segments_to_point(wall_segments, hinge_point)
        if not connected_segments:
            continue

        hinge_to_tip = tip_point - hinge_point
        tip_norm = float(np.linalg.norm(hinge_to_tip))
        if tip_norm < 1e-6:
            continue
        hinge_to_tip_unit = hinge_to_tip / tip_norm

        best_segment = None
        best_alignment = -1.0
        for segment in connected_segments:
            vector = segment["p2"] - segment["p1"]
            vector_norm = float(np.linalg.norm(vector))
            if vector_norm < 1e-6:
                continue
            vector = vector / vector_norm
            alignment = float(abs(np.dot(vector, hinge_to_tip_unit)))
            if alignment > best_alignment:
                best_alignment = alignment
                best_segment = segment
        if best_segment is None:
            continue

        point_1 = best_segment["p1"]
        point_2 = best_segment["p2"]
        segment_unit = _normalize_vector(point_2 - point_1, name="reconstruct_wall_segment")
        if segment_unit is None:
            continue
        if float(np.dot(segment_unit, hinge_to_tip_unit)) < 0:
            segment_unit = -segment_unit

        opening_candidates = _hinge_candidates_on_segment(hinge_candidates, best_segment)
        if len(opening_candidates) < 2:
            continue

        hinge_t = _segment_param_t(point_1, point_2, hinge_point)
        next_points = []
        for other in opening_candidates:
            point = other["pt"]
            other_t = _segment_param_t(point_1, point_2, point)
            if other_t > hinge_t + 1e-3:
                next_points.append((other_t, point))
        if not next_points:
            for other in opening_candidates:
                point = other["pt"]
                other_t = _segment_param_t(point_1, point_2, point)
                if other_t < hinge_t - 1e-3:
                    next_points.append((other_t, point))
            if not next_points:
                continue
            next_points.sort(key=lambda item: item[0], reverse=True)
        else:
            next_points.sort(key=lambda item: item[0])

        strike_point = next_points[0][1]
        opening_width = float(np.linalg.norm(strike_point - hinge_point))
        if opening_width < 1e-6:
            continue

        rotation_deg = float(math.degrees(math.atan2(strike_point[1] - hinge_point[1], strike_point[0] - hinge_point[0])))
        cross_value = float(
            (strike_point[0] - hinge_point[0]) * (tip_point[1] - hinge_point[1])
            - (strike_point[1] - hinge_point[1]) * (tip_point[0] - hinge_point[0])
        )
        swing_direction = "ccw" if cross_value > 0 else "cw"

        scale = float(opening_width) / float(TEMPLATE_HEIGHT)
        leaf_local = np.array(template["leaf"], dtype=float)
        arc_local = np.array(template["arc"], dtype=float)
        if swing_direction == "cw":
            leaf_local = leaf_local.copy()
            arc_local = arc_local.copy()
            leaf_local[:, 0] *= -1
            arc_local[:, 0] *= -1

        leaf_world = rotate_points(leaf_local * scale, rotation_deg) + hinge_point
        arc_world = rotate_points(arc_local * scale, rotation_deg) + hinge_point

        placed.append(
            {
                "id": int(door_id),
                "hinge": [float(hinge_point[0]), float(hinge_point[1])],
                "leaf": leaf_world.tolist(),
                "arc": arc_world.tolist(),
                "strike": [float(strike_point[0]), float(strike_point[1])],
                "tip": [float(tip_point[0]), float(tip_point[1])],
                "rotation_deg": rotation_deg,
                "width": opening_width,
                "swing_direction": swing_direction,
            }
        )

        if debug is not None:
            cv2.circle(debug, (int(hinge_point[0]), int(hinge_point[1])), 6, (0, 255, 0), -1)
            cv2.circle(debug, (int(strike_point[0]), int(strike_point[1])), 6, (0, 255, 255), -1)
            cv2.circle(debug, (int(tip_point[0]), int(tip_point[1])), 6, (0, 0, 255), -1)
            cv2.line(
                debug,
                (int(hinge_point[0]), int(hinge_point[1])),
                (int(strike_point[0]), int(strike_point[1])),
                (0, 255, 255),
                2,
            )
            cv2.line(
                debug,
                (int(hinge_point[0]), int(hinge_point[1])),
                (int(tip_point[0]), int(tip_point[1])),
                (0, 0, 255),
                2,
            )

    if debug is not None:
        for candidate in hinge_candidates:
            point = candidate["pt"]
            cv2.circle(debug, (int(point[0]), int(point[1])), 2, (255, 0, 0), -1)

    return placed, debug


def find_nearest_wall(cx, cy, walls):
    best_wall = None
    best_distance = 1e9
    best_projection = None

    for wall in walls:
        projection_x, projection_y, distance = point_to_segment_projection(
            cx,
            cy,
            wall["x1"],
            wall["y1"],
            wall["x2"],
            wall["y2"],
        )
        if distance < best_distance:
            best_distance = distance
            best_wall = wall
            best_projection = (projection_x, projection_y)

    return best_wall, best_projection, best_distance


def get_door_angle(rotated_box):
    points = np.array(rotated_box)
    edges = []
    for index in range(4):
        point_1 = points[index]
        point_2 = points[(index + 1) % 4]
        length = np.linalg.norm(point_2 - point_1)
        edges.append((length, point_1, point_2))

    _, point_1, point_2 = max(edges, key=lambda item: item[0])
    delta_x = point_2[0] - point_1[0]
    delta_y = point_2[1] - point_1[1]
    return math.degrees(math.atan2(delta_y, delta_x))


def get_hinge_from_rotated_box(rotated_box):
    points = np.array(rotated_box)
    min_length = float("inf")
    hinge_point = None

    for index in range(4):
        point_1 = points[index]
        point_2 = points[(index + 1) % 4]
        length = np.linalg.norm(point_2 - point_1)
        if length < min_length:
            min_length = length
            hinge_point = (point_1 + point_2) / 2

    return hinge_point


def _load_default_walls():
    if not DEFAULT_WALLS_PATH:
        return None

    walls_path = Path(DEFAULT_WALLS_PATH)
    if not walls_path.is_absolute():
        walls_path = ROOT_DIR / walls_path
    if not walls_path.exists():
        return None

    with open(walls_path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _segment_orientation(p1, p2, tol=1e-3):
    dx = float(p2[0] - p1[0])
    dy = float(p2[1] - p1[1])
    if abs(dx) <= tol:
        return "vertical"
    if abs(dy) <= tol:
        return "horizontal"
    return "angled"


def _normalize_wall_segments(walls):
    wall_polygons = []
    wall_segments = []

    if not isinstance(walls, list):
        return wall_polygons, wall_segments

    if walls and isinstance(walls[0], dict) and "vertices" in walls[0]:
        wall_polygons = walls
        raw_segments = _segments_from_wall_polygons(walls)
    else:
        raw_segments = []
        for index, segment in enumerate(walls):
            if not isinstance(segment, dict):
                continue
            if not {"x1", "y1", "x2", "y2"} <= set(segment.keys()):
                continue
            raw_segments.append(
                {
                    "id": int(segment.get("id", index)),
                    "wall_id": int(segment.get("wall_id", -1)),
                    "p1": np.array([float(segment["x1"]), float(segment["y1"])], dtype=float),
                    "p2": np.array([float(segment["x2"]), float(segment["y2"])], dtype=float),
                }
            )

    for index, segment in enumerate(raw_segments):
        point_1 = np.array(segment["p1"], dtype=float)
        point_2 = np.array(segment["p2"], dtype=float)
        length = float(np.linalg.norm(point_2 - point_1))
        if length < 1e-6:
            continue

        orientation = _segment_orientation(point_1, point_2)
        if orientation == "horizontal":
            axis = float((point_1[1] + point_2[1]) / 2.0)
            span_start, span_end = sorted((float(point_1[0]), float(point_2[0])))
        elif orientation == "vertical":
            axis = float((point_1[0] + point_2[0]) / 2.0)
            span_start, span_end = sorted((float(point_1[1]), float(point_2[1])))
        else:
            axis = None
            span_start = span_end = None

        wall_segments.append(
            {
                "id": int(segment.get("id", index)),
                "wall_id": int(segment.get("wall_id", -1)),
                "p1": point_1,
                "p2": point_2,
                "length": length,
                "orientation": orientation,
                "axis": axis,
                "span_start": span_start,
                "span_end": span_end,
            }
        )

    return wall_polygons, wall_segments


def _estimate_symbol_axis(detected):
    rotated_box = detected.get("rotated_box")
    if isinstance(rotated_box, list) and len(rotated_box) >= 2:
        points = np.array(rotated_box, dtype=float)
        best_vector = None
        best_length = -1.0
        for index in range(len(points)):
            point_1 = points[index]
            point_2 = points[(index + 1) % len(points)]
            vector = point_2 - point_1
            length = float(np.linalg.norm(vector))
            if length > best_length:
                best_length = length
                best_vector = vector
        if best_vector is not None:
            normalized = _normalize_vector(best_vector, name="symbol_axis")
            if normalized is not None:
                return normalized

    width = float(detected.get("width", 0.0))
    height = float(detected.get("height", 0.0))
    if width >= height:
        return np.array([1.0, 0.0], dtype=float)
    return np.array([0.0, 1.0], dtype=float)


def _build_polygon_contours(polygons, key):
    contours = []
    for polygon in polygons or []:
        points = polygon.get(key)
        if not isinstance(points, list) or len(points) < 3:
            continue
        contours.append(np.array(points, dtype=np.float32).reshape(-1, 1, 2))
    return contours


def _find_best_room(door_x, door_y, room_polygons):
    if not room_polygons:
        return None

    best_room = None
    best_distance = float("inf")

    for room in room_polygons:
        polygon = room.get("polygon")
        if not polygon or len(polygon) < 3:
            continue

        contour = np.array(polygon, dtype=np.float32).reshape(-1, 1, 2)
        distance = float(cv2.pointPolygonTest(contour, (float(door_x), float(door_y)), True))
        if distance >= 0:
            best_room = contour
            best_distance = 0.0
            break
        if abs(distance) < best_distance:
            best_distance = abs(distance)
            best_room = contour

    if best_room is None:
        return None

    moments = cv2.moments(best_room)
    if moments["m00"] < 1e-6:
        return None

    center = (
        float(moments["m10"] / moments["m00"]),
        float(moments["m01"] / moments["m00"]),
    )
    return {
        "contour": best_room,
        "center": center,
    }


def _find_door_room_center(door_x, door_y, room_polygons):
    room = _find_best_room(door_x, door_y, room_polygons)
    if room is None:
        return None
    return room["center"]


def _cluster_segments_by_axis(segments, axis_tol):
    groups = []
    for segment in sorted(segments, key=lambda item: item["axis"]):
        matched = None
        for group in groups:
            if abs(segment["axis"] - group["axis"]) <= axis_tol:
                matched = group
                break

        if matched is None:
            groups.append(
                {
                    "axis": float(segment["axis"]),
                    "axis_values": [float(segment["axis"])],
                    "segments": [segment],
                }
            )
        else:
            matched["axis_values"].append(float(segment["axis"]))
            matched["segments"].append(segment)
            matched["axis"] = float(sum(matched["axis_values"]) / len(matched["axis_values"]))
    return groups


def _merge_spans(spans, join_tol=2.0):
    merged = []
    for start, end, segment in spans:
        if not merged:
            merged.append([start, end, [segment]])
            continue

        previous = merged[-1]
        if start <= previous[1] + join_tol:
            previous[1] = max(previous[1], end)
            previous[2].append(segment)
        else:
            merged.append([start, end, [segment]])
    return merged


def _infer_wall_openings(
    wall_segments,
    *,
    min_segment_length=40.0,
    axis_tol=8.0,
    gap_min=40.0,
    gap_max=420.0,
    gap_tol=24.0,
    axis_merge_tol=40.0,
):
    raw_candidates = []

    for orientation in ("horizontal", "vertical"):
        oriented_segments = [
            segment
            for segment in wall_segments
            if segment["orientation"] == orientation and segment["length"] >= min_segment_length
        ]
        if not oriented_segments:
            continue

        for group in _cluster_segments_by_axis(oriented_segments, axis_tol):
            spans = sorted(
                (
                    float(segment["span_start"]),
                    float(segment["span_end"]),
                    segment,
                )
                for segment in group["segments"]
            )
            merged_spans = _merge_spans(spans)
            for previous, current in zip(merged_spans, merged_spans[1:]):
                gap_size = float(current[0] - previous[1])
                if gap_size < gap_min or gap_size > gap_max:
                    continue
                raw_candidates.append(
                    {
                        "orientation": orientation,
                        "axis": float(group["axis"]),
                        "gap_start": float(previous[1]),
                        "gap_end": float(current[0]),
                        "source_segments": previous[2] + current[2],
                    }
                )

    merged_candidates = []
    for candidate in sorted(raw_candidates, key=lambda item: (item["orientation"], item["gap_start"], item["axis"])):
        matched = None
        for merged in merged_candidates:
            if merged["orientation"] != candidate["orientation"]:
                continue
            if abs(candidate["gap_start"] - merged["gap_start"]) > gap_tol:
                continue
            if abs(candidate["gap_end"] - merged["gap_end"]) > gap_tol:
                continue
            if abs(candidate["axis"] - merged["axis"]) > axis_merge_tol:
                continue
            matched = merged
            break

        if matched is None:
            merged_candidates.append(
                {
                    "orientation": candidate["orientation"],
                    "axis": float(candidate["axis"]),
                    "gap_start": float(candidate["gap_start"]),
                    "gap_end": float(candidate["gap_end"]),
                    "axes": [candidate["axis"]],
                    "gap_starts": [candidate["gap_start"]],
                    "gap_ends": [candidate["gap_end"]],
                    "source_segments": list(candidate["source_segments"]),
                }
            )
        else:
            matched["axes"].append(candidate["axis"])
            matched["gap_starts"].append(candidate["gap_start"])
            matched["gap_ends"].append(candidate["gap_end"])
            matched["source_segments"].extend(candidate["source_segments"])
            matched["axis"] = float(sum(matched["axes"]) / len(matched["axes"]))
            matched["gap_start"] = float(sum(matched["gap_starts"]) / len(matched["gap_starts"]))
            matched["gap_end"] = float(sum(matched["gap_ends"]) / len(matched["gap_ends"]))

    openings = []
    for opening_id, merged in enumerate(merged_candidates):
        axis_center = float(sum(merged["axes"]) / len(merged["axes"]))
        gap_start = float(sum(merged["gap_starts"]) / len(merged["gap_starts"]))
        gap_end = float(sum(merged["gap_ends"]) / len(merged["gap_ends"]))
        width = max(0.0, gap_end - gap_start)
        if width <= 1e-6:
            continue

        if merged["orientation"] == "vertical":
            start_point = np.array([axis_center, gap_start], dtype=float)
            end_point = np.array([axis_center, gap_end], dtype=float)
            normal = np.array([1.0, 0.0], dtype=float)
        else:
            start_point = np.array([gap_start, axis_center], dtype=float)
            end_point = np.array([gap_end, axis_center], dtype=float)
            normal = np.array([0.0, 1.0], dtype=float)

        openings.append(
            {
                "id": opening_id,
                "orientation": merged["orientation"],
                "axis": axis_center,
                "gap_start": gap_start,
                "gap_end": gap_end,
                "width": width,
                "start_point": start_point,
                "end_point": end_point,
                "normal": normal,
                "wall_thickness": float(max(merged["axes"]) - min(merged["axes"])) if len(merged["axes"]) > 1 else 0.0,
                "source_segments": merged["source_segments"],
            }
        )

    return openings


def _distance_to_interval(value, start, end):
    if value < start:
        return float(start - value)
    if value > end:
        return float(value - end)
    return 0.0


def _select_opening_for_door(detected, openings):
    if not openings:
        return None

    center_x = float(detected.get("center_x", 0.0))
    center_y = float(detected.get("center_y", 0.0))
    width = float(detected.get("width", 0.0))
    height = float(detected.get("height", 0.0))
    symbol_axis = _estimate_symbol_axis(detected)
    symbol_extent = max(24.0, min(width, height))

    best_opening = None
    best_score = float("inf")

    for opening in openings:
        if opening["orientation"] == "vertical":
            axis_distance = abs(center_x - opening["axis"])
            span_distance = _distance_to_interval(center_y, opening["gap_start"], opening["gap_end"])
            expected_axis = np.array([1.0, 0.0], dtype=float)
        else:
            axis_distance = abs(center_y - opening["axis"])
            span_distance = _distance_to_interval(center_x, opening["gap_start"], opening["gap_end"])
            expected_axis = np.array([0.0, 1.0], dtype=float)

        axis_alignment = abs(float(np.dot(symbol_axis, expected_axis)))
        orientation_penalty = (1.0 - axis_alignment) * 120.0
        width_penalty = abs(opening["width"] - symbol_extent) * 0.15
        score = axis_distance * 2.5 + span_distance * 4.0 + orientation_penalty + width_penalty

        if score < best_score:
            best_score = score
            best_opening = opening

    return best_opening


def _legacy_hinge_hint(detected, orientation):
    rule = LEGACY_HINGE_RULES.get(orientation)
    if not rule:
        return np.array(
            [
                float(detected.get("center_x", 0.0)),
                float(detected.get("center_y", 0.0)),
            ],
            dtype=float,
        )

    return np.array(
        [
            float(detected.get(rule["x"], detected.get("center_x", 0.0))),
            float(detected.get(rule["y"], detected.get("center_y", 0.0))),
        ],
        dtype=float,
    )


def _choose_inward_normal(anchor_point, tangent, *, room=None, image_width=None, image_height=None, fallback_target=None):
    tangent_unit = _normalize_vector(tangent, name="wall_tangent")
    if tangent_unit is None:
        return np.array([0.0, 1.0], dtype=float)

    normal = np.array([-tangent_unit[1], tangent_unit[0]], dtype=float)

    if room is not None:
        target = np.array(room["center"], dtype=float)
    elif image_width is not None and image_height is not None:
        target = np.array([float(image_width) / 2.0, float(image_height) / 2.0], dtype=float)
    elif fallback_target is not None:
        target = np.array(fallback_target, dtype=float)
    else:
        return normal

    if float(np.dot(normal, target - anchor_point)) < 0:
        normal = -normal
    return normal


def _transform_template_points(points, scale, hinge, closed_direction, open_direction):
    basis = np.column_stack((closed_direction, open_direction))
    return (np.array(points, dtype=float) * scale) @ basis.T + hinge


def _build_door_geometry(template, template_height, hinge, strike, open_direction, detected_id, *, anchor_mode, wall_orientation):
    door_width = float(np.linalg.norm(strike - hinge))
    if door_width < 1e-6:
        return None

    closed_direction = _normalize_vector(strike - hinge, name="closed_direction")
    open_direction = _normalize_vector(open_direction, name="open_direction")
    if closed_direction is None or open_direction is None:
        return None

    scale = float(door_width) / float(template_height)
    leaf_world = _transform_template_points(template["leaf"], scale, hinge, closed_direction, open_direction)
    arc_world = _transform_template_points(template["arc"], scale, hinge, closed_direction, open_direction)

    all_points = np.vstack((leaf_world, arc_world))
    bbox_min = all_points.min(axis=0)
    bbox_max = all_points.max(axis=0)

    return {
        "id": int(detected_id),
        "hinge": hinge.tolist(),
        "leaf": leaf_world.tolist(),
        "arc": arc_world.tolist(),
        "rotation_deg": float(math.degrees(math.atan2(open_direction[1], open_direction[0]))),
        "wall_orientation": str(wall_orientation),
        "anchor_mode": str(anchor_mode),
        "door_width": float(door_width),
        "bbox_center": ((bbox_min + bbox_max) / 2.0).tolist(),
    }


def _point_inside_any_wall(point, wall_contours):
    for contour in wall_contours:
        distance = float(cv2.pointPolygonTest(contour, (float(point[0]), float(point[1])), True))
        if distance > 1.5:
            return True, distance
    return False, 0.0


def _score_door_candidate(candidate, detected_center, wall_contours, *, room=None, legacy_hinge=None):
    score = float(np.linalg.norm(np.array(candidate["bbox_center"], dtype=float) - detected_center)) * 0.08

    if legacy_hinge is not None:
        score += float(np.linalg.norm(np.array(candidate["hinge"], dtype=float) - legacy_hinge)) * 0.02

    sampled_points = []
    leaf = np.array(candidate["leaf"], dtype=float)
    arc = np.array(candidate["arc"], dtype=float)

    if len(leaf) > 1:
        sampled_points.append(leaf[1])
    if len(arc) > 0:
        step = max(1, len(arc) // 6)
        sampled_points.extend(arc[::step])
        if len(sampled_points) == 0 or not np.array_equal(sampled_points[-1], arc[-1]):
            sampled_points.append(arc[-1])

    wall_penalty = 0.0
    for point in sampled_points:
        inside_wall, distance = _point_inside_any_wall(point, wall_contours)
        if inside_wall:
            wall_penalty += 400.0 + distance * 30.0

    room_penalty = 0.0
    if room is not None:
        contour = room["contour"]
        for point in sampled_points:
            distance = float(cv2.pointPolygonTest(contour, (float(point[0]), float(point[1])), True))
            if distance < -2.0:
                room_penalty += abs(distance) * 4.0

    return score + wall_penalty + room_penalty


def _build_opening_based_door(
    template,
    detected,
    template_height,
    opening,
    *,
    wall_contours,
    room=None,
    image_width=None,
    image_height=None,
):
    opening_center = (opening["start_point"] + opening["end_point"]) / 2.0
    wall_tangent = opening["end_point"] - opening["start_point"]
    inward_normal = _choose_inward_normal(
        opening_center,
        wall_tangent,
        room=room,
        image_width=image_width,
        image_height=image_height,
        fallback_target=(detected.get("center_x"), detected.get("center_y")),
    )

    detected_center = np.array(
        [
            float(detected.get("center_x", 0.0)),
            float(detected.get("center_y", 0.0)),
        ],
        dtype=float,
    )
    legacy_hinge = _legacy_hinge_hint(detected, opening["orientation"])

    candidates = []
    for hinge, strike in (
        (opening["start_point"], opening["end_point"]),
        (opening["end_point"], opening["start_point"]),
    ):
        candidate = _build_door_geometry(
            template,
            template_height,
            hinge,
            strike,
            inward_normal,
            detected["id"],
            anchor_mode="opening_gap",
            wall_orientation=opening["orientation"],
        )
        if candidate is None:
            continue

        candidate["opening_id"] = int(opening["id"])
        candidate["opening_span"] = [opening["start_point"].tolist(), opening["end_point"].tolist()]
        candidate["wall_distance"] = 0.0
        score = _score_door_candidate(
            candidate,
            detected_center,
            wall_contours,
            room=room,
            legacy_hinge=legacy_hinge,
        )
        candidates.append((score, candidate))

    if not candidates:
        return None

    candidates.sort(key=lambda item: item[0])
    best = candidates[0][1]
    best.pop("bbox_center", None)
    return best


def _project_to_segment(point, segment):
    proj_x, proj_y, distance = point_to_segment_projection(
        float(point[0]),
        float(point[1]),
        float(segment["p1"][0]),
        float(segment["p1"][1]),
        float(segment["p2"][0]),
        float(segment["p2"][1]),
    )
    return np.array([proj_x, proj_y], dtype=float), float(distance)


def _select_best_wall_segment(detected, wall_segments):
    if not wall_segments:
        return None, None, float("inf")

    center = np.array(
        [
            float(detected.get("center_x", 0.0)),
            float(detected.get("center_y", 0.0)),
        ],
        dtype=float,
    )
    symbol_axis = _estimate_symbol_axis(detected)

    best_segment = None
    best_projection = None
    best_score = float("inf")

    for segment in wall_segments:
        if segment["length"] < 30.0:
            continue

        tangent = _normalize_vector(segment["p2"] - segment["p1"], name="wall_segment_tangent")
        if tangent is None:
            continue
        normal = np.array([-tangent[1], tangent[0]], dtype=float)
        alignment = abs(float(np.dot(symbol_axis, normal)))
        projection, distance = _project_to_segment(center, segment)
        score = distance * 2.0 + (1.0 - alignment) * 120.0 - min(segment["length"], 300.0) * 0.05

        if score < best_score:
            best_score = score
            best_segment = segment
            best_projection = projection

    return best_segment, best_projection, best_score


def _build_segment_based_door(
    template,
    detected,
    template_height,
    segment,
    projection,
    *,
    wall_contours,
    room=None,
    image_width=None,
    image_height=None,
):
    tangent = _normalize_vector(segment["p2"] - segment["p1"], name="projected_segment_tangent")
    if tangent is None:
        return None

    door_width = max(
        24.0,
        min(
            float(detected.get("width", 0.0)),
            float(detected.get("height", 0.0)),
            segment["length"],
        ),
    )
    opening_start = projection - tangent * (door_width / 2.0)
    opening_end = projection + tangent * (door_width / 2.0)
    opening_center = (opening_start + opening_end) / 2.0

    inward_normal = _choose_inward_normal(
        opening_center,
        tangent,
        room=room,
        image_width=image_width,
        image_height=image_height,
        fallback_target=(detected.get("center_x"), detected.get("center_y")),
    )

    orientation = segment["orientation"] if segment["orientation"] in {"horizontal", "vertical"} else "angled"
    legacy_orientation = "vertical" if orientation == "vertical" else "horizontal"
    legacy_hinge = _legacy_hinge_hint(detected, legacy_orientation)
    detected_center = np.array(
        [
            float(detected.get("center_x", 0.0)),
            float(detected.get("center_y", 0.0)),
        ],
        dtype=float,
    )

    candidates = []
    for hinge, strike in (
        (opening_start, opening_end),
        (opening_end, opening_start),
    ):
        candidate = _build_door_geometry(
            template,
            template_height,
            hinge,
            strike,
            inward_normal,
            detected["id"],
            anchor_mode="segment_projection",
            wall_orientation=orientation,
        )
        if candidate is None:
            continue

        _, wall_distance = _project_to_segment(np.array(candidate["hinge"], dtype=float), segment)
        candidate["wall_distance"] = wall_distance
        score = _score_door_candidate(
            candidate,
            detected_center,
            wall_contours,
            room=room,
            legacy_hinge=legacy_hinge,
        ) + wall_distance * 25.0
        candidates.append((score, candidate))

    if not candidates:
        return None

    candidates.sort(key=lambda item: item[0])
    best = candidates[0][1]
    best.pop("bbox_center", None)
    return best


def _build_legacy_door(template, detected, template_height):
    width = float(detected.get("width", 0.0))
    height = float(detected.get("height", 0.0))
    door_width = max(24.0, min(width, height))
    scale = float(door_width) / float(template_height)

    orientation = detected.get("orientation")
    if orientation not in LEGACY_HINGE_RULES:
        orientation = "horizontal" if width >= height else "vertical"

    rule = LEGACY_HINGE_RULES[orientation]
    hinge = np.array(
        [
            float(detected.get(rule["x"], detected.get("center_x", 0.0))),
            float(detected.get(rule["y"], detected.get("center_y", 0.0))),
        ],
        dtype=float,
    )

    rotation_deg = float(rule["rotation"])
    leaf_world = rotate_points(np.array(template["leaf"], dtype=float) * scale, rotation_deg) + hinge
    arc_world = rotate_points(np.array(template["arc"], dtype=float) * scale, rotation_deg) + hinge

    return {
        "id": int(detected["id"]),
        "hinge": hinge.tolist(),
        "leaf": leaf_world.tolist(),
        "arc": arc_world.tolist(),
        "rotation_deg": rotation_deg,
        "wall_orientation": str(orientation),
        "anchor_mode": "legacy_bbox",
        "door_width": door_width,
        "wall_distance": None,
    }


def place_single_door(
    template,
    detected,
    TEMPLATE_HEIGHT,
    *,
    walls=None,
    room_polygons=None,
    image_width=None,
    image_height=None,
):
    center_x = float(detected.get("center_x", 0.0))
    center_y = float(detected.get("center_y", 0.0))

    if walls is None:
        walls = _load_default_walls()

    wall_polygons, wall_segments = _normalize_wall_segments(walls)
    wall_contours = _build_polygon_contours(wall_polygons, "vertices")
    room = _find_best_room(center_x, center_y, room_polygons)

    openings = _infer_wall_openings(wall_segments)
    opening = _select_opening_for_door(detected, openings)

    placement = None
    if opening is not None:
        placement = _build_opening_based_door(
            template,
            detected,
            TEMPLATE_HEIGHT,
            opening,
            wall_contours=wall_contours,
            room=room,
            image_width=image_width,
            image_height=image_height,
        )

    if placement is None:
        segment, projection, _ = _select_best_wall_segment(detected, wall_segments)
        if segment is not None and projection is not None:
            placement = _build_segment_based_door(
                template,
                detected,
                TEMPLATE_HEIGHT,
                segment,
                projection,
                wall_contours=wall_contours,
                room=room,
                image_width=image_width,
                image_height=image_height,
            )

    if placement is None:
        placement = _build_legacy_door(template, detected, TEMPLATE_HEIGHT)

    return placement
