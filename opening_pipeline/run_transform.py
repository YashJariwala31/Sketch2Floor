"""Place detected doors using a template and geometry predictions.

Reads config from `transform_config.json`, loads the door template JSON and the
detected door geometry JSON, and writes `placed_doors.json` containing world-space
hinge/leaf/arc coordinates.
"""

import os
import json
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

WALLS_PATH = config.get("paths", {}).get("walls")


def main():
    template_path = (ROOT_DIR / TEMPLATE_PATH) if not os.path.isabs(TEMPLATE_PATH) else Path(TEMPLATE_PATH)
    with open(template_path, "r") as f:
        template = json.load(f)

    geometry_path = (ROOT_DIR / GEOMETRY_PATH) if not os.path.isabs(GEOMETRY_PATH) else Path(GEOMETRY_PATH)
    with open(geometry_path, "r", encoding="utf-8") as f:
        geometry = json.load(f)

    walls = None
    if WALLS_PATH:
        walls_path = (ROOT_DIR / WALLS_PATH) if not os.path.isabs(WALLS_PATH) else Path(WALLS_PATH)
        if walls_path.exists():
            with open(walls_path, "r", encoding="utf-8") as f:
                walls = json.load(f)

    # Load room polygons for per-room door orientation
    rooms_path_cfg = config.get("paths", {}).get("rooms")
    room_polygons = None
    if rooms_path_cfg:
        rp = (ROOT_DIR / rooms_path_cfg) if not os.path.isabs(rooms_path_cfg) else Path(rooms_path_cfg)
        if rp.exists():
            with open(rp, "r", encoding="utf-8") as f:
                room_polygons = json.load(f)
            print(f"[INFO] Loaded {len(room_polygons)} room polygons for door orientation")
        else:
            print(f"[WARN] Room polygons not found at {rp}, using fallback orientation")

    # Extract image dimensions for fallback orientation
    img_w = geometry.get('image_width')
    img_h = geometry.get('image_height')

    placed = []
    for det in geometry.get('doors', []):
        placed.append(place_single_door(
            template, det, TEMPLATE_HEIGHT,
            walls=walls,
            room_polygons=room_polygons,
            image_width=img_w,
            image_height=img_h,
        ))

    output_path = (ROOT_DIR / OUTPUT_PATH) if not os.path.isabs(OUTPUT_PATH) else Path(OUTPUT_PATH)
    with open(output_path, "w") as f:
        json.dump({"doors": placed}, f, indent=2)


if __name__ == "__main__":
    main()
