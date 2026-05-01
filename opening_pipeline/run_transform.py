"""Place detected doors using a template and geometry predictions.

Reads config from `transform_config.json`, loads the door template JSON and the
detected door geometry JSON, and writes `placed_doors.json` containing world-space
hinge/leaf/arc coordinates.
"""

import json
import os
from pathlib import Path

from opening_pipeline.transform import place_single_door


BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent

with open(BASE_DIR / "transform_config.json") as f:
    config = json.load(f)

image_id = os.environ.get('IMAGE_ID', '3')

if isinstance(config.get('paths', {}).get('geometry'), str) and '{IMAGE}' in config['paths']['geometry']:
    config['paths']['geometry'] = config['paths']['geometry'].replace('{IMAGE}', image_id)
else:
    config['paths']['geometry'] = f'predictions/{image_id}_geometry.json'

TEMPLATE_PATH = config["paths"]["template"]
GEOMETRY_PATH = config["paths"]["geometry"]
OUTPUT_PATH = config["paths"]["output"]
TEMPLATE_HEIGHT = config["template"]["height"]

WALLS_PATH = os.environ.get("S2FP_WALLS_PATH", config.get("paths", {}).get("walls"))
ROOMS_PATH = os.environ.get("S2FP_ROOMS_PATH", config.get("paths", {}).get("rooms"))
GEOMETRY_PATH = os.environ.get("S2FP_GEOMETRY_PATH", GEOMETRY_PATH)
OUTPUT_PATH = os.environ.get("S2FP_PLACED_DOORS_PATH", OUTPUT_PATH)


def _resolve_path(path_value):
    return (ROOT_DIR / path_value) if not os.path.isabs(path_value) else Path(path_value)


def _door_sort_key(door):
    hinge = door.get("hinge") or [0.0, 0.0]
    attached_wall_id = str(door.get("attached_wall_id", ""))
    return (
        round(float(hinge[1]), 4),
        round(float(hinge[0]), 4),
        attached_wall_id,
        str(door.get("id", "")),
    )


def _write_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, sort_keys=True)
    os.replace(temp_path, path)


def main():
    template_path = _resolve_path(TEMPLATE_PATH)
    with open(template_path, "r") as f:
        template = json.load(f)

    geometry_path = _resolve_path(GEOMETRY_PATH)
    with open(geometry_path, "r", encoding="utf-8") as f:
        geometry = json.load(f)

    walls = None
    if WALLS_PATH:
        walls_path = _resolve_path(WALLS_PATH)
        if walls_path.exists():
            with open(walls_path, "r", encoding="utf-8") as f:
                walls = json.load(f)

    # Load room polygons for per-room door orientation
    room_polygons = None
    if ROOMS_PATH:
        rp = _resolve_path(ROOMS_PATH)
        if rp.exists():
            with open(rp, "r", encoding="utf-8") as f:
                room_polygons = json.load(f)
            print(f"[INFO] Loaded {len(room_polygons)} room polygons for door orientation")
        else:
            print(f"[WARN] Room polygons not found at {rp}, using fallback orientation")

    # Extract image dimensions for fallback orientation
    img_w = geometry.get('image_width')
    img_h = geometry.get('image_height')

    detections = sorted(
        geometry.get("doors", []),
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
        placement = place_single_door(
            template, det, TEMPLATE_HEIGHT,
            walls=walls,
            room_polygons=room_polygons,
            image_width=img_w,
            image_height=img_h,
        )
        if placement is None:
            print(f"[WARN] Skipping door {det.get('id', '?')}: no nearby wall/opening match")
            continue
        placed.append(placement)

    output_path = _resolve_path(OUTPUT_PATH)
    placed = sorted(placed, key=_door_sort_key)
    _write_json(output_path, {"doors": placed})


if __name__ == "__main__":
    main()
