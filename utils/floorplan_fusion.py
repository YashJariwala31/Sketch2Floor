import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


@dataclass(frozen=True)
class Wall:
    id: str
    x1: float
    y1: float
    x2: float
    y2: float
    thickness: Optional[float] = None


def _as_float(x: Any) -> float:
    return float(x)


def _coerce_point(value: Any) -> Optional[List[float]]:
    if not (isinstance(value, (list, tuple)) and len(value) == 2):
        return None

    try:
        point = [_as_float(value[0]), _as_float(value[1])]
    except (TypeError, ValueError):
        return None

    if not math.isfinite(point[0]) or not math.isfinite(point[1]):
        return None
    return point


def _coerce_point_list(value: Any) -> List[List[float]]:
    if not isinstance(value, list):
        return []

    out: List[List[float]] = []
    for item in value:
        point = _coerce_point(item)
        if point is not None:
            out.append(point)
    return out


def _norm(vx: float, vy: float) -> float:
    return math.hypot(vx, vy)


def _dot(ax: float, ay: float, bx: float, by: float) -> float:
    return ax * bx + ay * by


def _project_point_to_segment(px: float, py: float, x1: float, y1: float, x2: float, y2: float) -> Tuple[float, float, float, float]:
    vx = x2 - x1
    vy = y2 - y1
    denom = vx * vx + vy * vy
    if denom <= 1e-12:
        dx = px - x1
        dy = py - y1
        return x1, y1, 0.0, math.hypot(dx, dy)

    t = ((px - x1) * vx + (py - y1) * vy) / denom
    t_clamped = max(0.0, min(1.0, t))
    projx = x1 + t_clamped * vx
    projy = y1 + t_clamped * vy
    dist = math.hypot(px - projx, py - projy)
    return projx, projy, t_clamped, dist


def _wall_direction(w: Wall) -> Tuple[float, float, float]:
    wx = w.x2 - w.x1
    wy = w.y2 - w.y1
    n = _norm(wx, wy)
    if n <= 1e-9:
        return 1.0, 0.0, 0.0
    return wx / n, wy / n, n


def _perp(wx: float, wy: float) -> Tuple[float, float]:
    return -wy, wx


def _cross(ax: float, ay: float, bx: float, by: float) -> float:
    return ax * by - ay * bx


def _wall_from_polygon_vertices(w: Dict[str, Any], index: int) -> Optional[Wall]:
    verts = w.get("vertices")
    if not isinstance(verts, list) or len(verts) < 2:
        return None

    try:
        points = [(_as_float(v[0]), _as_float(v[1])) for v in verts]
    except (TypeError, ValueError, IndexError):
        return None

    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    width = max_x - min_x
    height = max_y - min_y
    if max(width, height) <= 1e-6:
        return None

    wid = str(w.get("id", w.get("wall_id", f"wallpoly_{index}")))
    if width >= height:
        center_y = (min_y + max_y) / 2.0
        return Wall(
            id=wid,
            x1=min_x,
            y1=center_y,
            x2=max_x,
            y2=center_y,
            thickness=max(1.0, height),
        )

    center_x = (min_x + max_x) / 2.0
    return Wall(
        id=wid,
        x1=center_x,
        y1=min_y,
        x2=center_x,
        y2=max_y,
        thickness=max(1.0, width),
    )


def _parse_walls(walls_input: Any) -> List[Wall]:
    if isinstance(walls_input, dict) and isinstance(walls_input.get("walls"), list):
        walls_input = walls_input["walls"]

    out: List[Wall] = []
    if not isinstance(walls_input, list):
        raise ValueError("walls must be a list, or a dict containing a 'walls' list")

    for i, w in enumerate(walls_input):
        if not isinstance(w, dict):
            raise ValueError("each wall must be a dict")

        if {"x1", "y1", "x2", "y2"}.issubset(w.keys()):
            out.append(
                Wall(
                    id=str(w.get("id", f"wall_{i}")),
                    x1=_as_float(w["x1"]),
                    y1=_as_float(w["y1"]),
                    x2=_as_float(w["x2"]),
                    y2=_as_float(w["y2"]),
                    thickness=_as_float(w["thickness"]) if "thickness" in w and w["thickness"] is not None else None,
                )
            )
            continue

        if "vertices" in w and isinstance(w["vertices"], list):
            wall = _wall_from_polygon_vertices(w, i)
            if wall is not None:
                out.append(wall)
            continue

        raise ValueError(f"Unrecognized wall format at index {i}: keys={list(w.keys())}")

    return sorted(out, key=lambda wall: (round(wall.y1, 4), round(wall.x1, 4), str(wall.id)))


def _parse_doors(doors_input: Any) -> List[Dict[str, Any]]:
    if isinstance(doors_input, dict) and isinstance(doors_input.get("doors"), list):
        doors_input = doors_input["doors"]
    if not isinstance(doors_input, list):
        raise ValueError("doors must be a list, or a dict containing a 'doors' list")

    out: List[Dict[str, Any]] = []
    for i, d in enumerate(doors_input):
        if not isinstance(d, dict):
            raise ValueError("each door must be a dict")
        if "hinge" not in d:
            raise ValueError(f"door missing 'hinge' at index {i}")

        hinge = _coerce_point(d["hinge"])
        if hinge is None:
            raise ValueError(f"door hinge must be [x,y] at index {i}")

        strike = None
        if "strike" in d:
            strike = _coerce_point(d["strike"])
        elif "arc_end" in d:
            strike = _coerce_point(d["arc_end"])
        elif "arc" in d and isinstance(d["arc"], list) and len(d["arc"]) > 0:
            strike = _coerce_point(d["arc"][-1])
        elif "leaf" in d and isinstance(d["leaf"], list) and len(d["leaf"]) > 0:
            strike = _coerce_point(d["leaf"][-1])

        if strike is None:
            raise ValueError(
                f"door must include 'strike' (or an 'arc'/'leaf' to infer it) at index {i}"
            )

        parsed = {
            "id": str(d.get("id", f"door_{i}")),
            "hinge": hinge,
            "strike": strike,
        }

        leaf = _coerce_point_list(d.get("leaf"))
        if len(leaf) >= 2:
            parsed["leaf"] = leaf[:2]

        arc = _coerce_point_list(d.get("arc"))
        if len(arc) >= 2:
            parsed["arc"] = arc

        opening_span = _coerce_point_list(d.get("opening_span"))
        if len(opening_span) >= 2:
            parsed["opening_span"] = opening_span[:2]

        if isinstance(d.get("wall_orientation"), str):
            parsed["wall_orientation"] = str(d["wall_orientation"])

        out.append(parsed)

    return sorted(
        out,
        key=lambda door: (
            round(float(door["hinge"][1]), 4),
            round(float(door["hinge"][0]), 4),
            str(door["id"]),
        ),
    )


def _wall_length_from_dict(wall: Dict[str, Any]) -> float:
    return math.hypot(
        float(wall.get("x2", 0.0)) - float(wall.get("x1", 0.0)),
        float(wall.get("y2", 0.0)) - float(wall.get("y1", 0.0)),
    )


def _door_symbol_bbox(door: Dict[str, Any]) -> Optional[Tuple[float, float, float, float]]:
    points: List[List[float]] = []
    for key in ("hinge", "strike"):
        point = _coerce_point(door.get(key))
        if point is not None:
            points.append(point)

    points.extend(_coerce_point_list(door.get("opening_span")))
    points.extend(_coerce_point_list(door.get("leaf")))
    points.extend(_coerce_point_list(door.get("arc")))

    if len(points) < 2:
        return None

    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return (min(xs), min(ys), max(xs), max(ys))


def _segment_overlap_ratio_with_box(
    wall: Dict[str, Any],
    box: Tuple[float, float, float, float],
    *,
    padding: float,
    samples: int = 11,
) -> float:
    sample_count = max(3, int(samples))
    inside = 0

    x1 = float(wall["x1"])
    y1 = float(wall["y1"])
    x2 = float(wall["x2"])
    y2 = float(wall["y2"])
    min_x, min_y, max_x, max_y = box

    for index in range(sample_count):
        t = index / (sample_count - 1)
        px = x1 + (x2 - x1) * t
        py = y1 + (y2 - y1) * t
        if (
            min_x - padding <= px <= max_x + padding
            and min_y - padding <= py <= max_y + padding
        ):
            inside += 1

    return inside / float(sample_count)


def _is_symbol_artifact_wall(wall: Dict[str, Any], door: Dict[str, Any]) -> bool:
    box = _door_symbol_bbox(door)
    if box is None:
        return False

    thickness = wall.get("thickness")
    try:
        thickness_value = float(thickness) if thickness is not None else 0.0
    except (TypeError, ValueError):
        thickness_value = 0.0

    padding = max(8.0, thickness_value * 0.35)
    overlap_ratio = _segment_overlap_ratio_with_box(wall, box, padding=padding)
    if overlap_ratio < 0.65:
        return False

    wall_length = _wall_length_from_dict(wall)
    box_extent = max(box[2] - box[0], box[3] - box[1])

    if wall_length <= max(box_extent * 1.35, padding * 8.0, 260.0):
        return True

    return overlap_ratio >= 0.98


def _remove_symbol_artifact_walls(
    fused_walls: List[Dict[str, Any]],
    door_list: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    cleaned: List[Dict[str, Any]] = []

    for wall in fused_walls:
        if any(_is_symbol_artifact_wall(wall, door) for door in door_list):
            continue
        cleaned.append(wall)

    return cleaned


def _opening_boxes_from_geometry(geometry: Any) -> List[Tuple[float, float, float, float]]:
    if not isinstance(geometry, dict):
        return []

    boxes: List[Tuple[float, float, float, float]] = []
    openings = geometry.get("doors")
    if not isinstance(openings, list):
        return []

    for opening in openings:
        if not isinstance(opening, dict):
            continue

        points = _coerce_point_list(opening.get("rotated_box"))
        if len(points) >= 2:
            xs = [point[0] for point in points]
            ys = [point[1] for point in points]
            box = (min(xs), min(ys), max(xs), max(ys))
        else:
            try:
                x = _as_float(opening.get("x"))
                y = _as_float(opening.get("y"))
                width = _as_float(opening.get("width"))
                height = _as_float(opening.get("height"))
            except (TypeError, ValueError):
                continue
            box = (x, y, x + width, y + height)

        if (box[2] - box[0]) <= 1e-6 or (box[3] - box[1]) <= 1e-6:
            continue
        boxes.append(box)

    return sorted(
        boxes,
        key=lambda box: (
            round(float(box[1]), 4),
            round(float(box[0]), 4),
            round(float(box[3]), 4),
            round(float(box[2]), 4),
        ),
    )


def _carve_wall_segment_by_box(
    wall: Dict[str, Any],
    box: Tuple[float, float, float, float],
    *,
    box_index: int,
    min_remaining_wall: float,
) -> List[Dict[str, Any]]:
    try:
        x1 = float(wall["x1"])
        y1 = float(wall["y1"])
        x2 = float(wall["x2"])
        y2 = float(wall["y2"])
    except (KeyError, TypeError, ValueError):
        return [wall]

    try:
        thickness = float(wall.get("thickness")) if wall.get("thickness") is not None else 0.0
    except (TypeError, ValueError):
        thickness = 0.0

    pad_minor = max(8.0, thickness * 0.35)
    pad_major = max(6.0, thickness * 0.25)
    min_axis_overlap = max(6.0, thickness * 0.5)
    min_piece_length = max(float(min_remaining_wall), 12.0)

    min_x, min_y, max_x, max_y = box
    is_horizontal = abs(y2 - y1) <= abs(x2 - x1)

    if is_horizontal:
        center = (y1 + y2) / 2.0
        if not (min_y - pad_minor <= center <= max_y + pad_minor):
            return [wall]

        start = min(x1, x2)
        end = max(x1, x2)
        cut_start = max(start, min_x - pad_major)
        cut_end = min(end, max_x + pad_major)
        if cut_end - cut_start < min_axis_overlap:
            return [wall]

        remaining: List[Tuple[float, float]] = []
        if cut_start - start >= min_piece_length:
            remaining.append((start, cut_start))
        if end - cut_end >= min_piece_length:
            remaining.append((cut_end, end))

        carved: List[Dict[str, Any]] = []
        for piece_index, (piece_start, piece_end) in enumerate(remaining):
            updated = dict(wall)
            updated["id"] = f"{wall['id']}_cut{box_index}_{piece_index}"
            if x1 <= x2:
                updated["x1"] = piece_start
                updated["x2"] = piece_end
            else:
                updated["x1"] = piece_end
                updated["x2"] = piece_start
            updated["y1"] = y1
            updated["y2"] = y2
            carved.append(updated)
        return carved

    center = (x1 + x2) / 2.0
    if not (min_x - pad_minor <= center <= max_x + pad_minor):
        return [wall]

    start = min(y1, y2)
    end = max(y1, y2)
    cut_start = max(start, min_y - pad_major)
    cut_end = min(end, max_y + pad_major)
    if cut_end - cut_start < min_axis_overlap:
        return [wall]

    remaining = []
    if cut_start - start >= min_piece_length:
        remaining.append((start, cut_start))
    if end - cut_end >= min_piece_length:
        remaining.append((cut_end, end))

    carved = []
    for piece_index, (piece_start, piece_end) in enumerate(remaining):
        updated = dict(wall)
        updated["id"] = f"{wall['id']}_cut{box_index}_{piece_index}"
        if y1 <= y2:
            updated["y1"] = piece_start
            updated["y2"] = piece_end
        else:
            updated["y1"] = piece_end
            updated["y2"] = piece_start
        updated["x1"] = x1
        updated["x2"] = x2
        carved.append(updated)
    return carved


def _cleanup_fused_walls_with_geometry(
    fused: Dict[str, Any],
    geometry: Any,
    *,
    min_remaining_wall: float,
) -> Dict[str, Any]:
    boxes = _opening_boxes_from_geometry(geometry)
    if not boxes:
        return fused

    walls = list(fused.get("walls", [])) if isinstance(fused.get("walls", []), list) else []
    for box_index, box in enumerate(boxes):
        updated: List[Dict[str, Any]] = []
        for wall in walls:
            if not isinstance(wall, dict):
                continue
            updated.extend(
                _carve_wall_segment_by_box(
                    wall,
                    box,
                    box_index=box_index,
                    min_remaining_wall=min_remaining_wall,
                )
            )
        walls = updated

    walls.sort(
        key=lambda wall: (
            round(float(wall["y1"]), 4),
            round(float(wall["x1"]), 4),
            round(float(wall["y2"]), 4),
            round(float(wall["x2"]), 4),
            str(wall["id"]),
        )
    )

    cleaned = dict(fused)
    cleaned["walls"] = walls
    return cleaned


def fuse_walls_and_doors(
    walls: Any,
    doors: Any,
    *,
    attach_threshold: float = 35.0,
    perpendicular_eps_deg: float = 20.0,
    min_remaining_wall: float = 2.0,
) -> Dict[str, Any]:
    wall_list = _parse_walls(walls)
    door_list = _parse_doors(doors)

    door_fused: List[Dict[str, Any]] = []

    openings_by_wall: Dict[str, List[Tuple[float, float, Dict[str, Any]]]] = {}

    for d in door_list:
        hx, hy = d["hinge"]
        sx, sy = d["strike"]
        dx = sx - hx
        dy = sy - hy
        width = _norm(dx, dy)
        if width <= 1e-6:
            continue

        best_candidate = None

        for w in wall_list:
            hprojx, hprojy, ht, hdist = _project_point_to_segment(hx, hy, w.x1, w.y1, w.x2, w.y2)
            sprojx, sprojy, st, sdist = _project_point_to_segment(sx, sy, w.x1, w.y1, w.x2, w.y2)
            wxn, wyn, wlen = _wall_direction(w)
            if wlen <= 1e-9:
                continue

            effective_threshold = max(float(attach_threshold), float(w.thickness or 0.0) * 0.75 + 8.0)
            if hdist > effective_threshold or sdist > effective_threshold:
                continue

            interval_len = abs(st - ht) * wlen
            if interval_len < max(20.0, width * 0.35):
                continue

            score = hdist * 2.0 + sdist + abs(interval_len - width) * 0.12 - min(wlen, 400.0) * 0.01
            candidate_key = (
                round(float(score), 6),
                round(float(min(ht, st)), 6),
                round(float(max(ht, st)), 6),
                str(w.id),
            )
            if best_candidate is None or candidate_key < best_candidate["key"]:
                best_candidate = {
                    "key": candidate_key,
                    "score": score,
                    "wall": w,
                    "hinge_projection": (hprojx, hprojy),
                    "strike_projection": (sprojx, sprojy),
                    "hinge_t": ht,
                    "strike_t": st,
                    "direction": (wxn, wyn),
                    "wall_length": wlen,
                }

        if best_candidate is None:
            continue

        best_wall = best_candidate["wall"]
        wxn, wyn = best_candidate["direction"]
        wlen = best_candidate["wall_length"]
        projx, projy = best_candidate["hinge_projection"]
        strike_projx, strike_projy = best_candidate["strike_projection"]

        t0 = min(best_candidate["hinge_t"], best_candidate["strike_t"])
        t1 = max(best_candidate["hinge_t"], best_candidate["strike_t"])
        t0 = max(0.0, min(1.0, t0))
        t1 = max(0.0, min(1.0, t1))
        if abs(t1 - t0) * wlen < float(min_remaining_wall):
            continue

        perp_x, perp_y = _perp(wxn, wyn)
        swing_vector_x = dx
        swing_vector_y = dy
        sign = 1.0 if _dot(perp_x, perp_y, swing_vector_x, swing_vector_y) >= 0.0 else -1.0
        corr_dx = perp_x * sign
        corr_dy = perp_y * sign
        corr_arc_end = [projx + corr_dx * width, projy + corr_dy * width]
        cross = _cross(wxn, wyn, corr_dx, corr_dy)
        swing = "left" if cross > 0 else "right"
        door_angle = 90

        ang = abs(math.degrees(math.atan2(_cross(wxn, wyn, corr_dx, corr_dy), _dot(wxn, wyn, corr_dx, corr_dy))))
        if abs(ang - 90.0) > float(perpendicular_eps_deg):
            corr_dx, corr_dy = perp_x * sign, perp_y * sign
            corr_arc_end = [projx + corr_dx * width, projy + corr_dy * width]
            cross = _cross(wxn, wyn, corr_dx, corr_dy)
            swing = "left" if cross > 0 else "right"

        attached_wall_id = best_wall.id

        door_out = {
            "id": d["id"],
            "hinge": [projx, projy],
            "strike": [strike_projx, strike_projy],
            "width": width,
            "angle": door_angle,
            "swing": swing,
            "attached_wall_id": attached_wall_id,
            "arc_end": corr_arc_end,
        }
        door_fused.append(door_out)

        openings_by_wall.setdefault(attached_wall_id, []).append((min(t0, t1), max(t0, t1), door_out))

    fused_walls: List[Dict[str, Any]] = []

    for w in wall_list:
        wxn, wyn, wlen = _wall_direction(w)
        if wlen <= 1e-9:
            continue

        openings = openings_by_wall.get(w.id, [])
        if not openings:
            fused_walls.append({"id": w.id, "x1": w.x1, "y1": w.y1, "x2": w.x2, "y2": w.y2, "thickness": w.thickness})
            continue

        openings.sort(key=lambda item: (round(float(item[0]), 6), round(float(item[1]), 6), str(item[2]["id"])))

        merged: List[Tuple[float, float]] = []
        for t0, t1, _ in openings:
            if not merged:
                merged.append((t0, t1))
                continue
            p0, p1 = merged[-1]
            if t0 <= p1 + (1e-6):
                merged[-1] = (p0, max(p1, t1))
            else:
                merged.append((t0, t1))

        cursor = 0.0
        seg_idx = 0

        for t0, t1 in merged:
            if (t0 - cursor) * wlen >= float(min_remaining_wall):
                sx1 = w.x1 + (w.x2 - w.x1) * cursor
                sy1 = w.y1 + (w.y2 - w.y1) * cursor
                sx2 = w.x1 + (w.x2 - w.x1) * t0
                sy2 = w.y1 + (w.y2 - w.y1) * t0
                fused_walls.append({"id": f"{w.id}_seg{seg_idx}", "x1": sx1, "y1": sy1, "x2": sx2, "y2": sy2, "thickness": w.thickness})
                seg_idx += 1

            cursor = max(cursor, t1)

        if (1.0 - cursor) * wlen >= float(min_remaining_wall):
            sx1 = w.x1 + (w.x2 - w.x1) * cursor
            sy1 = w.y1 + (w.y2 - w.y1) * cursor
            fused_walls.append({"id": f"{w.id}_seg{seg_idx}", "x1": sx1, "y1": sy1, "x2": w.x2, "y2": w.y2, "thickness": w.thickness})

    door_fused_final = []
    for d in door_fused:
        if d.get("attached_wall_id") is None:
            continue
        door_fused_final.append({k: d[k] for k in ("id", "hinge", "strike", "width", "angle", "swing", "attached_wall_id")})

    fused_walls = _remove_symbol_artifact_walls(fused_walls, door_list)

    fused_walls.sort(
        key=lambda wall: (
            round(float(wall["y1"]), 4),
            round(float(wall["x1"]), 4),
            round(float(wall["y2"]), 4),
            round(float(wall["x2"]), 4),
            str(wall["id"]),
        )
    )
    door_fused_final.sort(
        key=lambda door: (
            round(float(door["hinge"][1]), 4),
            round(float(door["hinge"][0]), 4),
            str(door["attached_wall_id"]),
            str(door["id"]),
        )
    )

    return {"walls": fused_walls, "doors": door_fused_final}


def _read_json(path: Path) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=True)


def fuse_from_files(
    *,
    walls_path: Path,
    doors_path: Path,
    out_path: Path,
    geometry_path: Optional[Path] = None,
    attach_threshold: float = 35.0,
) -> Dict[str, Any]:
    walls = _read_json(walls_path)
    doors = _read_json(doors_path)
    fused = fuse_walls_and_doors(walls, doors, attach_threshold=attach_threshold)
    if geometry_path is not None and geometry_path.exists():
        geometry = _read_json(geometry_path)
        fused = _cleanup_fused_walls_with_geometry(fused, geometry, min_remaining_wall=2.0)
    _write_json(out_path, fused)
    return fused


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--walls", required=True)
    p.add_argument("--doors", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--geometry")
    p.add_argument("--attach-threshold", type=float, default=35.0)
    args = p.parse_args()

    fuse_from_files(
        walls_path=Path(args.walls),
        doors_path=Path(args.doors),
        out_path=Path(args.out),
        geometry_path=Path(args.geometry) if args.geometry else None,
        attach_threshold=float(args.attach_threshold),
    )
