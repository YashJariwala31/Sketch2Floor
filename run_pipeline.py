"""Run the end-to-end pipeline.

Sequentially executes:
- door/window model inference
- mask-to-geometry conversion
- door placement (transform)
- overlay visualization
"""

import os
import subprocess
import sys
import shutil
from pathlib import Path

image_input = input('Enter image number: ').strip()
image_input = image_input.strip('"').strip("'")
input_path = Path(image_input)

ROOT_DIR = Path(__file__).resolve().parent
python = sys.executable

original_dir = ROOT_DIR / 'original'

if input_path.exists() and input_path.is_file():
    image_path = input_path
    image_id = input_path.stem
else:
    image_id = input_path.stem
    candidates = [
        original_dir / f'{image_id}.jpeg',
        original_dir / f'{image_id}.jpg',
        original_dir / f'{image_id}.png',
    ]
    image_path = next((p for p in candidates if p.exists() and p.is_file()), candidates[0])

print(f'[INFO] Using image_id={image_id} image_path={image_path}')

(ROOT_DIR / 'predictions').mkdir(parents=True, exist_ok=True)
(ROOT_DIR / 'intermediate').mkdir(parents=True, exist_ok=True)

door_mask = ROOT_DIR / 'predictions' / f'{image_id}_door.png'
window_mask = ROOT_DIR / 'predictions' / f'{image_id}_window.png'
geometry_json = ROOT_DIR / 'predictions' / f'{image_id}_geometry.json'
annotated_img = ROOT_DIR / 'predictions' / f'{image_id}_annotated.png'

print('[STEP 1] Running wall pipeline...')
subprocess.run([python, '-m', 'wall_pipeline.main', str(image_path)], check=True)

wall_src = ROOT_DIR / 'wall_pipeline' / 'data' / 'intermediate' / 'wall_polygons.json'
wall_dst = ROOT_DIR / 'intermediate' / 'wall_polygons.json'
if not wall_src.exists():
    raise FileNotFoundError(f'Wall polygons not generated: {wall_src}')
shutil.copyfile(wall_src, wall_dst)

print('[STEP 2] Running detection...')
subprocess.run([python, '-m', 'opening_pipeline.test_final', '--image', str(image_path)], check=True)

print('[STEP 3] Mask → geometry...')
subprocess.run(
    [
        python,
        '-m',
        'opening_pipeline.mask_to_geometry',
        '--image',
        str(image_path),
        '--door_mask',
        str(door_mask),
        '--window_mask',
        str(window_mask),
        '--out_json',
        str(geometry_json),
        '--out_annotated',
        str(annotated_img),
    ],
    check=True,
)

if not geometry_json.exists() or geometry_json.stat().st_size == 0:
    raise SystemExit('[ERROR] Geometry output was not generated; aborting downstream steps.')

print('[STEP 4] Door placement...')
env = os.environ.copy()
env['IMAGE_ID'] = image_id
subprocess.run([python, '-m', 'opening_pipeline.run_transform'], check=True, env=env)

print('[STEP 5] Overlay...')
subprocess.run([python, '-m', 'opening_pipeline.overlay', image_id], check=True)

print('DONE')
