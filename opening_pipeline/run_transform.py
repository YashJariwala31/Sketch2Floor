"""Place detected doors using a template and geometry predictions.

Reads config from `transform_config.json`, loads the door template JSON and the
detected door geometry JSON, and writes `placed_doors.json` containing world-space
hinge/leaf/arc coordinates.
"""

import os
import json
import cv2
from pathlib import Path

from opening_pipeline.transform import reconstruct_doors_3point


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

    if not WALLS_PATH:
        raise ValueError('transform_config.json must define paths.walls for 3-point reconstruction')

    walls_path = (ROOT_DIR / WALLS_PATH) if not os.path.isabs(WALLS_PATH) else Path(WALLS_PATH)
    with open(walls_path, "r") as f:
        wall_polygons = json.load(f)

    door_mask_path = ROOT_DIR / 'predictions' / f'{image_id}_door.png'
    door_mask = cv2.imread(str(door_mask_path), cv2.IMREAD_GRAYSCALE)
    if door_mask is None:
        raise ValueError(f'Failed to read door mask: {door_mask_path}')

    original_candidates = [
        ROOT_DIR / 'original' / f'{image_id}.jpeg',
        ROOT_DIR / 'original' / f'{image_id}.jpg',
        ROOT_DIR / 'original' / f'{image_id}.png',
    ]
    original_img = None
    for p in original_candidates:
        original_img = cv2.imread(str(p))
        if original_img is not None:
            break

    placed, debug = reconstruct_doors_3point(
        template,
        TEMPLATE_HEIGHT,
        door_mask=door_mask,
        wall_polygons=wall_polygons,
        debug_image=original_img,
    )

    if debug is not None:
        (ROOT_DIR / 'predictions').mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(ROOT_DIR / 'predictions' / f'debug_doors_{image_id}.png'), debug)

    output_path = (ROOT_DIR / OUTPUT_PATH) if not os.path.isabs(OUTPUT_PATH) else Path(OUTPUT_PATH)
    with open(output_path, "w") as f:
        json.dump({"doors": placed}, f, indent=2)


if __name__ == "__main__":
    main()
