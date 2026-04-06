"""Place detected doors using a template and geometry predictions.

Reads config from `transform_config.json`, loads the door template JSON and the
detected door geometry JSON, and writes `placed_doors.json` containing world-space
hinge/leaf/arc coordinates.
"""

import os
import json
from transform import place_single_door


with open("transform_config.json") as f:
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


def main():
    with open(TEMPLATE_PATH, "r") as f:
        template = json.load(f)
    with open(GEOMETRY_PATH, "r") as f:
        geometry = json.load(f)
    doors = geometry.get("doors", [])
    placed = [place_single_door(template, d, TEMPLATE_HEIGHT) for d in doors]
    with open(OUTPUT_PATH, "w") as f:
        json.dump({"doors": placed}, f, indent=2)


if __name__ == "__main__":
    main()
