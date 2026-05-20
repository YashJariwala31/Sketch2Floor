"""Overlay placed door geometry on a floorplan image.

Reads `placed_doors.json` (hinge/leaf/arc points) and draws the result on top of an
input image using OpenCV for quick visual verification.
"""

import os
import cv2
import json
import numpy as np
from functools import lru_cache
from pathlib import Path
import sys


def _door_sort_key(door):
    hinge = door.get("hinge") or [0.0, 0.0]
    return (
        round(float(hinge[1]), 4),
        round(float(hinge[0]), 4),
        str(door.get("attached_wall_id", "")),
        str(door.get("id", "")),
    )


@lru_cache(maxsize=1)
def _load_window_template():
    candidates = []
    env_path = os.environ.get("S2FP_WINDOW_TEMPLATE_PATH")
    if env_path:
        candidates.append(Path(env_path))
    candidates.append(Path(__file__).resolve().parent / "Wind.json")
    candidates.append(Path(r"C:\Users\yashj\Desktop\original\Wind.json"))

    for candidate in candidates:
        if candidate.exists():
            with open(candidate, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
    return None


def _window_template_bounds(template):
    points = []
    for line in template.get("lines", []):
        if isinstance(line, dict):
            points.append((float(line["x1"]), float(line["y1"])))
            points.append((float(line["x2"]), float(line["y2"])))
    if not points:
        return None
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return min(xs), min(ys), max(xs), max(ys)


def _template_polyline_points_within_bounds(polyline, bounds, pad_ratio=0.08):
    if not isinstance(polyline, list):
        return []
    min_x, min_y, max_x, max_y = bounds
    width = max(max_x - min_x, 1e-6)
    height = max(max_y - min_y, 1e-6)
    pad_x = width * pad_ratio
    pad_y = height * pad_ratio
    points = []
    for point in polyline:
        if isinstance(point, dict) and "x" in point and "y" in point:
            x = float(point["x"])
            y = float(point["y"])
            if (min_x - pad_x) <= x <= (max_x + pad_x) and (min_y - pad_y) <= y <= (max_y + pad_y):
                points.append((x, y))
    return points


def _draw_windows(img, windows_data):
    windows = windows_data.get('windows', []) if isinstance(windows_data, dict) else []
    template = _load_window_template()
    bounds = _window_template_bounds(template) if template else None
    use_template = bool(bounds and template)
    for window in windows:
        if not isinstance(window, dict):
            continue

        start = window.get('start')
        end = window.get('end')
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
        wall_thickness = window.get('wall_thickness', 0.0)
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
                tuple(int(round(value)) for value in (clear_start + normal * clear_half_depth)),
                tuple(int(round(value)) for value in (clear_end + normal * clear_half_depth)),
                tuple(int(round(value)) for value in (clear_end - normal * clear_half_depth)),
                tuple(int(round(value)) for value in (clear_start - normal * clear_half_depth)),
            ],
            dtype=np.int32,
        ).reshape((-1, 1, 2))
        cv2.fillPoly(img, [clear_polygon], (255, 255, 255))

        def local_point(u, v):
            return start_pt + tangent * (length * u) + normal * (symbol_half_depth * 2.0 * v)

        def as_pt(point):
            return tuple(int(round(value)) for value in point)

        def draw_segment(u1, v1, u2, v2, thickness=line_thickness):
            cv2.line(img, as_pt(local_point(u1, v1)), as_pt(local_point(u2, v2)), (0, 0, 0), thickness)

        if use_template:
            min_x, min_y, max_x, max_y = bounds
            width = max(max_x - min_x, 1e-6)
            height = max(max_y - min_y, 1e-6)
            center_y = (min_y + max_y) / 2.0

            def norm_xy(x, y):
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


def draw_openings(image_path, placed_json_path, windows_json_path=None):
    img = cv2.imread(image_path)

    with open(placed_json_path) as f:
        data = json.load(f)

    doors = sorted(data.get('doors', []), key=_door_sort_key)

    for door in doors:
        # draw hinge
        hx, hy = map(lambda value: int(round(float(value))), door['hinge'])
        cv2.circle(img, (hx, hy), 8, (0,0,0), -1)

        # draw leaf
        leaf = door['leaf']
        cv2.line(img,
                 tuple(map(int, leaf[0])),
                 tuple(map(int, leaf[1])),
                 (0,0,0), 6)

        # draw arc
        arc = door['arc']
        for i in range(len(arc)-1):
            pt1 = tuple(map(int, arc[i]))
            pt2 = tuple(map(int, arc[i+1]))
            cv2.line(img, pt1, pt2, (0,0,0), 6)

        cv2.polylines(img, [np.array(arc, dtype=int)], False, (0,0,0), 5)

    if windows_json_path:
        with open(windows_json_path) as f:
            windows_data = json.load(f)
        _draw_windows(img, windows_data)

    return img

if __name__ == '__main__':
    if len(sys.argv) < 2:
        raise SystemExit('Usage: python overlay.py <image_id> [--doors <placed_doors.json>] [--windows <placed_windows.json>] [--out <overlay.png>]')

    base_path = Path(__file__).resolve().parent
    root_path = base_path.parent
    arg = sys.argv[1]
    input_path = Path(arg)

    if input_path.exists() and input_path.is_file():
        image_path = input_path
        image_id = input_path.stem
    else:
        image_id = arg
        original_dir = root_path / 'original'
        candidates = [
            original_dir / f'{image_id}.jpeg',
            original_dir / f'{image_id}.jpg',
            original_dir / f'{image_id}.png',
        ]
        image_path = next((p for p in candidates if p.exists() and p.is_file()), None)
        if image_path is None:
            raise SystemExit(f'Failed to resolve image for {arg}')

    placed_path = Path(sys.argv[sys.argv.index('--doors') + 1]) if '--doors' in sys.argv else None
    windows_path = Path(sys.argv[sys.argv.index('--windows') + 1]) if '--windows' in sys.argv else None
    if placed_path is None:
        placed_path = Path(
            os.environ.get('S2FP_PLACED_DOORS_PATH', str(root_path / 'placed_doors.json'))
        )
    if windows_path is None:
        env_windows_path = os.environ.get('S2FP_PLACED_WINDOWS_PATH')
        windows_path = Path(env_windows_path) if env_windows_path else None
    out_path = (
        Path(sys.argv[sys.argv.index('--out') + 1])
        if '--out' in sys.argv
        else Path(
            os.environ.get(
                'S2FP_OVERLAY_PATH',
                str(root_path / 'predictions' / f'overlay_{image_id}.png'),
            )
        )
    )

    if windows_path is not None and not windows_path.exists():
        windows_path = None

    output = draw_openings(str(image_path), str(placed_path), str(windows_path) if windows_path is not None else None)
    if output is None:
        raise SystemExit(f'Failed to read image: {image_path}')

    out_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out_path), output)
    print(f'Saved {out_path}')
