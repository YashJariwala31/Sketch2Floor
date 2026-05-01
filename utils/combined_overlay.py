import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

import cv2
import numpy as np


def _load_json(path: Path) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


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


def make_combined_overlay(
    *,
    image_path: Path,
    wall_polygons_path: Path,
    placed_doors_path: Path,
    out_path: Path,
) -> Path:
    img = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if img is None:
        raise FileNotFoundError(f"Failed to read image: {image_path}")

    walls_data = _load_json(wall_polygons_path)
    placed = _load_json(placed_doors_path)

    # Render on a clean white canvas (floorplan style)
    out = np.full_like(img, 255)

    # Prefer fused wall segments if provided (dict with 'walls'), else fall back to polygons.
    _draw_wall_segments(out, walls_data, color=(0, 0, 0))
    _draw_wall_polygons(out, walls_data, color=(0, 0, 0))
    _draw_doors(out, placed, color=(0, 0, 0))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out_path), out)
    return out_path


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--image", required=True)
    p.add_argument("--walls", required=True)
    p.add_argument("--doors", required=True)
    p.add_argument("--out", required=True)
    args = p.parse_args()

    make_combined_overlay(
        image_path=Path(args.image),
        wall_polygons_path=Path(args.walls),
        placed_doors_path=Path(args.doors),
        out_path=Path(args.out),
    )
