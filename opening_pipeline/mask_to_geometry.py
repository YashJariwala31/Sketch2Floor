"""
Convert predicted door/window mask images into structured geometry outputs.

Takes binary mask PNGs (doors/windows) and extracts bounding boxes + centers,
then writes JSON geometry and optional annotated images. Supports single-image
mode and batch folder mode (with optional walls JSON integration utilities).
"""

import argparse
import json
import math
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np


def _rounded_key(*values: float) -> Tuple[float, ...]:
    return tuple(round(float(value), 4) for value in values)


def _load_grayscale(path: str) -> np.ndarray:
    img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise FileNotFoundError(f"Failed to read image: {path}")
    return img


def _binarize(mask_gray: np.ndarray, thresh: int = 127) -> np.ndarray:
    _, bw = cv2.threshold(mask_gray, thresh, 255, cv2.THRESH_BINARY)
    return bw


def _morph_close(bw: np.ndarray, kernel_size: int = 5, iterations: int = 1) -> np.ndarray:
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_size, kernel_size))
    return cv2.morphologyEx(bw, cv2.MORPH_CLOSE, kernel, iterations=iterations)


def _find_external_contours(bw: np.ndarray) -> List[np.ndarray]:
    contours, _hier = cv2.findContours(bw, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    return sorted(contours, key=_contour_sort_key)


def _contour_sort_key(contour: np.ndarray) -> Tuple[float, float, float, float]:
    x, y, w, h = cv2.boundingRect(contour)
    area = float(cv2.contourArea(contour))
    return _rounded_key(y, x, -area, max(w, h))


def _canonicalize_box_points(points: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
    if not points:
        return []
    center_x = sum(float(x) for x, _ in points) / len(points)
    center_y = sum(float(y) for _, y in points) / len(points)
    ordered = sorted(
        ((float(x), float(y)) for x, y in points),
        key=lambda pt: (
            round(math.atan2(pt[1] - center_y, pt[0] - center_x), 8),
            round((pt[0] - center_x) ** 2 + (pt[1] - center_y) ** 2, 8),
        ),
    )
    start_index = min(range(len(ordered)), key=lambda idx: _rounded_key(ordered[idx][1], ordered[idx][0]))
    return ordered[start_index:] + ordered[:start_index]


def _min_area_rect_points(contour: np.ndarray) -> List[Tuple[float, float]]:
    rect = cv2.minAreaRect(contour)
    box = cv2.boxPoints(rect)
    return _canonicalize_box_points([(float(x), float(y)) for x, y in box])


def _opening_sort_key(item: Dict[str, Any]) -> Tuple[float, float, float, float]:
    return (
        round(float(item.get("center_y", 0.0)), 4),
        round(float(item.get("center_x", 0.0)), 4),
        round(float(item.get("height", 0.0)), 4),
        round(float(item.get("width", 0.0)), 4),
    )


def _reindex_openings(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    ordered = []
    for index, item in enumerate(sorted(items, key=_opening_sort_key)):
        normalized = dict(item)
        normalized["id"] = int(index)
        ordered.append(normalized)
    return ordered


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, sort_keys=True)


def extract_bboxes_and_centers_from_mask(
    mask_path: str,
    *,
    original_size: Optional[Tuple[int, int]] = None,
    bin_thresh: int = 127,
    close_kernel: int = 5,
    close_iterations: int = 1,
    area_threshold: float = 100.0,
    include_rotated_box: bool = False,
) -> List[Dict[str, Any]]:
    """Extract axis-aligned bounding boxes and centers from a (door/window) mask.

    - Loads as grayscale
    - Thresholds to binary
    - Morphological closing to join broken parts
    - Finds external contours
    - Filters by contour area

    If original_size=(W,H) is provided, the mask is resized to match exactly.
    """

    mask_gray = _load_grayscale(mask_path)

    if original_size is not None:
        ow, oh = original_size
        if mask_gray.shape[1] != ow or mask_gray.shape[0] != oh:
            mask_gray = cv2.resize(mask_gray, (ow, oh), interpolation=cv2.INTER_NEAREST)

    bw = _binarize(mask_gray, thresh=bin_thresh)
    bw = _morph_close(bw, kernel_size=close_kernel, iterations=close_iterations)

    if cv2.countNonZero(bw) == 0:
        return []

    contours = _find_external_contours(bw)

    out: List[Dict[str, Any]] = []
    for cnt in contours:
        area = float(cv2.contourArea(cnt))
        if area < area_threshold:
            continue

        x, y, w, h = cv2.boundingRect(cnt)
        cx = float(x + w / 2.0)
        cy = float(y + h / 2.0)

        item: Dict[str, Any] = {
            "id": -1,
            "x": int(x),
            "y": int(y),
            "width": int(w),
            "height": int(h),
            "center_x": float(cx),
            "center_y": float(cy),
            "orientation": "unknown",
        }

        item["rotated_box"] = _min_area_rect_points(cnt)

        out.append(item)

    return _reindex_openings(out)


def convert_masks_to_geometry(
    door_mask_path: str,
    window_mask_path: str,
    original_image_path: str,
    *,
    bin_thresh: int = 127,
    close_kernel: int = 5,
    close_iterations: int = 1,
    area_threshold: float = 100.0,
    include_rotated_box: bool = False,
    annotated_output_path: Optional[str] = None,
) -> Tuple[Dict[str, Any], np.ndarray]:
    """Convert door/window masks into JSON geometry + an annotated image."""

    original_bgr = cv2.imread(original_image_path, cv2.IMREAD_COLOR)
    if original_bgr is None:
        raise FileNotFoundError(f"Failed to read image: {original_image_path}")

    h, w = original_bgr.shape[:2]

    doors = extract_bboxes_and_centers_from_mask(
        door_mask_path,
        original_size=(w, h),
        bin_thresh=bin_thresh,
        close_kernel=close_kernel,
        close_iterations=close_iterations,
        area_threshold=area_threshold,
        include_rotated_box=include_rotated_box,
    )

    windows = extract_bboxes_and_centers_from_mask(
        window_mask_path,
        original_size=(w, h),
        bin_thresh=bin_thresh,
        close_kernel=close_kernel,
        close_iterations=close_iterations,
        area_threshold=area_threshold,
        include_rotated_box=include_rotated_box,
    )

    annotated = original_bgr.copy()

    if len(doors) == 0 and len(windows) == 0:
        print("[WARN] No openings detected; generating wall-only geometry output")

    for d in doors:
        x, y, ww, hh = int(d["x"]), int(d["y"]), int(d["width"]), int(d["height"])
        cv2.rectangle(annotated, (x, y), (x + ww, y + hh), (0, 0, 255), 2)
        cv2.circle(
            annotated,
            (
                int(round(float(d["center_x"]))),
                int(round(float(d["center_y"]))),
            ),
            3,
            (0, 0, 255),
            -1,
        )

    for win in windows:
        x, y, ww, hh = int(win["x"]), int(win["y"]), int(win["width"]), int(win["height"])
        cv2.rectangle(annotated, (x, y), (x + ww, y + hh), (255, 0, 0), 2)
        cv2.circle(
            annotated,
            (
                int(round(float(win["center_x"]))),
                int(round(float(win["center_y"]))),
            ),
            3,
            (255, 0, 0),
            -1,
        )

    if annotated_output_path:
        cv2.imwrite(annotated_output_path, annotated)

    geometry = {"doors": doors, "windows": windows}
    return geometry, annotated


def _load_walls_json(path: Path) -> List[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict) or "walls" not in data or not isinstance(data["walls"], list):
        raise ValueError(f"Invalid walls JSON format (expected dict with 'walls' list): {path}")
    walls = data["walls"]
    for w in walls:
        if not isinstance(w, dict):
            raise ValueError(f"Invalid wall item in {path}")
        for k in ("id", "x1", "y1", "x2", "y2"):
            if k not in w:
                raise ValueError(f"Wall missing key '{k}' in {path}")
    return walls


def _point_to_segment_projection(
    px: float,
    py: float,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
) -> Tuple[float, float, float]:
    vx = x2 - x1
    vy = y2 - y1
    wx = px - x1
    wy = py - y1

    denom = float(vx * vx + vy * vy)
    if denom <= 1e-9:
        dx = px - x1
        dy = py - y1
        return float(x1), float(y1), float((dx * dx + dy * dy) ** 0.5)

    t = float((wx * vx + wy * vy) / denom)
    if t < 0.0:
        t = 0.0
    elif t > 1.0:
        t = 1.0

    projx = float(x1 + t * vx)
    projy = float(y1 + t * vy)
    dx = px - projx
    dy = py - projy
    dist = float((dx * dx + dy * dy) ** 0.5)
    return projx, projy, dist


def _wall_orientation(x1: float, y1: float, x2: float, y2: float) -> str:
    dx = abs(x2 - x1)
    dy = abs(y2 - y1)
    return "horizontal" if dx >= dy else "vertical"


def _refine_one_element_to_wall(
    elem: Dict[str, Any],
    walls: List[Dict[str, Any]],
    *,
    max_wall_distance_px: float = 30.0,
) -> Optional[Dict[str, Any]]:
    x = float(elem["x"])
    y = float(elem["y"])
    w = float(elem["width"])
    h = float(elem["height"])
    cx = float(x + w / 2.0)
    cy = float(y + h / 2.0)

    best_wall: Optional[Dict[str, Any]] = None
    best_proj: Optional[Tuple[float, float]] = None
    best_key: Optional[Tuple[float, str]] = None

    for wall in walls:
        wx1 = float(wall["x1"])
        wy1 = float(wall["y1"])
        wx2 = float(wall["x2"])
        wy2 = float(wall["y2"])
        projx, projy, dist = _point_to_segment_projection(cx, cy, wx1, wy1, wx2, wy2)
        candidate_key = (round(float(dist), 6), str(wall.get("id", "")))
        if best_key is None or candidate_key < best_key:
            best_key = candidate_key
            best_wall = wall
            best_proj = (projx, projy)

    if best_wall is None or best_proj is None:
        return None
    if best_key is None or best_key[0] > float(max_wall_distance_px):
        return None

    wx1 = float(best_wall["x1"])
    wy1 = float(best_wall["y1"])
    wx2 = float(best_wall["x2"])
    wy2 = float(best_wall["y2"])
    orientation = _wall_orientation(wx1, wy1, wx2, wy2)
    projx, projy = best_proj

    width_along_wall = float(min(w, h))

    if orientation == "horizontal":
        snapped_cx = float(projx)
        snapped_cy = float(wy1)
    else:
        snapped_cx = float(wx1)
        snapped_cy = float(projy)

    return {
        "id": int(elem["id"]),
        "cx": float(snapped_cx),
        "cy": float(snapped_cy),
        "width": float(width_along_wall),
        "orientation": str(orientation),
        "wall_id": int(best_wall["id"]),
    }


def refine_doors_windows_with_walls(
    *,
    walls: List[Dict[str, Any]],
    doors: List[Dict[str, Any]],
    windows: List[Dict[str, Any]],
    max_wall_distance_px: float = 30.0,
) -> Dict[str, List[Dict[str, Any]]]:
    refined_doors: List[Dict[str, Any]] = []
    refined_windows: List[Dict[str, Any]] = []

    for d in doors:
        rd = _refine_one_element_to_wall(d, walls, max_wall_distance_px=max_wall_distance_px)
        if rd is not None:
            refined_doors.append(rd)

    for w in windows:
        rw = _refine_one_element_to_wall(w, walls, max_wall_distance_px=max_wall_distance_px)
        if rw is not None:
            refined_windows.append(rw)

    return {"doors": refined_doors, "windows": refined_windows}


def _iter_images_in_dir(original_dir: str) -> List[Path]:
    exts = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}
    p = Path(original_dir)
    if not p.exists() or not p.is_dir():
        raise FileNotFoundError(f"Original directory not found: {original_dir}")
    files = [f for f in p.iterdir() if f.is_file() and f.suffix.lower() in exts]
    files.sort(key=lambda x: x.name)
    return files


def convert_masks_to_geometry_from_folders(
    *,
    original_dir: str,
    mask_dir: str,
    out_dir: str,
    walls_dir: Optional[str] = None,
    door_suffix: str = "_door.png",
    window_suffix: str = "_window.png",
    walls_suffix: str = "_walls.json",
    bin_thresh: int = 127,
    close_kernel: int = 5,
    close_iterations: int = 1,
    area_threshold: float = 100.0,
    include_rotated_box: bool = False,
    max_wall_distance_px: float = 30.0,
) -> Dict[str, int]:
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    mask_path = Path(mask_dir)
    if not mask_path.exists() or not mask_path.is_dir():
        raise FileNotFoundError(f"Mask directory not found: {mask_dir}")

    walls_path: Optional[Path] = None
    use_walls = False
    if walls_dir:
        candidate = Path(walls_dir)
        if candidate.exists() and candidate.is_dir():
            walls_path = candidate
            use_walls = True
        else:
            print(f"[INFO] Running without walls (walls_dir not found): {walls_dir}")
    else:
        print("[INFO] Running without walls")

    original_images = _iter_images_in_dir(original_dir)
    original_stems = {p.stem for p in original_images}

    orphan_masks: List[str] = []
    for m in mask_path.iterdir():
        if not m.is_file():
            continue
        name_lower = m.name.lower()
        if name_lower.endswith(door_suffix.lower()):
            stem = m.name[: -len(door_suffix)]
        elif name_lower.endswith(window_suffix.lower()):
            stem = m.name[: -len(window_suffix)]
        else:
            continue

        if stem not in original_stems:
            orphan_masks.append(m.name)

    if orphan_masks:
        orphan_masks.sort()
        print(f"[WARN] Found {len(orphan_masks)} mask file(s) with no matching original image stem.")
        for n in orphan_masks:
            print(f"[WARN] Orphan mask: {n}")

    total_images = 0
    processed = 0
    skipped = 0
    failed = 0
    succeeded = 0

    for img_path in original_images:
        total_images += 1
        stem = img_path.stem

        door_mask = mask_path / f"{stem}{door_suffix}"
        window_mask = mask_path / f"{stem}{window_suffix}"
        walls_json: Optional[Path] = None
        if use_walls and walls_path is not None:
            walls_json = walls_path / f"{stem}{walls_suffix}"

        print(f"[INFO] Image: {img_path.name}")
        print(f"[INFO] Expect door mask: {door_mask.name}")
        print(f"[INFO] Expect window mask: {window_mask.name}")
        if walls_json is not None:
            print(f"[INFO] Expect walls json: {walls_json.name}")

        if not door_mask.exists() or not window_mask.exists():
            missing: List[str] = []
            if not door_mask.exists():
                missing.append(door_mask.name)
            if not window_mask.exists():
                missing.append(window_mask.name)
            print(f"[WARN] Skipping {img_path.name}: missing mask(s): {', '.join(missing)}")
            skipped += 1
            continue

        if walls_json is not None and not walls_json.exists():
            print(f"[WARN] Walls missing for {img_path.name}: {walls_json.name}. Writing unaligned geometry.")
            walls_json = None

        out_json = out_path / f"{stem}_geometry.json"
        out_annotated = out_path / f"{stem}_annotated.png"

        processed += 1

        try:
            geometry, _annotated = convert_masks_to_geometry(
                str(door_mask),
                str(window_mask),
                str(img_path),
                bin_thresh=bin_thresh,
                close_kernel=close_kernel,
                close_iterations=close_iterations,
                area_threshold=area_threshold,
                include_rotated_box=include_rotated_box,
                annotated_output_path=str(out_annotated),
            )

            if len(geometry["doors"]) == 0 and len(geometry["windows"]) > 0:
                print("[WARN] No doors detected")
                print("[INFO] Processing partial detection")
            elif len(geometry["windows"]) == 0 and len(geometry["doors"]) > 0:
                print("[WARN] No windows detected")
                print("[INFO] Processing partial detection")

            if walls_json is not None:
                print("[INFO] Walls provided but ignored in bounding-box detection mode")
            payload: Dict[str, Any] = geometry

            _write_json(out_json, payload)

            print(f"[OK] Wrote: {out_json.name}")
            print(f"[OK] Wrote: {out_annotated.name}")
            succeeded += 1
        except ValueError as e:
            msg = str(e)
            if msg.startswith("Empty mask(s):"):
                print(f"[WARN] Skipping {img_path.name}: {msg}")
                skipped += 1
            else:
                print(f"[ERROR] Failed on {img_path.name}: {e}")
                failed += 1
        except Exception as e:
            print(f"[ERROR] Failed on {img_path.name}: {e}")
            failed += 1

    return {
        "total_images": int(total_images),
        "processed": int(processed),
        "succeeded": int(succeeded),
        "skipped": int(skipped),
        "failed": int(failed),
    }


def main() -> int:
    parser = argparse.ArgumentParser()

    mode = parser.add_mutually_exclusive_group(required=False)
    mode.add_argument("--image")
    mode.add_argument("--original_dir")

    parser.add_argument("--door_mask")
    parser.add_argument("--window_mask")
    parser.add_argument("--out_json")
    parser.add_argument("--out_annotated")

    parser.add_argument("--mask_dir", default="predictions")
    parser.add_argument("--walls_dir", default=None)
    parser.add_argument("--out_dir", default="predictions")
    parser.add_argument("--door_suffix", default="_door.png")
    parser.add_argument("--window_suffix", default="_window.png")
    parser.add_argument("--walls_suffix", default="_walls.json")
    parser.add_argument("--max_wall_distance_px", type=float, default=30.0)

    parser.add_argument("--bin_thresh", type=int, default=127)
    parser.add_argument("--close_kernel", type=int, default=5)
    parser.add_argument("--close_iterations", type=int, default=1)
    parser.add_argument("--area_threshold", type=float, default=100.0)
    parser.add_argument("--rotated", action="store_true")
    args = parser.parse_args()

    if len(sys.argv) == 1:
        args.original_dir = "C:\\Users\\yashj\\Desktop\\model\\original"
        if args.mask_dir is None:
            args.mask_dir = "predictions"
        if args.out_dir is None:
            args.out_dir = "predictions"
        print("[INFO] No arguments provided. Running in auto folder mode.")
        print(f"[INFO] original_dir={args.original_dir}")
        print(f"[INFO] mask_dir={args.mask_dir}")
        print(f"[INFO] walls_dir={args.walls_dir}")
        print(f"[INFO] out_dir={args.out_dir}")

    if args.original_dir:
        summary = convert_masks_to_geometry_from_folders(
            original_dir=args.original_dir,
            mask_dir=args.mask_dir,
            out_dir=args.out_dir,
            walls_dir=args.walls_dir,
            door_suffix=args.door_suffix,
            window_suffix=args.window_suffix,
            walls_suffix=args.walls_suffix,
            bin_thresh=args.bin_thresh,
            close_kernel=args.close_kernel,
            close_iterations=args.close_iterations,
            area_threshold=args.area_threshold,
            include_rotated_box=args.rotated,
            max_wall_distance_px=args.max_wall_distance_px,
        )

        print("[SUMMARY] Folder run complete")
        print(f"[SUMMARY] total_images={summary['total_images']}")
        print(f"[SUMMARY] processed={summary['processed']}")
        print(f"[SUMMARY] succeeded={summary['succeeded']}")
        print(f"[SUMMARY] skipped={summary['skipped']}")
        print(f"[SUMMARY] failed={summary['failed']}")
        return 0

    if not args.image:
        print("[ERROR] Missing required mode argument.")
        print("[ERROR] Provide either --original_dir (folder mode) or --image (single-image mode).")
        parser.print_help()
        return 1
    if not args.door_mask or not args.window_mask:
        print("[ERROR] Single-image mode requires --door_mask and --window_mask")
        parser.print_help()
        return 1
    if not args.out_json or not args.out_annotated:
        print("[ERROR] Single-image mode requires --out_json and --out_annotated")
        parser.print_help()
        return 1

    if not Path(args.image).exists():
        print(f"[ERROR] Original image not found: {args.image}")
        return 1
    if not Path(args.door_mask).exists():
        print(f"[ERROR] Door mask not found: {args.door_mask}")
        return 1
    if not Path(args.window_mask).exists():
        print(f"[ERROR] Window mask not found: {args.window_mask}")
        return 1

    walls_json_single: Optional[Path] = None
    if args.walls_dir:
        candidate = Path(args.walls_dir)
        if candidate.exists() and candidate.is_dir():
            candidate_file = candidate / f"{Path(args.image).stem}{args.walls_suffix}"
            if candidate_file.exists():
                walls_json_single = candidate_file
            else:
                print(f"[INFO] Running without walls (walls file not found): {candidate_file}")
        else:
            print(f"[INFO] Running without walls (walls_dir not found): {args.walls_dir}")
    else:
        print("[INFO] Running without walls")

    print(f"[INFO] Image: {Path(args.image).name}")
    print(f"[INFO] Door mask: {Path(args.door_mask).name}")
    print(f"[INFO] Window mask: {Path(args.window_mask).name}")

    try:
        geometry, _annotated = convert_masks_to_geometry(
            args.door_mask,
            args.window_mask,
            args.image,
            bin_thresh=args.bin_thresh,
            close_kernel=args.close_kernel,
            close_iterations=args.close_iterations,
            area_threshold=args.area_threshold,
            include_rotated_box=args.rotated,
            annotated_output_path=args.out_annotated,
        )

        if len(geometry["doors"]) == 0 and len(geometry["windows"]) > 0:
            print("[WARN] No doors detected")
            print("[INFO] Processing partial detection")
        elif len(geometry["windows"]) == 0 and len(geometry["doors"]) > 0:
            print("[WARN] No windows detected")
            print("[INFO] Processing partial detection")

        if walls_json_single is not None:
            print("[INFO] Walls provided but ignored in bounding-box detection mode")

        # -------- ADD IMAGE METADATA --------
        image = cv2.imread(args.image)
        h, w = image.shape[:2]

        geometry_output = {
            "image_width": w,
            "image_height": h,
            "doors": geometry["doors"],
            "windows": geometry["windows"],
        }

        payload: Dict[str, Any] = geometry_output

        _write_json(Path(args.out_json), payload)

        print(f"[OK] Wrote: {Path(args.out_json).name}")
        print(f"[OK] Wrote: {Path(args.out_annotated).name}")
        print("[SUMMARY] processed=1 succeeded=1 skipped=0 failed=0")
        return 0
    except Exception as e:
        print(f"[ERROR] Failed: {e}")
        print("[SUMMARY] processed=1 succeeded=0 skipped=0 failed=1")
        return 1


if __name__ == "__main__":
    sys.exit(main())
