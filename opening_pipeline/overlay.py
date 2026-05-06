"""Overlay placed door geometry on a floorplan image.

Reads `placed_doors.json` (hinge/leaf/arc points) and draws the result on top of an
input image using OpenCV for quick visual verification.
"""

import os
import cv2
import json
import numpy as np
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


def draw_doors(image_path, placed_json_path):
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

    return img

if __name__ == '__main__':
    if len(sys.argv) < 2:
        raise SystemExit('Usage: python overlay.py <image_id> [--doors <placed_doors.json>] [--out <overlay.png>]')

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
    if placed_path is None:
        placed_path = Path(
            os.environ.get('S2FP_PLACED_DOORS_PATH', str(root_path / 'placed_doors.json'))
        )
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

    output = draw_doors(str(image_path), str(placed_path))
    if output is None:
        raise SystemExit(f'Failed to read image: {image_path}')

    out_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out_path), output)
    print(f'Saved {out_path}')
