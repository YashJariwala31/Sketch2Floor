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
            verts = w["vertices"]
            if len(verts) < 2:
                continue
            wid = str(w.get("id", w.get("wall_id", f"wallpoly_{i}")))
            for j in range(len(verts)):
                x1, y1 = verts[j]
                x2, y2 = verts[(j + 1) % len(verts)]
                out.append(
                    Wall(
                        id=f"{wid}_e{j}",
                        x1=_as_float(x1),
                        y1=_as_float(y1),
                        x2=_as_float(x2),
                        y2=_as_float(y2),
                        thickness=None,
                    )
                )
            continue

        raise ValueError(f"Unrecognized wall format at index {i}: keys={list(w.keys())}")

    return out


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

        hinge = d["hinge"]
        if not (isinstance(hinge, (list, tuple)) and len(hinge) == 2):
            raise ValueError(f"door hinge must be [x,y] at index {i}")

        arc_end = None
        if "arc_end" in d:
            arc_end = d["arc_end"]
        elif "arc" in d and isinstance(d["arc"], list) and len(d["arc"]) > 0:
            arc_end = d["arc"][-1]
        elif "leaf" in d and isinstance(d["leaf"], list) and len(d["leaf"]) > 0:
            arc_end = d["leaf"][-1]

        if arc_end is None or not (isinstance(arc_end, (list, tuple)) and len(arc_end) == 2):
            raise ValueError(
                f"door must include 'arc_end' (or an 'arc'/'leaf' to infer it) at index {i}"
            )

        out.append(
            {
                "id": str(d.get("id", f"door_{i}")),
                "hinge": [_as_float(hinge[0]), _as_float(hinge[1])],
                "arc_end": [_as_float(arc_end[0]), _as_float(arc_end[1])],
            }
        )

    return out


def fuse_walls_and_doors(
    walls: Any,
    doors: Any,
    *,
    attach_threshold: float = 15.0,
    perpendicular_eps_deg: float = 20.0,
    min_remaining_wall: float = 2.0,
) -> Dict[str, Any]:
    wall_list = _parse_walls(walls)
    door_list = _parse_doors(doors)

    door_fused: List[Dict[str, Any]] = []

    openings_by_wall: Dict[str, List[Tuple[float, float, Dict[str, Any]]]] = {}

    for d in door_list:
        hx, hy = d["hinge"]
        ax, ay = d["arc_end"]
        dx = ax - hx
        dy = ay - hy
        width = _norm(dx, dy)
        if width <= 1e-6:
            continue

        best_wall: Optional[Wall] = None
        best_proj = None
        best_dist = float("inf")
        best_t = 0.0

        for w in wall_list:
            projx, projy, t, dist = _project_point_to_segment(hx, hy, w.x1, w.y1, w.x2, w.y2)
            if dist < best_dist:
                best_dist = dist
                best_wall = w
                best_proj = (projx, projy)
                best_t = t

        if best_wall is None or best_proj is None:
            continue
        if best_dist > float(attach_threshold):
            continue

        wxn, wyn, wlen = _wall_direction(best_wall)
        if wlen <= 1e-9:
            continue

        projx, projy = best_proj

        perp_x, perp_y = _perp(wxn, wyn)
        sign = 1.0 if _dot(perp_x, perp_y, dx, dy) >= 0.0 else -1.0
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

        hinge_t = best_t

        forward_len = (1.0 - hinge_t) * wlen
        backward_len = hinge_t * wlen

        if forward_len >= width:
            t0 = hinge_t
            t1 = hinge_t + width / wlen
        elif backward_len >= width:
            t0 = hinge_t - width / wlen
            t1 = hinge_t
        else:
            continue

        t0 = max(0.0, min(1.0, t0))
        t1 = max(0.0, min(1.0, t1))
        if abs(t1 - t0) * wlen < float(min_remaining_wall):
            continue

        attached_wall_id = best_wall.id

        door_out = {
            "id": d["id"],
            "hinge": [projx, projy],
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
            fused_walls.append({"id": w.id, "x1": w.x1, "y1": w.y1, "x2": w.x2, "y2": w.y2})
            continue

        openings.sort(key=lambda x: x[0])

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
                fused_walls.append({"id": f"{w.id}_seg{seg_idx}", "x1": sx1, "y1": sy1, "x2": sx2, "y2": sy2})
                seg_idx += 1

            cursor = max(cursor, t1)

        if (1.0 - cursor) * wlen >= float(min_remaining_wall):
            sx1 = w.x1 + (w.x2 - w.x1) * cursor
            sy1 = w.y1 + (w.y2 - w.y1) * cursor
            fused_walls.append({"id": f"{w.id}_seg{seg_idx}", "x1": sx1, "y1": sy1, "x2": w.x2, "y2": w.y2})

    door_fused_final = []
    for d in door_fused:
        if d.get("attached_wall_id") is None:
            continue
        door_fused_final.append({k: d[k] for k in ("id", "hinge", "width", "angle", "swing", "attached_wall_id")})

    return {"walls": fused_walls, "doors": door_fused_final}


def _read_json(path: Path) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def fuse_from_files(
    *,
    walls_path: Path,
    doors_path: Path,
    out_path: Path,
    attach_threshold: float = 15.0,
) -> Dict[str, Any]:
    walls = _read_json(walls_path)
    doors = _read_json(doors_path)
    fused = fuse_walls_and_doors(walls, doors, attach_threshold=attach_threshold)
    _write_json(out_path, fused)
    return fused


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--walls", required=True)
    p.add_argument("--doors", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--attach-threshold", type=float, default=15.0)
    args = p.parse_args()

    fuse_from_files(
        walls_path=Path(args.walls),
        doors_path=Path(args.doors),
        out_path=Path(args.out),
        attach_threshold=float(args.attach_threshold),
    )
