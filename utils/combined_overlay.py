import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Tuple

import cv2
import numpy as np


def _load_json(path: Path) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def _load_window_template() -> Dict[str, Any] | None:
    candidates = []
    env_path = os.environ.get("S2FP_WINDOW_TEMPLATE_PATH")
    if env_path:
        candidates.append(Path(env_path))
    candidates.append(Path(__file__).resolve().parent.parent / "opening_pipeline" / "Wind.json")
    candidates.append(Path(r"C:\Users\yashj\Desktop\original\Wind.json"))

    for candidate in candidates:
        if candidate.exists():
            with open(candidate, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
    return None


def _window_template_bounds(template: Dict[str, Any]) -> Tuple[float, float, float, float] | None:
    points: List[Tuple[float, float]] = []
    for line in template.get("lines", []):
        if isinstance(line, dict):
            points.append((float(line["x1"]), float(line["y1"])))
            points.append((float(line["x2"]), float(line["y2"])))
    if not points:
        return None
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return min(xs), min(ys), max(xs), max(ys)


def _template_polyline_points_within_bounds(polyline: Any, bounds: Tuple[float, float, float, float], *, pad_ratio: float = 0.08) -> List[Tuple[float, float]]:
    if not isinstance(polyline, list):
        return []
    min_x, min_y, max_x, max_y = bounds
    width = max(max_x - min_x, 1e-6)
    height = max(max_y - min_y, 1e-6)
    pad_x = width * pad_ratio
    pad_y = height * pad_ratio
    points: List[Tuple[float, float]] = []
    for point in polyline:
        if isinstance(point, dict) and "x" in point and "y" in point:
            x = float(point["x"])
            y = float(point["y"])
            if (min_x - pad_x) <= x <= (max_x + pad_x) and (min_y - pad_y) <= y <= (max_y + pad_y):
                points.append((x, y))
    return points


def _as_int_pt(pt) -> Tuple[int, int]:
    return int(round(float(pt[0]))), int(round(float(pt[1])))


def _wall_polygon_sort_key(poly: Dict[str, Any]) -> Tuple[float, float, str]:
    verts = poly.get("vertices") or []
    if not verts:
        return (0.0, 0.0, str(poly.get("wall_id", poly.get("id", ""))))
    ys = [float(vertex[1]) for vertex in verts]
    xs = [float(vertex[0]) for vertex in verts]
    return (round(min(ys), 4), round(min(xs), 4), str(poly.get("wall_id", poly.get("id", ""))))


def _wall_segment_sort_key(wall: Dict[str, Any]) -> Tuple[float, float, float, float, str]:
    return (
        round(float(wall.get("y1", 0.0)), 4),
        round(float(wall.get("x1", 0.0)), 4),
        round(float(wall.get("y2", 0.0)), 4),
        round(float(wall.get("x2", 0.0)), 4),
        str(wall.get("id", "")),
    )


def _door_sort_key(door: Dict[str, Any]) -> Tuple[float, float, str]:
    hinge = door.get("hinge") or [0.0, 0.0]
    return (
        round(float(hinge[1]), 4),
        round(float(hinge[0]), 4),
        str(door.get("id", "")),
    )


def _draw_wall_polygons(img: np.ndarray, wall_polygons: Any, *, color=(0, 0, 0), thickness: int = 6) -> None:
    if not isinstance(wall_polygons, list):
        return

    for poly in sorted(wall_polygons, key=_wall_polygon_sort_key):
        if not isinstance(poly, dict):
            continue
        verts = poly.get("vertices")
        if not isinstance(verts, list) or len(verts) < 2:
            continue
        pts = np.array([_as_int_pt(v) for v in verts], dtype=np.int32).reshape((-1, 1, 2))
        cv2.fillPoly(img, [pts], color)
        cv2.polylines(img, [pts], isClosed=True, color=color, thickness=int(thickness))


def _draw_wall_segments(img: np.ndarray, walls: Any, *, color=(0, 0, 0), thickness: int = 10) -> None:
    if not (isinstance(walls, dict) and isinstance(walls.get("walls"), list)):
        return

    for w in sorted(walls["walls"], key=_wall_segment_sort_key):
        if not isinstance(w, dict):
            continue
        if not {"x1", "y1", "x2", "y2"}.issubset(w.keys()):
            continue
        p1 = _as_int_pt((w["x1"], w["y1"]))
        p2 = _as_int_pt((w["x2"], w["y2"]))
        wall_thickness = w.get("thickness", thickness)
        try:
            wall_thickness = int(round(float(wall_thickness)))
        except (TypeError, ValueError):
            wall_thickness = int(thickness)
        wall_thickness = max(6, wall_thickness)
        cv2.line(img, p1, p2, color, wall_thickness)


def _draw_doors(img: np.ndarray, placed_doors: Dict[str, Any], *, color=(0, 0, 0)) -> None:
    doors = placed_doors.get("doors", []) if isinstance(placed_doors, dict) else []

    for door in sorted(doors, key=_door_sort_key):
        if not isinstance(door, dict):
            continue
        hinge = door.get("hinge")
        leaf = door.get("leaf")
        arc = door.get("arc")

        if isinstance(hinge, (list, tuple)) and len(hinge) == 2:
            hx, hy = _as_int_pt(hinge)
            cv2.circle(img, (hx, hy), 8, color, -1)

        if isinstance(leaf, list) and len(leaf) >= 2:
            p0 = _as_int_pt(leaf[0])
            p1 = _as_int_pt(leaf[1])
            cv2.line(img, p0, p1, color, 6)

        if isinstance(arc, list) and len(arc) >= 2:
            arc_pts = np.array([_as_int_pt(p) for p in arc], dtype=np.int32)
            cv2.polylines(img, [arc_pts.reshape((-1, 1, 2))], isClosed=False, color=color, thickness=5)


def _draw_windows(img: np.ndarray, placed_windows: Dict[str, Any], *, color=(0, 0, 0)) -> None:
    windows = placed_windows.get("windows", []) if isinstance(placed_windows, dict) else []
    template = _load_window_template()
    bounds = _window_template_bounds(template) if template else None
    use_template = bool(bounds and template)

    for window in windows:
        if not isinstance(window, dict):
            continue
        start = window.get("start")
        end = window.get("end")
        if not (isinstance(start, (list, tuple)) and len(start) == 2 and isinstance(end, (list, tuple)) and len(end) == 2):
            continue

        start_pt = np.array([float(start[0]), float(start[1])], dtype=float)
        end_pt = np.array([float(end[0]), float(end[1])], dtype=float)
        tangent = end_pt - start_pt
        length = float(np.linalg.norm(tangent))
        if length <= 1e-6:
            continue

        tangent /= length
        normal = np.array([-tangent[1], tangent[0]], dtype=float)
        wall_thickness = window.get("wall_thickness", 0.0)
        try:
            wall_thickness = float(wall_thickness)
        except (TypeError, ValueError):
            wall_thickness = 0.0

        frame_half_depth = max(6.0, min(12.0, wall_thickness * 0.46 if wall_thickness > 0 else 7.0))
        symbol_half_depth = max(frame_half_depth, wall_thickness * 0.5 if wall_thickness > 0 else frame_half_depth + 1.0)
        line_thickness = 2
        frame_thickness = 2
        clear_half_depth = max(symbol_half_depth + 2.0, wall_thickness * 0.6 if wall_thickness > 0 else symbol_half_depth + 3.0)
        cap_clear = 0.0 if use_template else max(6.0, wall_thickness * 0.35 if wall_thickness > 0 else 8.0)

        clear_start = start_pt - tangent * cap_clear
        clear_end = end_pt + tangent * cap_clear
        clear_polygon = np.array(
            [
                _as_int_pt(clear_start + normal * clear_half_depth),
                _as_int_pt(clear_end + normal * clear_half_depth),
                _as_int_pt(clear_end - normal * clear_half_depth),
                _as_int_pt(clear_start - normal * clear_half_depth),
            ],
            dtype=np.int32,
        ).reshape((-1, 1, 2))
        cv2.fillPoly(img, [clear_polygon], (255, 255, 255))

        def local_point(u: float, v: float) -> np.ndarray:
            return start_pt + tangent * (length * u) + normal * (symbol_half_depth * 2.0 * v)

        def draw_segment(u1: float, v1: float, u2: float, v2: float, thickness: int = line_thickness) -> None:
            cv2.line(img, _as_int_pt(local_point(u1, v1)), _as_int_pt(local_point(u2, v2)), color, thickness)
        if use_template:
            min_x, min_y, max_x, max_y = bounds
            width = max(max_x - min_x, 1e-6)
            height = max(max_y - min_y, 1e-6)
            center_y = (min_y + max_y) / 2.0

            def norm_xy(x: float, y: float) -> Tuple[float, float]:
                u = (x - min_x) / width
                v = (y - center_y) / height
                return u, v

            for line in template.get("lines", []):
                if not isinstance(line, dict):
                    continue
                u1, v1 = norm_xy(float(line["x1"]), float(line["y1"]))
                u2, v2 = norm_xy(float(line["x2"]), float(line["y2"]))
                draw_segment(u1, v1, u2, v2, line_thickness)

            for polyline in template.get("polylines", []):
                filtered_points = _template_polyline_points_within_bounds(polyline, bounds)
                if len(filtered_points) < 2:
                    continue
                normalized = []
                for x, y in filtered_points:
                    normalized.append(norm_xy(x, y))
                for (u1, v1), (u2, v2) in zip(normalized, normalized[1:]):
                    draw_segment(u1, v1, u2, v2, line_thickness)


def make_combined_overlay(
    *,
    image_path: Path,
    wall_polygons_path: Path,
    placed_doors_path: Path,
    placed_windows_path: Path | None,
    out_path: Path,
) -> Path:
    img = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if img is None:
        raise FileNotFoundError(f"Failed to read image: {image_path}")

    walls_data = _load_json(wall_polygons_path)
    placed = _load_json(placed_doors_path)
    placed_windows = _load_json(placed_windows_path) if placed_windows_path and placed_windows_path.exists() else {"windows": []}

    # Render on a clean white canvas (floorplan style)
    out = np.full_like(img, 255)

    # Prefer fused wall segments if provided (dict with 'walls'), else fall back to polygons.
    _draw_wall_segments(out, walls_data, color=(0, 0, 0))
    _draw_wall_polygons(out, walls_data, color=(0, 0, 0))
    _draw_doors(out, placed, color=(0, 0, 0))
    _draw_windows(out, placed_windows, color=(0, 0, 0))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out_path), out)
    return out_path


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--image", required=True)
    p.add_argument("--walls", required=True)
    p.add_argument("--doors", required=True)
    p.add_argument("--windows")
    p.add_argument("--out", required=True)
    args = p.parse_args()

    make_combined_overlay(
        image_path=Path(args.image),
        wall_polygons_path=Path(args.walls),
        placed_doors_path=Path(args.doors),
        placed_windows_path=Path(args.windows) if args.windows else None,
        out_path=Path(args.out),
    )
