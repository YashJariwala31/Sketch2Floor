"""Attach detected windows to nearby walls and write placed window geometry."""

import json
import os
from pathlib import Path

import numpy as np

from opening_pipeline.transform import _normalize_vector, _normalize_wall_segments, _select_best_wall_segment


BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent

GEOMETRY_PATH = os.environ.get("S2FP_GEOMETRY_PATH", "predictions/3_geometry.json")
WALLS_PATH = os.environ.get("S2FP_WALLS_PATH")
OUTPUT_PATH = os.environ.get("S2FP_PLACED_WINDOWS_PATH", "intermediate/placed_windows.json")


def _resolve_path(path_value):
    return (ROOT_DIR / path_value) if not os.path.isabs(path_value) else Path(path_value)


def _window_sort_key(window):
    center = window.get("center") or [0.0, 0.0]
    attached_wall_id = str(window.get("attached_wall_id", ""))
    return (
        round(float(center[1]), 4),
        round(float(center[0]), 4),
        attached_wall_id,
        str(window.get("id", "")),
    )


def _write_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    with open(temp_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
    os.replace(temp_path, path)


def _append_point(points, value):
    if not (isinstance(value, (list, tuple)) and len(value) == 2):
        return
    try:
        point = np.array([float(value[0]), float(value[1])], dtype=float)
    except (TypeError, ValueError):
        return
    if not np.isfinite(point).all():
        return
    points.append(point)


def _window_reference_points(detected):
    points = []

    _append_point(points, [detected.get("center_x", 0.0), detected.get("center_y", 0.0)])

    x = detected.get("x")
    y = detected.get("y")
    width = detected.get("width")
    height = detected.get("height")
    if None not in (x, y, width, height):
        try:
            x = float(x)
            y = float(y)
            width = float(width)
            height = float(height)
        except (TypeError, ValueError):
            width = height = 0.0
        else:
            for point in (
                (x, y),
                (x + width, y),
                (x + width, y + height),
                (x, y + height),
                (x + width / 2.0, y),
                (x + width, y + height / 2.0),
                (x + width / 2.0, y + height),
                (x, y + height / 2.0),
            ):
                _append_point(points, point)

    rotated_box = detected.get("rotated_box")
    if isinstance(rotated_box, list):
        for point in rotated_box:
            _append_point(points, point)

    return points


def _window_span_along_tangent(detected, tangent, segment_length):
    points = _window_reference_points(detected)
    if points:
        projections = [float(np.dot(point, tangent)) for point in points]
        span = max(projections) - min(projections)
    else:
        span = 0.0

    if span <= 1e-6:
        try:
            span = max(float(detected.get("width", 0.0)), float(detected.get("height", 0.0)))
        except (TypeError, ValueError):
            span = 0.0

    span = max(24.0, float(span))
    if segment_length > 1e-6:
        span = min(span, float(segment_length))
    return span


def place_single_window(detected, walls):
    _wall_polygons, wall_segments = _normalize_wall_segments(walls)
    if not wall_segments:
        return None

    segment, projection, _score = _select_best_wall_segment(detected, wall_segments)
    if segment is None or projection is None:
        return None

    tangent = _normalize_vector(segment["p2"] - segment["p1"], name="window_wall_tangent")
    if tangent is None:
        return None

    window_width = _window_span_along_tangent(detected, tangent, float(segment.get("length", 0.0) or 0.0))

    start = projection - tangent * (window_width / 2.0)
    end = projection + tangent * (window_width / 2.0)
    orientation = segment["orientation"] if segment["orientation"] in {"horizontal", "vertical"} else "angled"

    return {
        "id": int(detected.get("id", 0)),
        "center": projection.tolist(),
        "start": start.tolist(),
        "end": end.tolist(),
        "width": float(window_width),
        "attached_wall_id": int(segment.get("wall_id", segment.get("id", -1))),
        "wall_orientation": str(orientation),
        "wall_thickness": float(segment.get("thickness", 0.0) or 0.0),
    }


def main():
    geometry_path = _resolve_path(GEOMETRY_PATH)
    with open(geometry_path, "r", encoding="utf-8") as handle:
        geometry = json.load(handle)

    if not WALLS_PATH:
        raise RuntimeError("S2FP_WALLS_PATH is required for window placement.")

    walls_path = _resolve_path(WALLS_PATH)
    with open(walls_path, "r", encoding="utf-8") as handle:
        walls = json.load(handle)

    detections = sorted(
        geometry.get("windows", []),
        key=lambda det: (
            round(float(det.get("center_y", 0.0)), 4),
            round(float(det.get("center_x", 0.0)), 4),
            round(float(det.get("width", 0.0)), 4),
            round(float(det.get("height", 0.0)), 4),
            int(det.get("id", 0)),
        ),
    )

    placed = []
    for det in detections:
        placement = place_single_window(det, walls)
        if placement is None:
            print(f"[WARN] Skipping window {det.get('id', '?')}: no nearby wall match")
            continue
        placed.append(placement)

    output_path = _resolve_path(OUTPUT_PATH)
    _write_json(output_path, {"windows": sorted(placed, key=_window_sort_key)})


if __name__ == "__main__":
    main()
