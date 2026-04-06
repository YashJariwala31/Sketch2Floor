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
from pathlib import Path

image_input = input('Enter image number: ').strip()
image_input = image_input.strip('"').strip("'")
input_path = Path(image_input)
image_id = input_path.stem

base_path = Path(__file__).resolve().parent

original_dir = base_path / 'original'

if input_path.exists() and input_path.is_file():
    image_path = input_path
elif (original_dir / input_path.name).exists() and (original_dir / input_path.name).is_file():
    image_path = original_dir / input_path.name
else:
    candidates = [
        original_dir / f'{image_id}.jpeg',
        original_dir / f'{image_id}.jpg',
        original_dir / f'{image_id}.png',
    ]
    image_path = next((p for p in candidates if p.exists() and p.is_file()), candidates[0])

print(f'[INFO] Using image_id={image_id} image_path={image_path}')
door_mask = base_path / 'predictions' / f'{image_id}_door.png'
window_mask = base_path / 'predictions' / f'{image_id}_window.png'
geometry_json = base_path / 'predictions' / f'{image_id}_geometry.json'
annotated_img = base_path / 'predictions' / f'{image_id}_annotated.png'

python = sys.executable

print('[STEP 1] Running inference...')
subprocess.run([python, str(base_path / 'test_final.py'), '--image', str(image_path)], check=True)

print('[STEP 2] Mask → geometry...')
subprocess.run(
    [
        python,
        str(base_path / 'mask_to_geometry.py'),
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

print('[STEP 3] Door placement...')
env = os.environ.copy()
env['IMAGE_ID'] = image_id
subprocess.run([python, str(base_path / 'run_transform.py')], check=True, env=env)

print('[STEP 4] Overlay...')
subprocess.run([python, str(base_path / 'overlay.py'), image_id], check=True)

print('✅ DONE')
